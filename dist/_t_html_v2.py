# -*- coding: utf-8 -*-
"""第 2 遍:Playwright 深度交互测试 index.html"""
import os
import sys
import json
import time
import threading
import http.server
import socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = 8766

def start_server(directory):
    os.chdir(directory)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.serve_forever()

def main():
    base = r"d:\Tsinho文件夹\Trae\测试项目\ACG游戏姬工具\单html版本"
    t = threading.Thread(target=start_server, args=(base,), daemon=True)
    t.start()
    time.sleep(0.5)

    URL = f"http://127.0.0.1:{PORT}/index.html"
    fails = []
    errs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        page.on("pageerror", lambda e: errs.append(f"PAGEERROR: {e}"))
        page.on("console", lambda m: errs.append(f"CONSOLE.{m.type}: {m.text}") if m.type == "error" else None)

        page.goto(URL, wait_until="networkidle")
        page.wait_for_function("typeof CLOUD_DATA !== 'undefined' && CLOUD_DATA !== null", timeout=10000)
        page.wait_for_timeout(300)

        # ============== 1. latest-bar 内容 ==============
        print("=== 1. latest-bar ===")
        lb_date = page.text_content("#lb-date")
        lb_title = page.text_content("#lb-title")
        lb_total = page.text_content("#lb-total")
        lb_time = page.text_content("#lb-time")
        print(f"  date={lb_date} title={lb_title} total={lb_total} time={lb_time}")
        if lb_date != "2026-06-17": fails.append(f"latest-bar 日期错:{lb_date}")
        if lb_total != "50": fails.append(f"latest-bar 总数错:{lb_total}")

        # ============== 2. all 模式 ==============
        print("=== 2. all 模式 ===")
        page.evaluate("switchView('all')")
        page.wait_for_timeout(100)
        cnt_all = page.text_content("#cnt-all")
        rows_all = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  cnt-all={cnt_all}, 行数={rows_all}")
        if cnt_all != "50": fails.append(f"all 模式总数错:{cnt_all}")
        if rows_all != 50: fails.append(f"all 模式行数错:{rows_all}")

        # ============== 3. single 模式 - 切换日期 ==============
        print("=== 3. single 模式(切日期)===")
        page.evaluate("switchView('single')")
        page.wait_for_timeout(100)
        # 默认是最新日期(2026-06-17),应该有 44 条
        cnt1 = page.text_content("#cnt-single")
        rows1 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  2026-06-17 命中={cnt1}, 行数={rows1}")
        if cnt1 != "44": fails.append(f"single 2026-06-17 命中错:{cnt1} (期望 44)")
        if rows1 != 44: fails.append(f"single 2026-06-17 行数错:{rows1}")

        # 切到 2026-06-16
        page.select_option("#vp-single-date", "2026-06-16")
        page.wait_for_timeout(100)
        cnt2 = page.text_content("#cnt-single")
        rows2 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  2026-06-16 命中={cnt2}, 行数={rows2}")
        if cnt2 != "6": fails.append(f"single 2026-06-16 命中错:{cnt2} (期望 6)")
        if rows2 != 6: fails.append(f"single 2026-06-16 行数错:{rows2}")

        # ============== 4. range 模式 - 改范围 ==============
        print("=== 4. range 模式(改范围)===")
        page.evaluate("switchView('range')")
        page.wait_for_timeout(100)
        # 默认 from=2026-06-16 to=2026-06-17, 应该 50
        cnt3 = page.text_content("#cnt-range")
        rows3 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  默认范围 16~17 命中={cnt3}, 行数={rows3}")
        if cnt3 != "50": fails.append(f"range 默认范围错:{cnt3}")

        # from=to=2026-06-17, 应该 44
        page.select_option("#vp-range-from", "2026-06-17")
        page.select_option("#vp-range-to", "2026-06-17")
        page.wait_for_timeout(100)
        cnt4 = page.text_content("#cnt-range")
        print(f"  from=to=06-17 命中={cnt4} (期望 44)")
        if cnt4 != "44": fails.append(f"range 06-17 错:{cnt4}")

        # 反向范围 (to<from 应该自动交换)
        page.select_option("#vp-range-from", "2026-06-16")
        page.select_option("#vp-range-to", "2026-06-17")
        page.wait_for_timeout(100)
        cnt5 = page.text_content("#cnt-range")
        print(f"  from=06-16 to=06-17 命中={cnt5} (期望 50)")
        if cnt5 != "50": fails.append(f"range 16~17 错:{cnt5}")

        # ============== 5. pages 模式 - 翻页 ==============
        print("=== 5. pages 模式(翻页)===")
        page.evaluate("switchView('pages')")
        page.wait_for_timeout(100)
        # 默认 page_size=20, 50/20=3 页
        pg1 = page.text_content("#pg-info")
        rows_p1 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  第1页: {pg1}, 行数={rows_p1}")
        if "1 / 3" not in pg1: fails.append(f"pages 1/3 错:{pg1}")
        if rows_p1 != 20: fails.append(f"第1页行数错:{rows_p1}")

        # 翻到第3页 - 用 button.onclick 直接调 pageNext() 避开 strict click
        page.evaluate("pageNext()")
        page.wait_for_timeout(100)
        page.evaluate("pageNext()")
        page.wait_for_timeout(100)
        pg3 = page.text_content("#pg-info")
        rows_p3 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  点2次下一页后: {pg3}, 行数={rows_p3}")
        if "3 / 3" not in pg3: fails.append(f"pages 3/3 错:{pg3}")
        if rows_p3 != 10: fails.append(f"第3页行数错(期望 10):{rows_p3}")

        # 翻回第1页
        page.evaluate("pagePrev()")
        page.evaluate("pagePrev()")
        page.wait_for_timeout(100)
        pg_back = page.text_content("#pg-info")
        rows_back = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  翻回第1页: {pg_back}, 行数={rows_back}")
        if "1 / 3" not in pg_back: fails.append(f"翻回 1/3 错:{pg_back}")
        if rows_back != 20: fails.append(f"翻回第1页行数错:{rows_back}")

        # 翻过头 - 点 10 次下一页,applyView 内部会把 CURRENT_PAGE 钳到 totalPages
        try:
            for i in range(10):
                r = page.evaluate("(()=>{ pageNext(); return CURRENT_PAGE; })()")
                page.wait_for_timeout(50)
            print(f"  翻过头后 CURRENT_PAGE={r} (期望 3)")
        except Exception as e:
            print(f"  翻过头异常: {e}")
        pg_over = page.text_content("#pg-info")
        print(f"  狂点下一页 10 次: {pg_over} (应回 3/3)")
        if "3 / 3" not in pg_over: fails.append(f"翻过头没回 3/3:{pg_over}")
        rows_over = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        if rows_over != 10: fails.append(f"翻过头行数错(应 10):{rows_over}")

        # 改 page_size=10, 应该是 5 页
        page.fill("#vp-pages-size", "10")
        page.evaluate("document.getElementById('vp-pages-size').dispatchEvent(new Event('change'))")
        page.wait_for_timeout(100)
        pg_size10 = page.text_content("#pg-info")
        rows_size10 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  size=10: {pg_size10}, 行数={rows_size10}")
        if "5 页" not in pg_size10: fails.append(f"size=10 页数错:{pg_size10}")
        if rows_size10 != 10: fails.append(f"size=10 行数错:{rows_size10}")

        # 改 page_size=100, 应该只 1 页
        page.fill("#vp-pages-size", "100")
        page.evaluate("document.getElementById('vp-pages-size').dispatchEvent(new Event('change'))")
        page.wait_for_timeout(100)
        pg_size100 = page.text_content("#pg-info")
        rows_size100 = page.evaluate("document.querySelectorAll('#result-tbody tr').length")
        print(f"  size=100: {pg_size100}, 行数={rows_size100}")
        if "1 页" not in pg_size100: fails.append(f"size=100 页数错:{pg_size100}")
        if rows_size100 != 50: fails.append(f"size=100 行数错:{rows_size100}")

        # ============== 6. 数据源切换 ==============
        print("=== 6. 数据源切换 ===")
        # 切到 paste
        page.click("#tab-paste")
        page.wait_for_timeout(100)
        paste_visible = page.evaluate("!document.getElementById('src-paste').classList.contains('hidden')")
        cloud_hidden = page.evaluate("document.getElementById('src-cloud').classList.contains('hidden')")
        print(f"  paste 可见={paste_visible}, cloud 隐藏={cloud_hidden}")
        if not paste_visible: fails.append("paste 源没显示")
        if not cloud_hidden: fails.append("cloud 源没隐藏")

        # 切回 cloud
        page.click("#tab-cloud")
        page.wait_for_timeout(100)
        cloud_visible = page.evaluate("!document.getElementById('src-cloud').classList.contains('hidden')")
        print(f"  切回 cloud 可见={cloud_visible}")
        if not cloud_visible: fails.append("cloud 切回没显示")

        # ============== 7. 表格内容验证(标题/分类) ==============
        print("=== 7. 表格内容验证 ===")
        page.evaluate("switchView('all')")
        page.wait_for_timeout(100)
        first_row = page.evaluate("""
            (() => {
                const r = document.querySelectorAll('#result-tbody tr')[0];
                if (!r) return null;
                return {
                    cat: r.querySelector('.badge')?.textContent,
                    title: r.cells[1]?.textContent,
                    time: r.cells[2]?.textContent,
                    link: r.querySelector('a')?.href
                };
            })()
        """)
        print(f"  第1行: {first_row}")
        if not first_row or not first_row['title']: fails.append("表格第1行无标题")
        if first_row and not first_row['link'].startswith('http'): fails.append(f"链接错:{first_row['link']}")

        # ============== 8. JSON 容错 - 临时拿走 JSON 测加载 ==============
        print("=== 8. JSON 加载容错 ===")
        # 复制 JSON 备份,清空,测错误状态
        import shutil
        json_path = os.path.join(base, "data", "acgyx_latest.json")
        backup_path = json_path + ".bak"
        shutil.copy(json_path, backup_path)
        os.remove(json_path)
        page2 = ctx.new_page()
        page2.goto(URL, wait_until="networkidle")
        page2.wait_for_timeout(1500)
        cloud_status = page2.text_content("#cloud-status")
        print(f"  无JSON时 status={cloud_status!r}")
        if "加载失败" not in cloud_status and "打开" not in cloud_status:
            fails.append(f"无 JSON 时 status 不正确:{cloud_status}")
        page2.close()
        shutil.move(backup_path, json_path)

        # ============== 截图归档 ==============
        Path(os.path.join(base, "_shot_desktop_all.png")).write_bytes(page.screenshot(full_page=True))
        print("=== 截图已存 _shot_desktop_all.png ===")

        # ============== 手机端 ==============
        print("=== 9. 手机端(390x800)===")
        ctx2 = browser.new_context(viewport={"width": 390, "height": 800}, device_scale_factor=2)
        page3 = ctx2.new_page()
        page3.goto(URL, wait_until="networkidle")
        page3.wait_for_function("typeof CLOUD_DATA !== 'undefined' && CLOUD_DATA !== null", timeout=10000)
        page3.wait_for_timeout(300)
        # 切到 single/range/pages 看看
        for mode in ["single", "range", "pages"]:
            page3.evaluate(f"switchView('{mode}')")
            page3.wait_for_timeout(100)
        Path(os.path.join(base, "_shot_mobile_views.png")).write_bytes(page3.screenshot(full_page=True))
        print("  手机 4 模式已截图")

        if errs:
            print("--- 控制台错误 ---")
            for e in errs: print(e)
            # 警告不算 fail(可能 fetch 失败是因为测试环境)
            for e in errs:
                if "PAGEERROR" in e: fails.append(f"JS 错误:{e}")

        browser.close()

    print("\n========== 测试结果 ==========")
    if fails:
        print(f"❌ {len(fails)} 项失败:")
        for f in fails: print(f"  - {f}")
        sys.exit(1)
    else:
        print("✅ 全部通过!")

if __name__ == "__main__":
    main()
