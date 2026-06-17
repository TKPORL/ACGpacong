# -*- coding: utf-8 -*-
"""
ACG游戏姬工具 - 网页版后端
提供 REST API:
  - /api/preview_dates  抓首页 + 几页,返回最新发布日 + 所有出现过的日期
  - /api/scrape         按日期/页数抓取帖子
  - /api/download/<id>  下载 txt/json(文件名按抓取日期段生成)
"""

import json
import os
import socket
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request

# 允许从同目录导入 acgyx_scraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acgyx_scraper import (  # noqa: E402
    collect_posts,
    fetch_post_detail,
    filter_posts,
    get_total_pages,
    parse_date,
    render_txt,
    requests,
    DEFAULT_HEADERS,
    build_txt_filename,
    fetch_list_page,
    EXCLUDED_CATEGORIES,
)

app = Flask(__name__, template_folder="templates", static_folder="static")

# CORS:允许单 HTML(file://)或其它来源直接调用 API
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return ("", 204)

# 任务进度存储
TASKS: Dict[str, Dict[str, Any]] = {}
TASKS_LOCK = threading.Lock()
# 任务停止标志 (task_id -> threading.Event)
STOP_FLAGS: Dict[str, threading.Event] = {}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def run_task(task_id: str, pages: int, date_from: Optional[datetime],
             date_to: Optional[datetime], delay: float, limit: int,
             stop_event: Optional[threading.Event] = None):
    """后台抓取任务(支持停止:stop_event.set() 可立刻中断)"""
    if stop_event is None:
        stop_event = threading.Event()
    STOP_FLAGS[task_id] = stop_event

    def log(msg: str):
        with TASKS_LOCK:
            TASKS[task_id]["logs"].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
            )

    def is_stopped() -> bool:
        return stop_event.is_set()

    def sleep_or_stop(sec: float) -> bool:
        """延迟,可被停止信号提前唤醒。返回 True 表示被停止"""
        return stop_event.wait(timeout=sec)

    try:
        with TASKS_LOCK:
            TASKS[task_id]["status"] = "running"
            TASKS[task_id]["started_at"] = datetime.now().isoformat()

        session = make_session()
        exclude = EXCLUDED_CATEGORIES.copy()  # 排除喵笔记

        if pages <= 0:
            total_pages = get_total_pages(session)
            pages = min(total_pages, 20)
            log(f"自动探测共 {total_pages} 页,本次抓取前 {pages} 页")

        log(f"开始抓取列表(共 {pages} 页) ...")
        posts = collect_posts(pages, session, delay, exclude)
        if is_stopped():
            log("已停止(列表阶段)")
            with TASKS_LOCK:
                TASKS[task_id]["status"] = "stopped"
            return
        posts = filter_posts(posts, exclude, date_from, date_to)
        log(f"列表筛选后: {len(posts)} 条")

        if limit > 0:
            posts = posts[:limit]
        total_n = len(posts)
        rows: List[Dict] = []
        for i, p in enumerate(posts, 1):
            if is_stopped():
                log(f"已停止(详情 {i}/{total_n} 之前)")
                break
            log(f"详情 [{i}/{total_n}] {p['title'][:36]}")
            rows.append(fetch_post_detail(p, session))
            with TASKS_LOCK:
                TASKS[task_id]["progress"] = i / max(total_n, 1)
            if i < total_n and sleep_or_stop(delay):
                log(f"已停止(详情 {i+1}/{total_n} 之前)")
                break

        # 即便被停止,已抓到的也返回
        txt = render_txt(rows)
        fname = build_txt_filename(date_from, date_to).replace(".txt", "")
        status = "stopped" if is_stopped() else "done"
        with TASKS_LOCK:
            TASKS[task_id]["status"] = status
            TASKS[task_id]["finished_at"] = datetime.now().isoformat()
            TASKS[task_id]["rows"] = rows
            TASKS[task_id]["txt"] = txt
            TASKS[task_id]["progress"] = 1.0
            TASKS[task_id]["filename"] = fname
            TASKS[task_id]["date_from"] = date_from.isoformat() if date_from else ""
            TASKS[task_id]["date_to"] = date_to.isoformat() if date_to else ""
        STOP_FLAGS.pop(task_id, None)
        yun = sum(1 for r in rows if r.get("yun_links"))
        if status == "stopped":
            log(f"已停止: 共抓到 {len(rows)} 条,含移动云盘 {yun} 条")
        else:
            log(f"完成: 共 {len(rows)} 条,含移动云盘 {yun} 条")
    except Exception as e:
        import traceback
        with TASKS_LOCK:
            TASKS[task_id]["status"] = "error"
            TASKS[task_id]["error"] = str(e)
        STOP_FLAGS.pop(task_id, None)
        log(f"[错误] {e}")


