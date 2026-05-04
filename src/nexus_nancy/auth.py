import http.server
import json
import os
import secrets
import sys
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        query = parse_qs(urlparse(self.path).query)
        self.server.auth_code = query.get("code", [None])[0]
        self.server.auth_state = query.get("state", [None])[0]

        self.wfile.write(
            b"<html><body><h1>Login Successful</h1>"
            b"<p>You can close this window now.</p></body></html>"
        )

    def log_message(self, format, *args):
        # Silence server logs
        return


def login_codex(session_path: Path):
    import threading

    client_id = "app_EMoamEEZ73f0CkXaXp7hrann"
    # Port 18081 is a common local callback port for this flow.
    port = 18081
    redirect_uri = f"http://localhost:{port}/callback"

    state = secrets.token_urlsafe(16)
    auth_url = "https://auth.openai.com/authorize?" + urlencode({
        "client_id": client_id,
        "audience": "https://api.openai.com/v1",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access",
        "state": state,
    })

    print("\n" + "="*60)
    print(" OPENAI CODEX LOGIN (CHATGPT PLUS)".center(60))
    print("="*60)
    print("\nThis command will authenticate Nexus-Nancy using your ChatGPT Plus")
    print("subscription. Follow these steps to authorize this machine:\n")
    print(f"1. OPEN this URL in your local web browser:\n\n   {auth_url}\n")
    print("2. LOG IN to your OpenAI account.")
    print("3. AUTHORIZE the application if prompted.")
    print("4. FINISH: Your browser will redirect to a 'localhost' URL.")
    print("   Note: This page will likely show a 'Connection Refused' error.")
    print("   THIS IS NORMAL.\n")
    print("5. COPY the entire URL from your browser's address bar.")
    print("6. PASTE that URL below to complete the setup.\n")
    print("-" * 60)

    # Try to open browser automatically (works on local desktops)
    try:
        # Suppress stderr to avoid "no browser found" noise on clusters
        with open(os.devnull, "w") as f:
            old_stderr = os.dup(sys.stderr.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
            webbrowser.open(auth_url)
            os.dup2(old_stderr, sys.stderr.fileno())
    except Exception:
        pass

    server = http.server.HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    server.auth_code = None
    server.auth_state = None

    def _serve():
        try:
            server.handle_request()
        except Exception:
            pass

    t = threading.Thread(target=_serve, daemon=True)
    t.start()

    print("(Listening on localhost:18081 for automatic local redirect...)")

    try:
        manual_url = input("\nPASTE REDIRECT URL HERE: ").strip()
    except EOFError:
        manual_url = ""

    if manual_url:
        try:
            query = parse_qs(urlparse(manual_url).query)
            server.auth_code = query.get("code", [None])[0]
            server.auth_state = query.get("state", [None])[0]
            # Send a dummy request to cleanly unblock the server thread
            requests.get(redirect_uri, timeout=1)
        except Exception as e:
            print(f"Error parsing URL: {e}")

    t.join(timeout=2)

    if not server.auth_code or server.auth_state != state:
        print("\n[FAIL] Login timed out or invalid URL provided.")
        raise RuntimeError("Login failed: Invalid state or no code received.")

    print("\n[OK] Identity verified. Exchanging code for tokens...")

    resp = requests.post("https://auth.openai.com/oauth/token", json={
        "client_id": client_id,
        "code": server.auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })

    if not resp.ok:
        raise RuntimeError(f"Token exchange failed: {resp.text}")

    tokens = resp.json()
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    session_path.chmod(0o600)

    print(f"Login successful! Tokens saved to {session_path}")
    return tokens


def get_codex_token(session_path: Path):
    if not session_path.exists():
        return None

    tokens = json.loads(session_path.read_text(encoding="utf-8"))

    # Simplified token refresh logic
    # In a full impl, check 'expires_in' and use 'refresh_token'.
    return tokens.get("access_token")
