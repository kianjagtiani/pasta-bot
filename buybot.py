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
    page.goto(url, wait_until="domcontentloaded")
    page.evaluate(DETECTOR)


def found(page) -> float:
    try:
        return page.evaluate(
            "window.__pp_found || Number(sessionStorage.getItem('__pp_found')) || 0")
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
            """(args) => {const els = document.querySelectorAll(args.sel);
                args.idxs.forEach(i => els[i] && (els[i].style.outline = '3px solid red'));}""",
            {"sel": formfill.FILL_SELECTOR, "idxs": payment})
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
        tab_a.add_init_script(DETECTOR)
        tab_b.add_init_script(DETECTOR)
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

        log.info("BUY NOW clicked at %+0.2fs after drop",
                 timesync.corrected_now(offset) - drop_epoch)
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
