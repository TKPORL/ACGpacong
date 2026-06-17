# -*- coding: utf-8 -*-
"""第 3 遍:兼容性测试 - 多浏览器 + 多分辨率 + 长时间稳定性"""
import os
import time
import threading
import http.server
import socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 8767

def start_server(directory):
    os.chdir(directory)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.serve_forever()

def test_browser(browser_type, label, viewports, supports_mobile=True):
    """测一个浏览器,多种 viewport。supports_mobile=False 时忽略 is_mobile 标记"""
    base = r"d:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具\单html版本"
    fails = []
    print(f"\n========== {label} ==========")
    browser = browser_type.launch()
    for w, h, dev in viewports:
        ctx_args = {"viewport": {"width": w, "height": h}}
        if dev and supports_mobile:
            ctx_args.update(dev)
        elif dev and not supports_mobile:
            # firefox 不用 is_mobile 标记,直接小 viewport
            ctx_args = {"viewport": {"width": w, "height": h}}
        ctx = browser.new_context(**ctx_args)
        page = ctx.new_page()
        js_errs = []
        page.on("pageerror", lambda e: js_errs.append(str(e)))
        page.on("console", lambda m: js_errs.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)

        URL = f"http://127.0.0.1:{PORT}/acgyx.html"
        t0 = time.time()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_function("typeof CLOUD_DATA !== 'undefined' && CLOUD_DATA !== null", timeout=15000)
        page.wait_for_timeout(300)
        load_ms = int((time.time() - t0) * 1000)

        # 核心断言
        n = page.evaluate("CLOUD_ITEMS.length")
        items_label = f"{label} {w}x{h}{' (mobile)' if dev else ''}"
        print(f"  [{items_label}] 加载 {load_ms}ms, items={n}")
        if n != 50:
            fails.append(f"{items_label}: items 错 {n}")

        # 测一下切模式不崩
        for mode in ["single", "range", "pages", "all"]:
            page.evaluate(f"switchView('{mode}')")
            page.wait_for_timeout(50)
        rows = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        if rows != 50:
            fails.append(f"{items_label}: 切模式后行数错 {rows}")

        # 移动端额外测一下:汉堡菜单/横向滚动
        if dev:
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            print(f"    横向溢出: {overflow}")
            # 不算 fail,只是提示

        # 截图
        fname = f"_shot_{label}_{w}x{h}.png".replace(" ", "_")
        Path(os.path.join(base, fname)).write_bytes(page.screenshot(full_page=True))
        print(f"    截图: {fname}")

        if js_errs:
            for e in js_errs: print(f"    JS-ERR: {e}")
            for e in js_errs:
                if "PAGEERROR" in str(e) or "console.error" in str(e):
                    fails.append(f"{items_label}: JS 错 {e}")

        ctx.close()
    browser.close()
    return fails

def test_refresh_robust(p, ctx):
    """反复刷新页面测试稳定性 - 共用外层 sync_playwright"""
    print("\n========== 反复刷新稳定性 ==========")
    fails = []
    page = ctx.new_page()
    for i in range(5):
        page.goto(f"http://127.0.0.1:{PORT}/acgyx.html?t={i}", wait_until="networkidle")
        page.wait_for_function("typeof CLOUD_DATA !== 'undefined' && CLOUD_DATA !== null", timeout=10000)
        n = page.evaluate("CLOUD_ITEMS.length")
        print(f"  刷新 #{i+1}: items={n}")
        if n != 50: fails.append(f"刷新 {i+1} items 错:{n}")
    page.close()
    return fails

def main():
    base = r"d:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具\单html版本"
    t = threading.Thread(target=start_server, args=(base,), daemon=True)
    t.start()
    time.sleep(0.5)

    all_fails = []

    # 安装浏览器驱动检查
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # 桌面尺寸
        desktop_viewports = [
            (1920, 1080, None),  # FullHD
            (1280, 800, None),
            (1024, 768, None),
        ]
        # 移动端尺寸
        mobile_viewports = [
            (390, 800, {"device_scale_factor": 2, "is_mobile": True, "has_touch": True}),  # iPhone 14
            (414, 896, {"device_scale_factor": 3, "is_mobile": True, "has_touch": True}),  # iPhone Plus
            (360, 780, {"device_scale_factor": 3, "is_mobile": True, "has_touch": True}),  # 安卓中端
            (768, 1024, {"device_scale_factor": 2, "is_mobile": True, "has_touch": True}), # iPad mini
        ]

        # Chromium (覆盖 Chrome / Edge)
        all_fails += test_browser(p.chromium, "chromium", desktop_viewports + mobile_viewports)

        # Firefox 不支持 is_mobile
        all_fails += test_browser(p.firefox, "firefox", desktop_viewports[:1] + mobile_viewports[:1], supports_mobile=False)

        # 稳定性 - 共用外层 p,新开 ctx
        stable_browser = p.chromium.launch()
        stable_ctx = stable_browser.new_context(viewport={"width": 390, "height": 800}, is_mobile=True, has_touch=True)
        all_fails += test_refresh_robust(p, stable_ctx)
        stable_ctx.close()
        stable_browser.close()

    print("\n========== 兼容测试结果 ==========")
    if all_fails:
        print(f"❌ {len(all_fails)} 项失败:")
        for f in all_fails: print(f"  - {f}")
        return 1
    else:
        print("✅ 全部通过!")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
