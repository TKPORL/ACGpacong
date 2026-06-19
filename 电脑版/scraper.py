# -*- coding: utf-8 -*-
"""
scraper.py - 命令行入口

用途:
  1) 本地或 GitHub Actions 定时跑,把抓取结果写成 JSON
  2) 输出的 JSON 给 index.html 静态加载用

用法:
  python scraper.py --pages 3 --delay 0.8 --out ../data/acgyx_latest.json
  python scraper.py --pages 1 --limit 30 --out ./out.json
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# 允许从同目录导入 acgyx_scraper
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from acgyx_scraper import (  # noqa: E402
    DEFAULT_HEADERS,
    EXCLUDED_CATEGORIES,
    collect_posts,
    fetch_post_detail,
    filter_posts,
    get_total_pages,
    resolve_base_url,
)


def make_session():
    import requests
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def scrape(pages: int, limit: int, delay: float):
    """抓首页 + N 页,抓详情,返回 dict(含 items / latest_date 等)"""
    # 先探测可用域名
    resolve_base_url()
    session = make_session()
    if pages <= 0:
        total = get_total_pages(session)
        pages = min(total, 20)
        print(f"[scraper] 自动探测总页数: {total},本次抓前 {pages} 页", flush=True)

    print(f"[scraper] 抓取列表 ({pages} 页)...", flush=True)
    posts = collect_posts(pages, session, delay, EXCLUDED_CATEGORIES.copy())
    posts = filter_posts(posts, EXCLUDED_CATEGORIES.copy(), None, None)
    print(f"[scraper] 列表共 {len(posts)} 条", flush=True)

    if limit > 0:
        posts = posts[:limit]

    items = []
    latest_date = ""
    latest_title = ""
    for i, p in enumerate(posts, 1):
        try:
            row = fetch_post_detail(p, session)
        except Exception as e:
            print(f"  [{i}/{len(posts)}] 详情失败: {e}", file=sys.stderr, flush=True)
            row = {
                "title": p.get("title", ""),
                "raw_title": p.get("title", ""),
                "category": p.get("category", ""),
                "pub_time": p.get("pub_time", ""),
                "url": p.get("url", ""),
                "yun_links": [],
                "baidu_links": [],
                "baidu_codes": [],
                "cheat_code": "",
                "unzip_code": "",
            }
        items.append(row)
        pt = row.get("pub_time", "")
        if pt and (not latest_date or pt > latest_date):
            latest_date = pt
            latest_title = row.get("title", "")
        if i % 5 == 0 or i == len(posts):
            print(f"  [{i}/{len(posts)}] {row.get('title', '')[:40]}", flush=True)
        if i < len(posts):
            time.sleep(delay)

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "total": len(items),
        "latest_date": latest_date,
        "latest_title": latest_title,
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(description="ACG游戏姬抓取 → JSON")
    parser.add_argument("--pages", type=int, default=8, help="抓取页数(0=自动探测)")
    parser.add_argument("--limit", type=int, default=0, help="最多抓多少条详情(0=不限)")
    parser.add_argument("--delay", type=float, default=0.6, help="请求间隔(秒)")
    parser.add_argument("--out", default="../data/acgyx_latest.json", help="输出 JSON 路径")
    parser.add_argument("--data-dir", default=None, help="按日期分文件存储的目录(默认同 out 的父目录)")
    args = parser.parse_args()

    print(f"[scraper] start pages={args.pages} limit={args.limit} delay={args.delay}", flush=True)
    data = scrape(args.pages, args.limit, args.delay)

    out_path = os.path.abspath(args.out)
    data_dir = os.path.abspath(args.data_dir) if args.data_dir else os.path.dirname(out_path)
    data_dir_name = os.path.basename(data_dir)

    # 如果本次抓到 0 条，保留上次有效数据（防止空数据覆盖）
    if data["total"] == 0:
        print(f"[scraper] 本次抓取 0 条，保留旧数据 ...", flush=True)
        if os.path.exists(out_path):
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    old = json.load(f)
                if old.get("total", 0) > 0:
                    old["generated_at"] = data["generated_at"]
                    old["_note"] = f"本次抓取失败(0条)，保留旧数据(共{old['total']}条)"
                    data = old
                    print(f"[scraper] 已保留旧数据: {old['total']} 条", flush=True)
                else:
                    print(f"[scraper] 旧数据也是 0 条，不覆盖", flush=True)
                    return
            except Exception as e:
                print(f"[scraper] 读取旧数据失败: {e}，跳过写入", flush=True)
                return
        else:
            print(f"[scraper] 无旧数据文件，跳过写入", flush=True)
            return

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    # 1) 写 acgyx_latest.json(主输出,兼容旧版前端)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[scraper] wrote {out_path}  ({data['total']} items, latest={data['latest_date']})", flush=True)

    # 2) 按 pub_time 分日期写 data/YYYY-MM-DD.json(永久保留,旧文件追加新数据)
    by_date = {}
    for item in data["items"]:
        pt = item.get("pub_time", "")
        if not pt:
            continue
        date = pt[:10]  # 2026-06-19
        by_date.setdefault(date, []).append(item)

    manifest = []
    for date, new_items in by_date.items():
        day_path = os.path.join(data_dir, f"{date}.json")
        old_items = []
        if os.path.exists(day_path):
            try:
                with open(day_path, "r", encoding="utf-8") as f:
                    old = json.load(f)
                    old_items = old.get("items", [])
            except Exception as e:
                print(f"  [by-date] 读取 {date} 旧数据失败: {e}", flush=True)

        # 按 url 去重合并
        seen = {}
        for it in old_items:
            u = it.get("url", "")
            if u:
                seen[u] = it
        added = 0
        for it in new_items:
            u = it.get("url", "")
            if u and u not in seen:
                added += 1
            if u:
                seen[u] = it
        merged = list(seen.values())

        day_data = {
            "generated_at": data["generated_at"],
            "total": len(merged),
            "date": date,
            "items": merged,
        }
        with open(day_path, "w", encoding="utf-8") as f:
            json.dump(day_data, f, ensure_ascii=False, indent=2)
        print(f"  [by-date] {date}.json: {len(merged)} 条 (本次新增 {added})", flush=True)

        if date not in manifest:
            manifest.append(date)

    # 3) 写 manifest.json(日期索引,前端按日期 tab 切换用)
    manifest_path = os.path.join(data_dir, "manifest.json")
    old_manifest = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                old_manifest = json.load(f)
        except Exception:
            old_manifest = []
    # 合并 + 去重 + 倒序
    for d in old_manifest:
        if d not in manifest:
            manifest.append(d)
    manifest.sort(reverse=True)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[scraper] wrote {manifest_path}  ({len(manifest)} dates)", flush=True)


if __name__ == "__main__":
    main()
