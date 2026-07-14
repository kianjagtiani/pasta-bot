import threading

from playwright.sync_api import sync_playwright

from mock.server import serve


def test_detector_clicks_buy_now_on_flip():
    srv = serve(8198, flip_in=1.5)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto("http://127.0.0.1:8198/")
            page.evaluate(open("detector.js").read())
            page.wait_for_url("**/checkout", timeout=8000)
            # detection flag must survive the click's navigation
            assert page.evaluate("Number(sessionStorage.getItem('__pp_found'))") > 0
            browser.close()
    finally:
        srv.shutdown()
