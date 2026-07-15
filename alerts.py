"""iMessage countdown alerts + local alarm. Must never raise into the buy path."""
import logging
import subprocess
import threading

import timesync

log = logging.getLogger("alerts")

COUNTDOWN = [
    (1800, "yo pasta pass drops in 30 mins, start locking in gng"),
    (900, "15 mins out twin, wrap up whatever ur doing fr"),
    (300, "5 MINS BRO GET TO THE LAPTOP RN this is not a drill"),
    (60, "1 MIN LEFT LOCK TF IN, eyes on the browser gang"),
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
