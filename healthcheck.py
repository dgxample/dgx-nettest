#!/usr/bin/env python3
# Container healthcheck: GET /health on the app port, protocol per USE_HTTPS.
# Self-signed certs are not verified (the cert is for the browser, not this probe).
import os
import ssl
import urllib.request

port = os.environ.get("APP_PORT", "9000")
proto = "https" if os.environ.get("USE_HTTPS", "false").lower() == "true" else "http"

ctx = None
if proto == "https":
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

urllib.request.urlopen(f"{proto}://127.0.0.1:{port}/health", context=ctx, timeout=5)
