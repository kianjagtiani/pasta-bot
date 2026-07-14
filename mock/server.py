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
