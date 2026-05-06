import hashlib
import base64
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
            b"<p>You can close this window now and return to the terminal.</p></body></html>"
        )

    def log_message(self, format, *args):
        # Silence server logs
        return


def generate_pkce():
    # Use hex to match ChatMock's verifier style and length (128 chars)
    code_verifier = secrets.token_hex(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def parse_jwt_claims(token: str):
    if not token or token.count(".") != 2:
        return None
    try:
        _, payload, _ = token.split(".")
        padded = payload + "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(padded.encode())
        return json.loads(data.decode())
    except Exception:
        return None


def login_codex(session_path: Path):
    import threading

    client_id = "app_EMoamEEZ73f0CkXaXp7hrann"
    # Port 1455 is the standard callback port for the Codex CLI flow.
    port = 1455
    redirect_uri = f"http://localhost:{port}/auth/callback"

    state = secrets.token_hex(32)
    code_verifier, code_challenge = generate_pkce()

    auth_url = "https://auth.openai.com/oauth/authorize?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": "openid profile email offline_access",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "codex_cli_simplified_flow": "true",
            "id_token_add_organizations": "true",
        }
    )

    print("\n" + "=" * 60)
    print(" OPENAI CODEX LOGIN (CHATGPT PLUS)".center(60))
    print("=" * 60)
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
    server.timeout = 0.5  # Short timeout for handle_request

    def _serve():
        # Listen for a single request
        server.handle_request()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()

    print(f"(Listening on localhost:{port} for automatic local redirect...)")

    try:
        manual_url = input("\nPASTE REDIRECT URL HERE: ").strip()
    except EOFError:
        manual_url = ""

    if manual_url:
        try:
            # Parse manually first
            query = parse_qs(urlparse(manual_url).query)
            code = query.get("code", [None])[0]
            state_val = query.get("state", [None])[0]
            
            if code and state_val:
                server.auth_code = code
                server.auth_state = state_val
            
            # Unblock the server thread by sending a dummy request to ITSELF
            try:
                requests.get(f"http://127.0.0.1:{port}/unblock", timeout=0.1)
            except Exception:
                pass
        except Exception as e:
            print(f"Error parsing URL: {e}")

    # Wait for server thread to finish (either caught redirect or was unblocked)
    t.join(timeout=5)
    server.server_close()

    if not server.auth_code or server.auth_state != state:
        print("\n[FAIL] Login timed out or invalid URL provided.")
        raise RuntimeError("Login failed: Invalid state or no code received.")

    print("\n[OK] Identity verified. Exchanging code for tokens...")

    # Use data= for application/x-www-form-urlencoded, required by OpenAI
    resp = requests.post(
        "https://auth.openai.com/oauth/token",
        data={
            "client_id": client_id,
            "code": server.auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )

    if not resp.ok:
        raise RuntimeError(f"Token exchange failed: {resp.text}")

    tokens = resp.json()
    id_token = tokens.get("id_token")
    id_claims = parse_jwt_claims(id_token) if id_token else None

    # Optional: Exchange session for a persistent sk-... API key
    if id_claims and id_claims.get("organization_id") and id_claims.get("project_id"):
        print("[INFO] Attempting to upgrade session to persistent API key...")
        exchange_resp = requests.post(
            "https://auth.openai.com/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": client_id,
                "requested_token": "openai-api-key",
                "subject_token": id_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            },
        )
        if exchange_resp.ok:
            exchange_tokens = exchange_resp.json()
            tokens["api_key"] = exchange_tokens.get("access_token")
            print("[OK] Persistent API key obtained.")

    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    session_path.chmod(0o600)

    print(f"Login successful! Tokens saved to {session_path}")
    return tokens


def get_codex_token(session_path: Path):
    if not session_path.exists():
        return None

    tokens = json.loads(session_path.read_text(encoding="utf-8"))

    # Prefer the persistent API key if we have one
    if tokens.get("api_key"):
        return tokens.get("api_key")

    # Simplified token refresh logic
    # In a full impl, check 'expires_in' and use 'refresh_token'.
    return tokens.get("access_token")
