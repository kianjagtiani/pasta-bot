import recon

def test_extract_asset_urls():
    html = '<script src="/app.js"></script><link href="https://cdn.x.com/s.css" rel="stylesheet">'
    urls = recon.extract_asset_urls(html, "https://www.pastapass.com/")
    assert "https://www.pastapass.com/app.js" in urls
    assert "https://cdn.x.com/s.css" in urls

def test_scan_threats():
    assert recon.scan_threats("loading queue-it and reCAPTCHA v3") == ["captcha", "queue-it", "recaptcha"]
    assert recon.scan_threats("plain pasta page") == []

def test_diff_text():
    assert recon.diff_text("a\nb\n", "a\nc\n", "page.html")
    assert recon.diff_text("same\n", "same\n", "page.html") == ""
