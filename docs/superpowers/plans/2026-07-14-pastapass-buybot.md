# PastaPass Buy-Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the hybrid buy-bot from `docs/superpowers/specs/2026-07-14-pastapass-buybot-design.md`: detect and click PastaPass.com's "Buy Now" the instant it appears on 2026-07-16 14:00 ET, alert two phones on a countdown schedule, auto-fill non-payment checkout fields, and halt for the human to enter card details and submit.

**Architecture:** Small flat Python modules with pure, unit-tested logic (`timesync.py`, `alerts.py`, `formfill.py`, recon helpers) wired together by an orchestrator (`buybot.py`) driving a headed Playwright Chromium with an injected MutationObserver (`detector.js`). A local mock site (`mock/`) rehearses the full flow. `recon.py` snapshots the live site until the drop.

**Tech Stack:** Python 3.11+, Playwright (sync API), pytest, macOS `osascript` (iMessage + volume) and `afplay` (alarm). No other dependencies.

## Global Constraints

- Never store, log, or fill payment card fields — classify them and only highlight them (spec: "Card details are never stored in any file, config, or log").
- The bot must never auto-submit an order; it stops after filling non-payment fields.
- Alert failures must never crash or delay the buy path (send in a daemon thread, swallow exceptions).
- Drop time: `2026-07-16 14:00 America/New_York`. Two alert numbers from `config.json` key `alert_numbers`.
- Countdown alerts at T−30 min, T−15 min, T−5 min, T−1 min; drop alert on button detection; "no button yet" alert at T+5 s if not detected.
- `config.json` is gitignored; `config.example.json` is committed.
- Python venv at `.venv/`; run everything with `.venv/bin/python` / `.venv/bin/pytest`.

---

### Task 1: Scaffold + `timesync.py`

**Files:**
- Create: `requirements.txt`, `config.example.json`, `timesync.py`
- Modify: `.gitignore`
- Test: `tests/test_timesync.py`

**Interfaces:**
- Produces: `timesync.parse_server_epoch(date_header: str) -> float`; `timesync.fetch_offset(url: str, samples: int = 3) -> float` (median server−local clock offset, 0.0 on total failure); `timesync.corrected_now(offset: float) -> float`.

- [ ] **Step 1: Scaffold**

`requirements.txt`:
```
playwright==1.*
pytest==8.*
```

Append to `.gitignore`:
```
.venv/
__pycache__/
screenshots/
*.log
```

`config.example.json`:
```json
{
  "alert_numbers": ["+15551234567", "+15557654321"],
  "profile": {
    "first_name": "Kian",
    "last_name": "Jagtiani",
    "email": "kjagtian@usc.edu",
    "phone": "+15551234567",
    "address1": "123 Example St",
    "address2": "",
    "city": "Los Angeles",
    "state": "CA",
    "zip": "90007"
  }
}
```

Run:
```bash
python3 -m venv .venv && .venv/bin/pip -q install -r requirements.txt && .venv/bin/playwright install chromium
```

- [ ] **Step 2: Write failing tests**

`tests/test_timesync.py`:
```python
import timesync

def test_parse_server_epoch():
    # RFC 7231 Date header
    assert timesync.parse_server_epoch("Tue, 14 Jul 2026 12:00:00 GMT") == 1784030400.0

def test_corrected_now_applies_offset():
    import time
    off = 5.0
    assert abs(timesync.corrected_now(off) - (time.time() + 5.0)) < 0.5
```

- [ ] **Step 3: Run to verify failure**

Run: `.venv/bin/pytest tests/test_timesync.py -q` — Expected: FAIL (`ModuleNotFoundError: timesync`)

- [ ] **Step 4: Implement `timesync.py`**

```python
"""Clock offset vs the target site's server, from its HTTP Date header."""
import email.utils
import time
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def parse_server_epoch(date_header: str) -> float:
    return email.utils.parsedate_to_datetime(date_header).timestamp()


def corrected_now(offset: float) -> float:
    return time.time() + offset


def fetch_offset(url: str = "https://www.pastapass.com", samples: int = 3) -> float:
    offsets = []
    for _ in range(samples):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=5) as resp:
                t1 = time.time()
                date = resp.headers.get("Date")
            if date:
                offsets.append(parse_server_epoch(date) - (t0 + t1) / 2)
        except OSError:
            continue
    if not offsets:
        return 0.0
    offsets.sort()
    return offsets[len(offsets) // 2]
```

