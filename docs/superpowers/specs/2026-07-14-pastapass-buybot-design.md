# PastaPass Buy-Bot — Design

**Date:** 2026-07-14
**Goal:** Secure one Olive Garden Never-Ending Pasta Pass ($100 + tax, 10,000 available) the moment sales open on PastaPass.com — Thursday, July 16, 2026 at 2:00 p.m. ET (11:00 a.m. PT).

## Drop mechanics (from recon of pastapass.com)

- At 2:00 p.m. ET a **"Buy Now" button appears** on the landing page.
- ~30-minute overall purchasing window; once a pass is allocated, an **8-minute checkout window**.
- Credit/debit cards only (no Apple Pay/PayPal). Dine-in only pass, valid Aug 24 – Nov 22, 2026.
- As of July 14: no Queue-it waiting room or CAPTCHA visible in page content. Could change before Thursday — recon loop exists to catch that.

## Automation level (decided)

**Hybrid.** The bot detects and clicks "Buy Now" and fills the non-payment checkout fields. **Kian types the card details and clicks the final Place Order himself** (and solves any CAPTCHA). Card details are never stored in any file, config, or log. The 8-minute checkout window makes human-finishing cost-free; the race is only the button click.

## Components

### 1. `recon/` — pre-drop page watcher
- Script fetches `pastapass.com` HTML + referenced JS bundles, diffs against the previous snapshot, logs changes with timestamps.
- Runs every 30 minutes from now until the drop (scheduled background loop).
- Purpose: learn the real Buy Now selector and checkout form the moment Olive Garden deploys them; detect bad news early (queue system, CAPTCHA script, bot-wall).
- Output: `recon/snapshots/` (timestamped) + `recon/changes.log`.

### 2. `config.json` — local profile (gitignored, chmod 600)
- Contains: first/last name, email, phone, billing address, **two alert phone numbers** for iMessage.
- Does **not** contain card number, expiry, or CVV — typed manually at checkout.
- Kian fills it in before Thursday; delete after the drop if desired.

### 3. `buybot.py` — drop-day script (Playwright, headed Chromium)
- **Clock sync:** offset computed against NIST/`time.gov` so alert and drop timing don't depend on Mac clock drift.
- **Alert schedule** — iMessage via AppleScript (`osascript`) to **both** configured numbers, plus max-volume `afplay` alarm locally:
  - T−30 min: "Pasta Pass drop in 30 minutes"
  - T−15 min: "15 minutes"
  - T−5 min: "5 minutes — be at the laptop"
  - T−1 min: "1 minute"
  - **Drop:** the instant the Buy Now button is detected and clicked (or at T+5 s: "no button yet, still watching" if not yet detected).
- **Detection — two tabs opened at T−5 min:**
  - Tab A: static, injected MutationObserver watching for the Buy Now element (selector list from recon + text heuristic `/buy now/i` on buttons/links). Catches a client-side flip in the same tick and clicks immediately.
  - Tab B: reloads every ~2 s (starting T−15 s) to catch a server-side flip. First tab to find the button wins; the other stands down.
- **Checkout:** best-effort fill of recognized non-payment fields from `config.json` (matched via `autocomplete` attributes and label text from recon). Card fields left empty and visually highlighted. Bot **stops before final submit**.
- **Observability:** screenshot on every state change; all actions logged with timestamps.
- **Failure posture:** the browser is a normal visible window. Any selector miss or unexpected page (queue, CAPTCHA) → alarm fires, bot pauses, Kian takes over manually. The bot must never block manual use.

### 4. `mock/` — rehearsal harness
- Local static page replicating countdown → Buy Now flip → checkout form (modeled on recon findings).
- Full dry-run before Thursday: alerts (to both numbers), detection, click, fill, human finish.

## Ban-risk assessment (researched 2026-07-14)

- **Legal:** the BOTS Act (2016) covers event-ticket purchases, not restaurant promotions. One personal-use purchase via a script is not illegal.
- **Site terms:** PastaPass.com's posted terms contain **no anti-bot clause, no one-per-person limit, and no stated cancellation right** as of today (only: non-refundable, non-transferable, dine-in only). Terms could be expanded at purchase time.
- **Practice:** retailer bot-detection (Cloudflare, DataDome, etc.) targets high-volume patterns — datacenter IPs, many cards, hundreds of requests, headless fingerprints. This bot is one residential IP, one card, one purchase, a headed real browser window, with a human performing the payment step. Detection/cancellation risk is low.
- **Worst realistic outcome:** order canceled and refunded, or the IP rate-limited mid-drop → immediate manual fallback (alarm has already fired, page is open).
- **Not in scope:** CAPTCHA bypass, fingerprint spoofing, or stealth plugins. If a bot-wall appears, the design degrades gracefully to alarm-and-assist.

## Verification plan

1. Recon loop observed producing snapshots/diffs.
2. Mock rehearsal: full end-to-end run against `mock/`, confirming both numbers receive all five alert messages, button clicked < 1 s after flip, fields filled, bot halts before submit.
3. Live T−30 alerts on Thursday confirm the real run is armed.

## Out of scope

- Multiple passes / multiple sessions (one pass, personal use).
- Storing or auto-filling payment details.
- Any anti-bot circumvention.
