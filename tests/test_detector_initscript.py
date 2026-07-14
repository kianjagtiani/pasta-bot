import threading

from playwright.sync_api import sync_playwright

from mock.server import serve


def test_detector_works_as_init_script():
    # Regression: injected at document creation (documentElement not yet present),
    # the detector must still arm and catch a later flip.
    srv = serve(8197, flip_in=1.5)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.add_init_script(open("detector.js").read())
            page.goto("http://127.0.0.1:8197/")
            page.evaluate(open("detector.js").read())  # buybot arms both ways
            page.wait_for_url("**/checkout", timeout=8000)
            assert page.evaluate("Number(sessionStorage.getItem('__pp_found'))") > 0
            browser.close()
    finally:
        srv.shutdown()
