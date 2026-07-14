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
