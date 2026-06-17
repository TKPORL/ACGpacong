# -*- coding: utf-8 -*-
"""
scraper.py - 命令行入口

用途:
  1) 本地或 GitHub Actions 定时跑,把抓取结果写成 JSON
  2) 输出的 JSON 给 acgyx.html 静态加载用

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
)


def make_session():
    import requests
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def scrape(pages: int, limit: int, delay: float):
    """抓首页 + N 页,抓详情,返回 dict(含 items / latest_date 等)"""
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
    parser.add_argument("--pages", type=int, default=3, help="抓取页数(0=自动探测)")
    parser.add_argument("--limit", type=int, default=0, help="最多抓多少条详情(0=不限)")
    parser.add_argument("--delay", type=float, default=0.6, help="请求间隔(秒)")
    parser.add_argument("--out", default="../data/acgyx_latest.json", help="输出 JSON 路径")
    args = parser.parse_args()

    print(f"[scraper] start pages={args.pages} limit={args.limit} delay={args.delay}", flush=True)
    data = scrape(args.pages, args.limit, args.delay)

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[scraper] wrote {out_path}  ({data['total']} items, latest={data['latest_date']})", flush=True)


if __name__ == "__main__":
    main()
