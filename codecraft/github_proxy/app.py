"""GitHub device-flow proxy for the forja web app.

Why this exists: GitHub's device endpoints (github.com/login/device/code and
github.com/login/oauth/access_token) do not send CORS headers, so a browser on
a static page cannot call them. This Lambda forwards exactly those two calls.
It is the only server-side piece; the OAuth App's client secret is never used
(device flow needs none) and never leaves GitHub.

Runtime: AWS Lambda (python3.12) behind an API Gateway HTTP API, same pattern
as backend/progress in alektebel.github.io. Stdlib only.

Routes (POST, JSON in/out):
  POST /device  {}                                 -> GitHub's device code
  POST /token   {"device_code": "..."}             -> GitHub's token response
  GET  /                                          -> {"ok": true} smoke test
  OPTIONS /*                                      -> 204 + CORS

Env vars (set by template-github-cfn.yaml):
  GITHUB_CLIENT_ID  public OAuth App client id (not a secret)
  ALLOWED_ORIGIN    comma-separated CORS origins

Security notes:
  - The scope is locked to read:user; clients cannot ask for more.
  - The client id comes from the environment, never from the request.
  - The proxy only forwards to the two fixed GitHub URLs (no open proxy).
  - The device code and access token pass through this function; they are
    never logged and responses are marked no-store.
"""

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_ORIGINS = (
    "https://diegoatencia.dev,https://www.diegoatencia.dev,"
    "https://alektebel.github.io,http://127.0.0.1:8875,http://localhost:8875"
)
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
SCOPE = "read:user"
DEVICE_CODE_RE = re.compile(r"^[A-Za-z0-9]{8,128}$")
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def _cors(origin):
    allowed = [
        o.strip()
        for o in os.environ.get("ALLOWED_ORIGIN", DEFAULT_ORIGINS).split(",")
        if o.strip()
    ]
    if not allowed:
        allowed = DEFAULT_ORIGINS.split(",")
    return {
        "Access-Control-Allow-Origin": origin if origin in allowed else allowed[0],
        "Vary": "Origin",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Max-Age": "86400",
        "Cache-Control": "no-store",
        "Content-Type": "application/json",
    }


def _reply(status, headers, body):
    return {"statusCode": status, "headers": headers, "body": json.dumps(body)}


def _payload(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _forward(url, fields):
    """POST form fields to GitHub and return (status, decoded JSON)."""
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": BROWSER_UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return 502, {"error": "github_unreachable"}
    try:
        body = json.loads(raw)
    except ValueError:  # GitHub answered with HTML, e.g. a proxy error page
        return 502, {"error": "github_bad_response", "status": status}
    return status, body if isinstance(body, dict) else {"error": "github_bad_response"}


def lambda_handler(event, context):
    headers = _cors((event.get("headers") or {}).get("origin", ""))
    ctx = event.get("requestContext", {}).get("http", {}) or {}
    method = ctx.get("method", "")
    path = ctx.get("path", "")

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": headers, "body": ""}
    if method == "GET" and path not in ("/device", "/token"):
        return _reply(200, headers, {"ok": True})
    if method != "POST":
        return _reply(405, headers, {"error": "method_not_allowed"})

    client_id = os.environ.get("GITHUB_CLIENT_ID", "").strip()
    if not client_id:
        return _reply(500, headers, {"error": "github_proxy_not_configured"})

    if path == "/device":
        status, body = _forward(DEVICE_URL, {"client_id": client_id, "scope": SCOPE})
        return _reply(status, headers, body)

    if path == "/token":
        payload = _payload(event)
        code = (payload or {}).get("device_code", "")
        if not isinstance(code, str) or not DEVICE_CODE_RE.match(code):
            return _reply(400, headers, {"error": "bad_device_code"})
        status, body = _forward(
            TOKEN_URL,
            {
                "client_id": client_id,
                "device_code": code,
                "grant_type": GRANT_TYPE,
            },
        )
        return _reply(status, headers, body)

    return _reply(404, headers, {"error": "not_found"})
