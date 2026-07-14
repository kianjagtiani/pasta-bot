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