- [ ] **Step 5: Run tests, expect PASS**: `.venv/bin/pytest tests/test_timesync.py -q`

- [ ] **Step 6: Commit**: `git add -A && git commit -m "feat: scaffold + server clock sync"`

---

### Task 2: `alerts.py` — schedule + iMessage/alarm

**Files:**
- Create: `alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: `timesync.corrected_now(offset)`.
- Produces: `alerts.build_schedule(drop_epoch: float, now_epoch: float) -> list[tuple[float, str]]` (only future countdown alerts, ascending); `alerts.send_all(numbers: list[str], text: str) -> None` (never raises); `alerts.alarm() -> None` (non-blocking siren); `alerts.run_schedule(schedule, numbers, offset, stop_event) -> None` (blocking; run in a daemon thread).

- [ ] **Step 1: Write failing tests**

`tests/test_alerts.py`:
```python
import alerts

def test_build_schedule_full():
    sched = alerts.build_schedule(10000.0, 0.0)
    assert [t for t, _ in sched] == [10000.0 - 1800, 10000.0 - 900, 10000.0 - 300, 10000.0 - 60]
    assert "30 minutes" in sched[0][1] and "1 minute" in sched[-1][1]

def test_build_schedule_drops_past_alerts():
    sched = alerts.build_schedule(10000.0, 10000.0 - 200)  # inside T-5min
    assert [t for t, _ in sched] == [10000.0 - 60]

def test_imessage_cmd_escapes_quotes():
    cmd = alerts.imessage_cmd("+15551234567", 'say "hi"')
    assert cmd[0] == "osascript" and '\\"hi\\"' in cmd[-1]
```

- [ ] **Step 2: Run to verify failure**: `.venv/bin/pytest tests/test_alerts.py -q` — FAIL (no module)

- [ ] **Step 3: Implement `alerts.py`**

```python
"""iMessage countdown alerts + local alarm. Must never raise into the buy path."""
import logging
import subprocess
import threading

import timesync

log = logging.getLogger("alerts")

COUNTDOWN = [
    (1800, "🍝 Pasta Pass drop in 30 minutes (2:00 PM ET)"),
    (900, "🍝 15 minutes to Pasta Pass drop"),
    (300, "🍝 5 minutes — be at the laptop NOW"),
    (60, "🍝 1 MINUTE. Eyes on the browser."),
]

ALARM_SOUND = "/System/Library/Sounds/Sosumi.aiff"


def build_schedule(drop_epoch: float, now_epoch: float) -> list[tuple[float, str]]:
    return [(drop_epoch - s, msg) for s, msg in COUNTDOWN if drop_epoch - s > now_epoch]


def imessage_cmd(number: str, text: str) -> list[str]:
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    number = number.replace('"', "")
    script = (
        'tell application "Messages" to send '
        f'"{text}" to participant "{number}" of '
        "(1st account whose service type = iMessage)"
    )
    return ["osascript", "-e", script]


def send_all(numbers: list[str], text: str) -> None:
    for n in numbers:
        try:
            r = subprocess.run(imessage_cmd(n, text), capture_output=True, timeout=15)
            if r.returncode != 0:
                log.warning("iMessage to %s failed: %s", n, r.stderr.decode(errors="replace"))
        except Exception as e:  # alerts must never break the bot
            log.warning("iMessage to %s errored: %s", n, e)


def alarm(bursts: int = 6) -> None:
    def _run():
        try:
            subprocess.run(["osascript", "-e", "set volume output volume 90"], timeout=5)
            for _ in range(bursts):
                subprocess.run(["afplay", ALARM_SOUND], timeout=10)
        except Exception as e:
            log.warning("alarm failed: %s", e)

    threading.Thread(target=_run, daemon=True).start()


def run_schedule(schedule, numbers, offset, stop_event: threading.Event) -> None:
    for fire_at, msg in schedule:
        while not stop_event.is_set() and timesync.corrected_now(offset) < fire_at:
            stop_event.wait(min(1.0, max(0.05, fire_at - timesync.corrected_now(offset))))
        if stop_event.is_set():
            return
        log.info("alert: %s", msg)
        send_all(numbers, msg)
```

- [ ] **Step 4: Run tests, expect PASS**: `.venv/bin/pytest tests/test_alerts.py -q`

- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: alert schedule, iMessage, alarm"`