# --------------------- 路由 ---------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/preview_dates", methods=["GET"])
def api_preview_dates():
    """抓取首页 + 9 页(最多),返回:
      - latest_date: 最新发布的日期(YYYY-MM-DD)
      - latest_title: 最新帖子的标题
      - dates: 出现过的所有日期(去重,降序)
    用于进入页面时展示 + 填充下拉。
    """
    session = make_session()
    pages_to_scan = 10  # 用户要求 10 页以内足够
    all_dates: List[str] = []
    latest_date = ""           # 用字符串"YYYY-MM-DD"比较
    latest_title = ""
    try:
        for p in range(1, pages_to_scan + 1):
            try:
                posts = fetch_list_page(p, session)
            except Exception:
                break
            if not posts:
                break
            for it in posts:
                pt = it.get("pub_time", "")
                if pt and pt not in all_dates:
                    all_dates.append(pt)
                # 网站列表有置顶/老帖,需遍历找最新
                if pt and (not latest_date or pt > latest_date):
                    latest_date = pt
                    latest_title = it.get("title", "")
            if len(all_dates) >= 14:
                break
            time.sleep(0.3)
    except Exception as e:
        return jsonify({"error": str(e), "dates": all_dates,
                        "latest_date": latest_date,
                        "latest_title": latest_title}), 500

    # 降序(最新在前),并限制在最近一年内(避免 select 太多项)
    all_dates.sort(reverse=True)
    if latest_date and all_dates:
        try:
            cutoff = (datetime.fromisoformat(latest_date) - timedelta(days=365)).strftime("%Y-%m-%d")
            all_dates = [d for d in all_dates if d >= cutoff]
        except Exception:
            pass

    return jsonify({
        "latest_date": latest_date,
        "latest_title": latest_title,
        "dates": all_dates,
        "scanned_pages": min(pages_to_scan, len(all_dates)),
    })


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    data = request.get_json(force=True) or {}
    mode = (data.get("mode") or "single").lower()
    pages = int(data.get("pages", 0))
    delay = float(data.get("delay", 0.6))
    limit = int(data.get("limit", 0))

    # 按模式决定 date_from / date_to / pages
    if mode == "range":
        # 多天范围:严格按起止日期,翻页自动探测
        date_from = parse_date(data.get("date_from") or "")
        date_to = parse_date(data.get("date_to") or "")
        pages = 0  # 强制自动探测
    elif mode == "pages":
        # 指定页面:忽略所有日期,直接翻 N 页
        date_from = None
        date_to = None
        # pages 用前端传入
    else:
        # 单天(或默认):用上方 sel-date
        mode = "single"
        date_from = parse_date(data.get("date") or "")
        date_to = date_from
        pages = 0  # 自动探测

    task_id = uuid.uuid4().hex
    with TASKS_LOCK:
        TASKS[task_id] = {
            "id": task_id,
            "status": "pending",
            "logs": [],
            "rows": [],
            "txt": "",
            "progress": 0.0,
            "filename": build_txt_filename(date_from, date_to).replace(".txt", ""),
        }

    if data.get("async", False):
        threading.Thread(target=run_task, args=(
            task_id, pages, date_from, date_to, delay, limit), daemon=True).start()
        return jsonify({"task_id": task_id, "async": True})

    run_task(task_id, pages, date_from, date_to, delay, limit)
    with TASKS_LOCK:
        info = dict(TASKS[task_id])
    return jsonify(info)


@app.route("/api/task/<task_id>")
def api_task(task_id):
    with TASKS_LOCK:
        info = TASKS.get(task_id)
        if not info:
            return jsonify({"error": "task not found"}), 404
        return jsonify({k: v for k, v in info.items()})


@app.route("/api/stop/<task_id>", methods=["POST"])
def api_stop(task_id):
    """设置停止标志,后台任务会尽快中断并返回已抓到的部分数据"""
    evt = STOP_FLAGS.get(task_id)
    if not evt:
        return jsonify({"error": "task not running", "task_id": task_id}), 404
    evt.set()
    return jsonify({"ok": True, "task_id": task_id, "stopped": True})


@app.route("/api/download/<task_id>")
def api_download(task_id):
    fmt = request.args.get("format", "txt")
    with TASKS_LOCK:
        info = TASKS.get(task_id)
        if not info:
            return ("task not found", 404)
        if info.get("status") not in ("done", "stopped"):
            return ("task not done", 400)
        rows = info.get("rows", [])
        txt = info.get("txt", "")
        base_name = info.get("filename", "acgyx_posts")

    if fmt == "txt":
        return app.response_class(
            txt, mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition":
                     f"attachment; filename={base_name}.txt"})
    if fmt == "json":
        return app.response_class(
            json.dumps(rows, ensure_ascii=False, indent=2),
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition":
                     f"attachment; filename={base_name}.json"})
    return ("unsupported format", 400)


def find_free_port(host: str, start: int, count: int = 20) -> int:
    """从 start 开始,顺延 count 个端口,找到第一个可 bind 的就返回。
    不用 SO_REUSEADDR,否则别人 LISTEN 中的端口会被误判为可用。
    """
    for p in range(start, start + count):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, p))
            s.close()
            return p
        except OSError:
            try:
                s.close()
            except OSError:
                pass
            continue
    raise RuntimeError(
        f"端口 {start}~{start + count - 1} 全部被占用,"
        f"请关闭占用的程序或设置 PORT 环境变量指定其他起始端口"
    )


if __name__ == "__main__":
    host = "127.0.0.1"
    start = int(os.environ.get("PORT", 5000))
    try:
        port = find_free_port(host, start, 20)
    except RuntimeError as e:
        print(f"[失败] {e}")
        sys.exit(1)
    if port != start:
        print(f"[提示] 端口 {start} 被占用,自动改用 {port}")
    url = f"http://{host}:{port}/"
    print(f"[启动] ACG游戏姬工具已启动: {url}")

    # 启动后 1.5s 自动打开默认浏览器(避免双击 bat 后用户找不到入口)
    def _auto_open():
        time.sleep(1.5)
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[提示] 自动打开浏览器失败: {e}  请手动访问 {url}")
    threading.Thread(target=_auto_open, daemon=True).start()

    app.run(host=host, port=port, debug=False, threaded=True)
