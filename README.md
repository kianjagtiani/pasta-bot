I really want the olive garden pasta pass.

- **What it does:** Watches the Olive Garden drop page and clicks "Buy Now" the instant it appears, then auto-fills the contact and address fields — you type the card details and click Place Order yourself.
- **How it detects the drop:** A small JavaScript detector (`detector.js`) is injected into two Chrome tabs (one quietly observing the page, one reloading it) so the button is caught the moment it goes live.
- **How it keeps you in the loop:** iMessage alerts count down to the drop and fire a loud "GO!" the second the button is clicked; a recon loop (`recon.py`) checks the page for changes in the days before.
- **Architecture:** A Python orchestrator (`buybot.py`) drives a real Chrome browser via Playwright, with helper modules for alerts, form-filling, and time sync, plus a mock site (`mock/server.py`) for rehearsals — the browser stays fully usable by hand as a fallback.