---

### Task 3: `recon.py` — snapshot/diff/threat-scan loop

**Files:**
- Create: `recon.py`
- Test: `tests/test_recon.py`

**Interfaces:**
- Produces (pure, for tests): `recon.extract_asset_urls(html: str, base_url: str) -> list[str]` (absolute .js/.css URLs); `recon.scan_threats(text: str) -> list[str]`; `recon.diff_text(old: str, new: str, name: str) -> str` (unified diff, "" if same). CLI: `recon.py [--url U] [--loop SECONDS] [--dir recon]` writes `recon/snapshots/<UTC-timestamp>/` and appends to `recon/changes.log`.

- [ ] **Step 1: Write failing tests**

`tests/test_recon.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**: `.venv/bin/pytest tests/test_recon.py -q` — FAIL

- [ ] **Step 3: Implement `recon.py`**

```python
"""Snapshot pastapass.com + assets, diff vs last snapshot, flag anti-bot tech."""
import argparse
import difflib
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from timesync import UA

THREATS = ["akamai", "captcha", "cloudflare", "datadome", "hcaptcha",
           "perimeterx", "queue-it", "queueit", "recaptcha", "turnstile"]
ASSET_RE = re.compile(r'(?:src|href)="([^"]+\.(?:js|css)(?:\?[^"]*)?)"')


def extract_asset_urls(html: str, base_url: str) -> list[str]:
    return [urllib.parse.urljoin(base_url, m) for m in ASSET_RE.findall(html)]


def scan_threats(text: str) -> list[str]:
    low = text.lower()
    return sorted({t for t in THREATS if t in low})


