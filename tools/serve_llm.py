"""The gateway that lets other people's copies of the game reach this machine.

LM Studio's own server is meant for one trusted user on one machine: it does
not check the API key it is handed, it will answer any endpoint, and it queues
without ever saying so. Exposing it straight to the internet through a tunnel
would mean an unbounded number of strangers sharing one GPU, with the only
feedback being turns that quietly time out.

So the tunnel points here instead, and this forwards to LM Studio:

    player -> cloudflared -> serve_llm.py -> LM Studio (localhost:1234)

What it is honestly for is graceful degradation, not security. The shared token
ships inside the distributed game, so anyone who unzips it has the token - that
is understood, and it is fine. The token's real job is to turn away the
automated scanners that do find tunnel hostnames. The parts that matter are the
slot limit and the caps: they are what make a sixth simultaneous player get a
straight answer instead of a four-minute wait.

Run it with:

    LLM_TOKEN=<shared token> python3 tools/serve_llm.py

tools/start_server.sh starts this together with the tunnel.
"""

import argparse
import collections
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Only what the game actually calls. Everything else - completions, embeddings,
# model loading, LM Studio's own REST API - is not reachable through here.
ALLOWED = {("GET", "/v1/models"), ("POST", "/v1/chat/completions")}

# One turn is minutes of GPU time, so the ceiling is small and the units are
# whole conversations, not requests per second.
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW = 60.0

MAX_BODY_BYTES = 256 * 1024
# Above the 3500 the client asks for when it retries a reply that came back
# empty, which is the largest request the game legitimately makes: a reasoning
# model that spent its budget thinking needs that room to think *and* speak,
# and clamping it lower turns the retry into a second helping of the same
# failure. This only has to stop a caller asking for something absurd.
MAX_TOKENS_CAP = 4000


class Limits:
    """Slot accounting and per-IP rate limiting, shared across handler threads."""

    def __init__(self, slots):
        self.slots = threading.BoundedSemaphore(slots)
        self.total = slots
        self._lock = threading.Lock()
        self._hits = collections.defaultdict(collections.deque)

    def take_slot(self):
        return self.slots.acquire(blocking=False)

    def release_slot(self):
        self.slots.release()

    def rate_ok(self, ip):
        now = time.monotonic()
        with self._lock:
            hits = self._hits[ip]
            while hits and now - hits[0] > RATE_LIMIT_WINDOW:
                hits.popleft()
            if len(hits) >= RATE_LIMIT_REQUESTS:
                return False
            hits.append(now)
            # Evicted by age, not by emptiness: the prune above only ever runs
            # for the IP making the current request, so an address that called
            # once and never came back keeps its entry forever and is never
            # empty. Testing the newest hit is what actually collects them.
            if len(self._hits) > 4096:
                stale = [a for a, h in self._hits.items() if not h or now - h[-1] > RATE_LIMIT_WINDOW]
                for addr in stale:
                    del self._hits[addr]
            return True


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 would close the connection after every response and force each
    # turn to pay a fresh TLS handshake through the tunnel. Keep-alive requires
    # an accurate Content-Length on every reply, which _send below always sets.
    protocol_version = "HTTP/1.1"
    server_version = "KodAI-Gateway"

    # Bound to the ServerConfig by serve() below.
    limits = None
    upstream = ""
    token = ""

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, message):
        self._send(code, {"error": {"message": message}})

    def _reject(self, code, message, unread=0):
        """Turn a request away without stranding its body in the socket.

        Keep-alive is on, so bytes left unread are parsed as the start of the
        next request on this connection. cloudflared pools its connections to
        the origin, so the request that then fails to parse may well belong to
        a different player than the one who was turned away.
        """
        if unread > 0:
            try:
                self.rfile.read(unread)
            except OSError:
                self.close_connection = True
        self._error(code, message)

    def _client_ip(self):
        # Every request arrives from the tunnel process on loopback, so the
        # socket address is the same for everyone and useless for rate
        # limiting. cloudflared passes the real client along in this header.
        forwarded = self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def _authorized(self):
        if not self.token:
            return True
        header = self.headers.get("Authorization", "")
        return header.startswith("Bearer ") and header[7:].strip() == self.token

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        # Settled before anything else, because every rejection below has to
        # know how much body it is leaving behind.
        length = 0
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            # A negative or unparseable length would otherwise reach
            # rfile.read(-1), which blocks until the peer closes the socket -
            # stranding this thread for as long as a scanner cares to hold the
            # connection open. Neither is drainable, so the connection goes.
            if length < 0:
                self.close_connection = True
                self._error(400, "Bad Content-Length.")
                return
            if length > MAX_BODY_BYTES:
                self.close_connection = True
                self._error(413, "Request too large.")
                return

        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if (method, path) not in ALLOWED:
            self._reject(404, "Not found.", length)
            return
        if not self._authorized():
            self._reject(401, "Bad token.", length)
            return
        if not self.limits.rate_ok(self._client_ip()):
            self._reject(429, "Too many requests. Slow down.", length)
            return

        body = None
        if method == "POST":
            try:
                body = self._sanitize(self.rfile.read(length))
            except ValueError as e:
                self._error(400, str(e))
                return

        # The probe is cheap and must never be refused for lack of a slot -
        # the game calls it to decide whether to show MODEL OK at all, and a
        # busy server is still a reachable one.
        if method == "GET":
            self._forward(method, path, body)
            return

        if not self.limits.take_slot():
            self._error(503, "All slots busy.")
            return
        try:
            self._forward(method, path, body)
        finally:
            self.limits.release_slot()

    def _sanitize(self, raw):
        """Clamp what one caller can ask the shared GPU to do."""
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("Body is not JSON.") from None
        if not isinstance(payload, dict):
            raise ValueError("Body is not a JSON object.")
        # A caller asking for an enormous generation would hold a slot for far
        # longer than a turn of the game ever needs.
        requested = payload.get("max_tokens")
        if not isinstance(requested, int) or requested > MAX_TOKENS_CAP or requested < 1:
            payload["max_tokens"] = MAX_TOKENS_CAP
        # Streaming is refused rather than clamped: the game never asks for it,
        # and Cloudflare Quick Tunnels do not carry server-sent events anyway.
        payload["stream"] = False
        return json.dumps(payload).encode()

    def _forward(self, method, path, body):
        req = urllib.request.Request(
            self.upstream + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                payload = r.read()
                code = r.getcode()
        except urllib.error.HTTPError as e:
            self._error(e.code, f"Model server said: {e.reason}")
            return
        except Exception as e:  # noqa: BLE001 - upstream down, or the model is wedged
            self._error(502, f"Model server is not answering ({e.__class__.__name__}).")
            return
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve(port, upstream, token, slots):
    Handler.limits = Limits(slots)
    Handler.upstream = upstream.rstrip("/")
    Handler.token = token
    # ThreadingHTTPServer, emphatically not HTTPServer: the default is
    # single-threaded, which would put every player in one line behind one
    # multi-minute generation and cancel out LM Studio's own batching entirely.
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"gateway on 127.0.0.1:{port} -> {Handler.upstream}  ({slots} slots)", flush=True)
    if not token:
        print("warning: no LLM_TOKEN set, the gateway is open to anyone", file=sys.stderr, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--upstream", default=os.environ.get("LLM_UPSTREAM", "http://localhost:1234"))
    ap.add_argument("--slots", type=int, default=5, help="concurrent turns before 503")
    args = ap.parse_args()
    serve(args.port, args.upstream, os.environ.get("LLM_TOKEN", ""), args.slots)


if __name__ == "__main__":
    main()
