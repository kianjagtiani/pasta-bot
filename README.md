# PastaPass Buy-Bot

Hybrid bot for the Olive Garden Never-Ending Pasta Pass drop — **Thursday, July 16, 2026, 2:00 p.m. ET (11:00 a.m. PT)**. It clicks "Buy Now" the instant it appears and fills the non-payment checkout fields; **you type the card and click Place Order** (8-minute checkout window).

## Before Thursday

1. **Edit `config.json`** (never committed): put your **two real alert numbers** in `alert_numbers` and correct the `profile` block (name, email, phone, billing address).
2. **Grant automation permission once**: run
   `osascript -e 'tell application "Messages" to send "test" to participant "+1YOURNUMBER" of (1st account whose service type = iMessage)'`
   and click **OK** on the macOS permission prompt. Both phones should get the test text.
3. Keep the recon loop running (`.venv/bin/python recon.py --loop 1800`) and check `recon/changes.log` for `⚠️ ANTI-BOT KEYWORDS` or `CHANGED` entries.

## Thursday

Start any time before ~1:30 p.m. ET:

```bash
.venv/bin/python buybot.py
```

What happens:
- iMessage countdown to both numbers at T−30 / T−15 / T−5 / T−1 min.
- At T−5 min a Chrome window opens with two tabs watching the page (one observer, one reloader).
- The instant "Buy Now" appears it is clicked; loud alarm + "GO!" text fire; contact/address fields fill themselves; **card fields are outlined red — type those, then click Place Order.**
- If a CAPTCHA or queue appears, solve/wait by hand in the same window — the bot never blocks manual use.
- Screenshots land in `screenshots/`, log in `buybot.log`.

**Fallback:** if anything misbehaves, just use the open browser window like a normal human — you're already on the page at second zero.

## Rehearsal

```bash
.venv/bin/python mock/server.py --port 8199 --flip-in 100   # terminal 1
.venv/bin/python buybot.py --url http://127.0.0.1:8199 \
  --drop "$(date -v+100S +%Y-%m-%dT%H:%M:%S)" --tz America/Los_Angeles --open-at-seconds 60   # terminal 2
```

## Tests

```bash
.venv/bin/pytest -q
```