def diff_text(old: str, new: str, name: str) -> str:
    if old == new:
        return ""
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        f"prev/{name}", f"curr/{name}", n=2))


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def safe_name(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", url.split("://", 1)[-1])[:120] or "page"


def snapshot(url: str, root: Path) -> None:
    snaps = root / "snapshots"
    snaps.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cur = snaps / ts
    cur.mkdir()
    files = {}
    try:
        html = fetch(url)
    except OSError as e:
        _log(root, f"{ts} FETCH FAILED: {e}")
        return
    files["page.html"] = html
    for asset in extract_asset_urls(html, url):
        try:
            files[safe_name(asset)] = fetch(asset)
        except OSError as e:
            _log(root, f"{ts} asset failed {asset}: {e}")
    for name, text in files.items():
        (cur / name).write_text(text)

    threats = scan_threats("\n".join(files.values()))
    if threats:
        _log(root, f"{ts} ⚠️ ANTI-BOT KEYWORDS: {', '.join(threats)}")

    prev_dirs = sorted(d for d in snaps.iterdir() if d.is_dir() and d.name < ts)
    if prev_dirs:
        prev = prev_dirs[-1]
        changed = False
        for name, text in files.items():
            old_f = prev / name
            d = diff_text(old_f.read_text() if old_f.exists() else "", text, name)
            if d:
                changed = True
                _log(root, f"{ts} CHANGED {name}:\n{d}")
        if not changed:
            _log(root, f"{ts} no changes")
    else:
        _log(root, f"{ts} first snapshot ({len(files)} files)")


def _log(root: Path, line: str) -> None:
    print(line)
    with open(root / "changes.log", "a") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://www.pastapass.com")
    ap.add_argument("--dir", default="recon")
    ap.add_argument("--loop", type=int, default=0, help="seconds between snapshots; 0 = once")
    a = ap.parse_args()
    while True:
        snapshot(a.url, Path(a.dir))
        if not a.loop:
            break
        time.sleep(a.loop)
```

- [ ] **Step 4: Run tests, expect PASS**: `.venv/bin/pytest tests/test_recon.py -q`

- [ ] **Step 5: Smoke-run against live site**: `.venv/bin/python recon.py` — Expected: prints `... first snapshot (N files)`; `recon/changes.log` exists.

- [ ] **Step 6: Commit** (snapshots are gitignored): `git add -A && git commit -m "feat: recon snapshot/diff/threat-scan"`

---

### Task 4: `formfill.py` — checkout field classifier

**Files:**
- Create: `formfill.py`
- Test: `tests/test_formfill.py`

**Interfaces:**
- Produces: `formfill.classify(desc: dict) -> str | None` — desc has keys `name,id,autocomplete,placeholder,label`; returns a profile key (`first_name,last_name,email,phone,address1,address2,city,state,zip`), the sentinel `"PAYMENT"`, or None. `formfill.GATHER_JS: str` — JS returning the descriptor list (with index `i`) for all visible inputs/selects.

- [ ] **Step 1: Write failing tests**

`tests/test_formfill.py`:
```python
import formfill

def d(**kw):
    base = {"name": "", "id": "", "autocomplete": "", "placeholder": "", "label": ""}
    return base | kw

def test_payment_fields_flagged_never_mapped():
    for f in (d(autocomplete="cc-number"), d(name="cardNumber"), d(label="CVV"),
              d(placeholder="MM/YY expiration"), d(id="securityCode")):
        assert formfill.classify(f) == "PAYMENT"

def test_profile_mapping():
    assert formfill.classify(d(autocomplete="given-name")) == "first_name"
    assert formfill.classify(d(name="lastName")) == "last_name"
    assert formfill.classify(d(label="Email Address")) == "email"
    assert formfill.classify(d(placeholder="ZIP code")) == "zip"
    assert formfill.classify(d(name="addressLine1")) == "address1"
    assert formfill.classify(d(id="billing-state")) == "state"

def test_unknown_returns_none():
    assert formfill.classify(d(name="giftMessage")) is None

def test_payment_wins_over_profile():
    assert formfill.classify(d(name="cardholderZip", label="card zip")) == "PAYMENT"
```

- [ ] **Step 2: Run to verify failure**: `.venv/bin/pytest tests/test_formfill.py -q` — FAIL

- [ ] **Step 3: Implement `formfill.py`**

```python
"""Map checkout field descriptors to profile keys. Payment fields are only flagged."""

PAYMENT_TOKENS = ("card", "cc-", "ccnum", "cvv", "cvc", "expir", "security", "pan")

FIELD_MAP = [
    (("given-name", "first"), "first_name"),
    (("family-name", "last"), "last_name"),
    (("email",), "email"),
    (("tel", "phone"), "phone"),
    (("address-line1", "address1", "addressline1", "street"), "address1"),
    (("address-line2", "address2", "addressline2", "apt", "suite"), "address2"),
    (("postal", "zip"), "zip"),
    (("city",), "city"),
    (("state", "region", "province"), "state"),
]

GATHER_JS = """
() => Array.from(document.querySelectorAll(
        'input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select'))
    .filter(el => el.offsetParent !== null)
    .map((el, i) => ({
        i,
        name: el.name || '',
        id: el.id || '',
        autocomplete: el.getAttribute('autocomplete') || '',
        placeholder: el.placeholder || '',
        label: (el.labels && el.labels[0] && el.labels[0].innerText) || '',
        tag: el.tagName.toLowerCase(),
        value: el.value || '',
    }))
"""

FILL_SELECTOR = ("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select")


def classify(desc: dict) -> str | None:
    hay = " ".join(str(desc.get(k, "")) for k in
                   ("name", "id", "autocomplete", "placeholder", "label")).lower()
    if any(t in hay for t in PAYMENT_TOKENS):
        return "PAYMENT"
    for tokens, key in FIELD_MAP:
        if any(t in hay for t in tokens):
            return key
    return None
```

- [ ] **Step 4: Run tests, expect PASS**: `.venv/bin/pytest tests/test_formfill.py -q`

- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: checkout field classifier (payment excluded)"`

---

### Task 5: `detector.js` + `mock/` + integration test

**Files:**
- Create: `detector.js`, `mock/server.py`
- Test: `tests/test_detector_integration.py`

**Interfaces:**
- Produces: `detector.js` — injectable IIFE; sets `window.__pp_found` (epoch ms) and clicks the first visible enabled element matching /buy now/i among `button, a, input[type=submit], [role=button]`; watches via MutationObserver. `mock/server.py` — `python mock/server.py [--port 8199] [--flip-in 5]`; serves `/` (countdown page whose hidden Buy Now button is revealed `flip_in` seconds after server start) and `/checkout` (form with contact/address + card fields, non-functional submit).

- [ ] **Step 1: Write `detector.js`**

```javascript
(() => {
  if (window.__pp_armed) return;
  window.__pp_armed = true;
  const RX = /buy\s*now/i;
  const CANDIDATES = 'button, a, input[type="submit"], [role="button"]';
  const find = () => {
    for (const el of document.querySelectorAll(CANDIDATES)) {
      const t = el.innerText || el.value || el.getAttribute('aria-label') || '';
      if (RX.test(t) && !el.disabled && el.offsetParent !== null) return el;
    }
    return null;
  };
  const fire = (el) => {
    if (window.__pp_found) return;
    window.__pp_found = Date.now();
    el.click();
  };
  const now = find();
  if (now) return fire(now);
  new MutationObserver(() => {
    const el = find();
    if (el) fire(el);
  }).observe(document.documentElement, {
    subtree: true, childList: true,
    attributes: true, attributeFilter: ['disabled', 'class', 'style', 'hidden'],
  });
})();
```

- [ ] **Step 2: Write `mock/server.py`**

```python
"""Local rehearsal site: countdown -> Buy Now flip -> checkout form."""
import argparse
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE = """<!doctype html><title>Mock Pasta Pass</title>
<h1>Never-Ending Pasta Pass</h1>
<p id="status">Sale starts soon…</p>
<button id="buy" style="display:none" onclick="location.href='/checkout'">Buy Now</button>
<script>
  const flipAt = %FLIP_AT% * 1000;
  const t = setInterval(() => {
    if (Date.now() >= flipAt) {
      document.getElementById('buy').style.display = 'inline-block';
      document.getElementById('status').textContent = 'ON SALE';
      clearInterval(t);
    }
  }, 100);
</script>"""

CHECKOUT = """<!doctype html><title>Mock Checkout</title>
<h1>Checkout — you have 8:00</h1>
<form>
  <label>First Name <input name="firstName" autocomplete="given-name"></label><br>
  <label>Last Name <input name="lastName" autocomplete="family-name"></label><br>
  <label>Email <input name="email" autocomplete="email"></label><br>
  <label>Phone <input name="phone" autocomplete="tel"></label><br>
  <label>Address <input name="addressLine1" autocomplete="address-line1"></label><br>
  <label>City <input name="city"></label><br>
  <label>State <input name="state"></label><br>
  <label>ZIP <input name="zip" autocomplete="postal-code"></label><br>
  <label>Card Number <input name="cardNumber" autocomplete="cc-number"></label><br>
  <label>Expiration <input name="expiry" placeholder="MM/YY"></label><br>
  <label>CVV <input name="cvv"></label><br>
  <button type="button">Place Order</button>
</form>"""


class H(BaseHTTPRequestHandler):
    flip_at = 0.0

    def do_GET(self):
        body = CHECKOUT if self.path.startswith("/checkout") else \
            PAGE.replace("%FLIP_AT%", str(self.flip_at))
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def serve(port: int, flip_in: float) -> HTTPServer:
    H.flip_at = time.time() + flip_in
    return HTTPServer(("127.0.0.1", port), H)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8199)
    ap.add_argument("--flip-in", type=float, default=5)
    a = ap.parse_args()
    print(f"mock on http://127.0.0.1:{a.port} — Buy Now in {a.flip_in}s")
    serve(a.port, a.flip_in).serve_forever()
```

- [ ] **Step 3: Write integration test**

`tests/test_detector_integration.py`:
```python
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
            page.wait_for_function("window.__pp_found", timeout=8000)
            page.wait_for_url("**/checkout", timeout=5000)
            browser.close()
    finally:
        srv.shutdown()
```

Also create `mock/__init__.py` and `tests/__init__.py` (empty) so imports resolve.

- [ ] **Step 4: Run integration test, expect PASS**: `.venv/bin/pytest tests/test_detector_integration.py -q`

- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: buy-now detector + mock rehearsal site"`

---

### Task 6: `buybot.py` orchestrator

**Files:**
- Create: `buybot.py`

**Interfaces:**
- Consumes: everything above (`timesync.fetch_offset/corrected_now`, `alerts.build_schedule/run_schedule/send_all/alarm`, `formfill.classify/GATHER_JS/FILL_SELECTOR`, `detector.js`).
- Produces: CLI `buybot.py [--url URL] [--drop 2026-07-16T14:00] [--config config.json] [--tz America/New_York] [--open-at-seconds 300]`.

Behavior (all in one file; ~180 lines):
1. Load config; require `alert_numbers` (2 numbers) and `profile`.
2. `offset = timesync.fetch_offset(url)`; log offset.
3. Compute `drop_epoch` from `--drop` + `--tz` via `zoneinfo`.
4. Start daemon thread: `alerts.run_schedule(alerts.build_schedule(drop_epoch, corrected_now(offset)), numbers, offset, stop_event)`.
5. Sleep until T−`open_at_seconds` (5 min default), then launch **headed** Chromium (`channel="chrome"`, fall back to bundled), two pages. Tab A: goto URL, add detector via `page.add_init_script` + `page.evaluate` (init script survives client-side rerenders; evaluate arms the current DOM). Tab B: idle until T−15 s, then reload every 2 s, re-`evaluate` detector after each load.
6. Main loop polls both pages for `window.__pp_found` every 50 ms. At T+5 s without detection: send "⚠️ 2:00 passed, no Buy Now button yet — still watching" (once).
7. On detection: stop Tab B loop; `alerts.alarm()`; `alerts.send_all(numbers, "🚨 BUY NOW CLICKED — GO! Card + Place Order, 8 min")`; screenshot.
8. Fill phase on the winning page, retried every 2 s for 10 min: run `GATHER_JS`, `classify` each descriptor; fill empty mapped fields via `page.locator(FILL_SELECTOR).nth(i)` (`select_option` for selects, else `fill`); outline `PAYMENT` fields red via JS; screenshot after each round that changed something; log summary `filled=[...] payment=[...] unknown=[...]`.
9. Never touch anything classified PAYMENT; never click submit. Keep process alive until Ctrl-C (browser stays open).
10. Every state change logged to stdout + `buybot.log`; screenshots to `screenshots/`.

- [ ] **Step 1: Implement `buybot.py`** (complete file)

```python
"""Drop-day orchestrator: alerts, detection, click, non-payment fill, human finish."""
import argparse
import json
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

import alerts
import formfill
import timesync

log = logging.getLogger("buybot")
DETECTOR = Path(__file__).with_name("detector.js").read_text()


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://www.pastapass.com")
    ap.add_argument("--drop", default="2026-07-16T14:00")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--open-at-seconds", type=int, default=300)
    return ap.parse_args()


def load_config(path: str) -> dict:
    cfg = json.loads(Path(path).read_text())
    numbers = cfg.get("alert_numbers", [])
    if len(numbers) < 2:
        sys.exit("config.json needs two alert_numbers")
    if not cfg.get("profile"):
        sys.exit("config.json needs a profile block")
    return cfg


def shot(page, name):
    try:
        Path("screenshots").mkdir(exist_ok=True)
        page.screenshot(path=f"screenshots/{time.strftime('%H%M%S')}-{name}.png", full_page=True)
    except Exception as e:
        log.warning("screenshot %s failed: %s", name, e)


def arm(page, url):
    page.add_init_script(DETECTOR)
    page.goto(url, wait_until="domcontentloaded")
    page.evaluate(DETECTOR)


def found(page):
    try:
        return page.evaluate("window.__pp_found || 0")
    except Exception:
        return 0


def fill_round(page, profile) -> bool:
    descs = page.evaluate(formfill.GATHER_JS)
    filled, payment = [], []
    for d in descs:
        key = formfill.classify(d)
        if key == "PAYMENT":
            payment.append(d["i"])
        elif key and not d["value"] and profile.get(key):
            loc = page.locator(formfill.FILL_SELECTOR).nth(d["i"])
            try:
                if d["tag"] == "select":
                    loc.select_option(label=profile[key])
                else:
                    loc.fill(profile[key])
                filled.append(key)
            except Exception as e:
                log.warning("fill %s failed: %s", key, e)
    if payment:
        page.evaluate(
            """(idxs) => {const els = document.querySelectorAll(%s);
                idxs.forEach(i => els[i] && (els[i].style.outline = '3px solid red'));}"""
            % json.dumps(formfill.FILL_SELECTOR), payment)
    if filled:
        log.info("filled %s; %d payment fields highlighted (YOURS)", filled, len(payment))
    return bool(filled)


def main():
    a = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler("buybot.log")])
    cfg = load_config(a.config)
    numbers, profile = cfg["alert_numbers"], cfg["profile"]

    drop_epoch = datetime.fromisoformat(a.drop).replace(tzinfo=ZoneInfo(a.tz)).timestamp()
    offset = timesync.fetch_offset(a.url)
    log.info("server clock offset %+.2fs; drop at %s (%s)", offset, a.drop, a.tz)

    stop = threading.Event()
    sched = alerts.build_schedule(drop_epoch, timesync.corrected_now(offset))
    threading.Thread(target=alerts.run_schedule, args=(sched, numbers, offset, stop),
                     daemon=True).start()
    log.info("%d countdown alerts armed", len(sched))

    while timesync.corrected_now(offset) < drop_epoch - a.open_at_seconds:
        time.sleep(1)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=False, channel="chrome")
        except Exception:
            browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        tab_a, tab_b = ctx.new_page(), ctx.new_page()
        arm(tab_a, a.url)
        log.info("tab A armed (observer)")
        shot(tab_a, "armed")

        warned_late = False
        last_reload = 0.0
        winner = None
        while not winner:
            now = timesync.corrected_now(offset)
            for page in (tab_a, tab_b):
                if found(page):
                    winner = page
                    break
            if winner:
                break
            if now >= drop_epoch - 15 and now - last_reload >= 2:
                last_reload = now
                try:
                    if not tab_b.url.startswith(a.url.rstrip("/")):
                        arm(tab_b, a.url)
                    else:
                        tab_b.reload(wait_until="domcontentloaded")
                        tab_b.evaluate(DETECTOR)
                except Exception as e:
                    log.warning("tab B reload: %s", e)
            if now >= drop_epoch + 5 and not warned_late:
                warned_late = True
                alerts.send_all(numbers, "⚠️ 2:00 passed — no Buy Now button yet, still watching")
            time.sleep(0.05)

        log.info("BUY NOW clicked at %+0.2fs after drop", timesync.corrected_now(offset) - drop_epoch)
        winner.bring_to_front()
        alerts.alarm()
        alerts.send_all(numbers, "🚨 BUY NOW CLICKED — GO! Type card + Place Order (8 min window)")
        shot(winner, "clicked")

        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                if fill_round(winner, profile):
                    shot(winner, "filled")
            except Exception as e:
                log.warning("fill round: %s", e)
            time.sleep(2)
        log.info("fill loop ended; browser stays open — Ctrl-C when done")
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax + unit suite green**: `.venv/bin/python -m py_compile buybot.py && .venv/bin/pytest -q`

- [ ] **Step 3: Commit**: `git add -A && git commit -m "feat: drop-day orchestrator"`

---

### Task 7: Rehearsal + arm for Thursday

**Files:**
- Create: `config.json` (from example — Kian fills real numbers/profile; gitignored), `README.md`

- [ ] **Step 1: Full mock rehearsal**

Terminal 1: `.venv/bin/python mock/server.py --port 8199 --flip-in 90`
Terminal 2 (drop set ~90 s out, matching flip):
```bash
.venv/bin/python buybot.py --url http://127.0.0.1:8199 \
  --drop "<now+90s local, ISO e.g. 2026-07-14T03:05>" --tz America/Los_Angeles --open-at-seconds 60
```
Expected: T−1 iMessage on both phones → browser opens → button flips → clicked <1 s → alarm + drop iMessage → checkout fields filled except card/expiry/CVV outlined red → no submit.

- [ ] **Step 2: Start recon loop** (background): `.venv/bin/python recon.py --loop 1800`

- [ ] **Step 3: Write `README.md`** — how to fill `config.json`, the exact Thursday command
  (`.venv/bin/python buybot.py`), what the human does at 2:00 (card + Place Order + any CAPTCHA), fallback = just use the open browser manually.

- [ ] **Step 4: Commit**: `git add -A && git commit -m "docs: runbook"`

---

## Self-Review

- **Spec coverage:** recon loop (T3), config w/o card (T1/T7), clock sync (T1), alert schedule incl. late-warning + two numbers (T2/T6), two-tab detection (T5/T6), non-payment fill + red highlight + no-submit (T4/T6), screenshots/logs (T6), mock rehearsal (T5/T7), ban-risk = spec-only (no task needed). ✔
- **Placeholder scan:** none. ✔
- **Type consistency:** `classify` keys match `config.example.json` profile keys; `GATHER_JS`/`FILL_SELECTOR` element order both come from the same selector string, so `nth(i)` indexes align; `serve(port, flip_in)` matches test usage. ✔
