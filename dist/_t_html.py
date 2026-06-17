# -*- coding: utf-8 -*-
"""Playwright 测试 index.html(改造后)"""
import sys
import json
import threading
import http.server
import socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 8765

def start_server():
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.serve_forever()

def main():
    import os
    os.chdir(r"d:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具\单html版本")
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    import time; time.sleep(0.5)

    URL = f"http://127.0.0.1:{PORT}/index.html"
    with sync_playwright() as p:
        # 1) 桌面
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR: {e}"))
        page.on("console", lambda msg: errs.append(f"CONSOLE.{msg.type}: {msg.text}") if msg.type == "error" else None)

        page.goto(URL, wait_until="networkidle")
        page.wait_for_function("typeof CLOUD_DATA !== 'undefined' && CLOUD_DATA !== null", timeout=10000)
        page.wait_for_timeout(300)

        n = page.evaluate("CLOUD_ITEMS.length")
        lb = page.evaluate("document.getElementById('latest-bar').classList.contains('hidden') ? 'hidden' : 'visible'")
        latest = page.evaluate("CLOUD_DATA.latest_date + ' | ' + CLOUD_DATA.latest_title")
        st = page.evaluate("document.getElementById('cloud-status').textContent")
        print(f"[桌面] items={n} latestBar={lb}")
        print(f"[桌面] latest={latest}")
        print(f"[桌面] status={st}")

        # 切换 single
        page.evaluate("switchView('single')")
        page.wait_for_timeout(100)
        single_cnt = page.evaluate("document.getElementById('cnt-single').textContent")
        print(f"[桌面] single 模式命中={single_cnt}")

        # 切换 range
        page.evaluate("switchView('range')")
        page.wait_for_timeout(100)
        range_cnt = page.evaluate("document.getElementById('cnt-range').textContent")
        print(f"[桌面] range 模式命中={range_cnt}")

        # 切换 pages
        page.evaluate("switchView('pages')")
        page.wait_for_timeout(100)
        pg_info = page.evaluate("document.getElementById('pg-info').textContent")
        print(f"[桌面] pages 模式={pg_info}")

        # 截一张图
        Path(r"d:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具\单html版本\_test_shot_desktop.png").write_bytes(
            page.screenshot(full_page=True)
        )
        print("[桌面] 已截图 _test_shot_desktop.png")

        # 2) 手机
        ctx2 = browser.new_context(viewport={"width": 390, "height": 800}, device_scale_factor=2)
        page2 = ctx2.new_page()
        page2.goto(URL, wait_until="networkidle")
        page2.wait_for_function("typeof CLOUD_DATA !== 'undefined' && CLOUD_DATA !== null", timeout=10000)
        page2.wait_for_timeout(300)
        n2 = page2.evaluate("CLOUD_ITEMS.length")
        print(f"[手机] items={n2}")
        Path(r"d:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具\单html版本\_test_shot_mobile.png").write_bytes(
            page2.screenshot(full_page=True)
        )
        print("[手机] 已截图 _test_shot_mobile.png")

        if errs:
            print("---ERRORS---")
            for e in errs: print(e)
        else:
            print("---无错误---")

        browser.close()

if __name__ == "__main__":
    main()
