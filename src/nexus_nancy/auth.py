import http.server
import json
import secrets
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
    client_id = "pdlLmc9vS9j78K6m0iS16iP3979T6Y"
    # Port 18081 is a common local callback port for this flow.
    port = 18081
    redirect_uri = f"http://localhost:{port}/callback"

    state = secrets.token_urlsafe(16)
    auth_url = "https://auth0.openai.com/authorize?" + urlencode({
        "client_id": client_id,
        "audience": "https://api.openai.com/v1",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access",
        "state": state,
    })

    print("\n--- OpenAI Codex Login ---")
    print("Opening browser to authorize Nexus-Nancy...")
    print(f"URL: {auth_url}\n")

    # Try to open browser automatically
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    server.auth_code = None
    server.auth_state = None

    # Wait for one request
    server.handle_request()

    if not server.auth_code or server.auth_state != state:
        raise RuntimeError("Login failed: Invalid state or no code received.")

    print("Exchanging code for tokens...")

    resp = requests.post("https://auth0.openai.com/oauth/token", json={
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
