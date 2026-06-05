#!/usr/bin/env python3
"""
Minimal reference service for the DGXample.

Serves two endpoints on the single exposed port:
  GET /health  -> JSON {"status": "ok"}   (used by the container healthcheck)
  GET /        -> HTML info + status page

Listens on http or https depending on USE_HTTPS. When USE_HTTPS=true it loads the
host-generated certificate mounted read-only at /certs. A real container replaces
the Handler with its own service logic — the surrounding scaffolding (single port,
optional TLS, /health endpoint) is the part that stays the same across containers.
"""
import json
import os
import socket
import ssl
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

APP_PORT = int(os.environ.get("APP_PORT", "9000"))
USE_HTTPS = os.environ.get("USE_HTTPS", "false").lower() == "true"
SECURITY_LEVEL = os.environ.get("SECURITY_LEVEL", "strict")
CERT_FILE = "/certs/cert.pem"
KEY_FILE = "/certs/key.pem"

START_TIME = time.time()


def info():
    return {
        "service": "nettest",
        "status": "ok",
        "hostname": socket.gethostname(),
        "security_level": SECURITY_LEVEL,
        "protocol": "https" if USE_HTTPS else "http",
        "port": APP_PORT,
        "uptime_seconds": int(time.time() - START_TIME),
        "python": sys.version.split()[0],
    }


def render_page(data):
    rows = "\n".join(
        f"    <tr><th>{k}</th><td>{v}</td></tr>" for k, v in data.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>nettest — {data['hostname']}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 36rem; padding: 0 1rem; }}
    h1 {{ font-size: 1.4rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ text-align: left; padding: 0.4rem 0.8rem; border-bottom: 1px solid #ddd; }}
    th {{ width: 12rem; color: #555; font-weight: 600; }}
    .ok {{ color: #138000; }}
  </style>
</head>
<body>
  <h1>nettest <span class="ok">&#9679; {data['status']}</span></h1>
  <p>Minimal reference service for the DGXample.</p>
  <table>
{rows}
  </table>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, json.dumps({"status": "ok"}).encode(), "application/json")
        elif self.path == "/":
            self._send(200, render_page(info()).encode(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found\n", "text/plain")

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    httpd = HTTPServer(("0.0.0.0", APP_PORT), Handler)
    if USE_HTTPS:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    proto = "https" if USE_HTTPS else "http"
    print(f"nettest serving {proto} on 0.0.0.0:{APP_PORT} (security={SECURITY_LEVEL})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
