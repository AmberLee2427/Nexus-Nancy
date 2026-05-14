import json
import time
from pathlib import Path

import httpx
import jwt

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"


class CodexAuth:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.secret_path = workspace_root / ".agents/secrets/codex.json"

    def run(self):
        print("\n--- Codex Authentication: Initial Discovery ---")
        tokens = self._get_device_tokens()

        claims = jwt.decode(tokens["id_token"], options={"verify_signature": False})
        auth_claim = claims.get("https://api.openai.com/auth", {})
        org_id = auth_claim.get("organization_id")
        account_id = auth_claim.get("chatgpt_account_id")

        # If not in JWT, try the /v1/me endpoint
        if not org_id or not account_id:
            try:
                with httpx.Client() as client:
                    me_resp = client.get(
                        "https://api.openai.com/v1/me",
                        headers={"Authorization": f"Bearer {tokens['access_token']}"},
                    ).json()
                    org_id = org_id or me_resp.get("orgs", {}).get("data", [{}])[0].get("id")
                    account_id = account_id or me_resp.get("id")
            except Exception:
                pass

        if org_id:
            print(f"\nDetected Organization: {org_id}")
            if account_id:
                print(f"Detected Account: {account_id}")
            print("\n--- Codex Authentication: Scoped Token Verification ---")
            tokens = self._get_device_tokens(org_id)

        self.secret_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "access_token": tokens["access_token"],
            "organization_id": org_id,
            "chatgpt_account_id": account_id,
            "updated_at": time.time(),
        }
        self.secret_path.write_text(json.dumps(data, indent=2))
        print(f"\n[OK] Codex secrets saved to {self.secret_path}")
        return "Authentication successful."

    def _get_device_tokens(self, organization_id=None):
        headers = {
            "User-Agent": "Codex/0.129.0 (darwin; arm64)",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        with httpx.Client() as client:
            resp = client.post(
                "https://auth.openai.com/api/accounts/deviceauth/usercode",
                json={"client_id": CLIENT_ID},
                headers=headers,
            )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"failed to request device code: HTTP {resp.status_code}: {resp.text}"
                )

            data = resp.json()
            # This endpoint uses non-standard 'device_auth_id' instead of 'device_code'
            # and often omits 'verification_uri'.
            device_auth_id = data.get("device_auth_id")
            if not device_auth_id:
                raise KeyError(f"'device_auth_id' missing from response. Body: {data}")

            user_code = data["user_code"]
            verification_uri = data.get("verification_uri", "https://auth.openai.com/codex/device")

            if organization_id:
                verification_uri += f"?organization={organization_id}"

            print(f"\n1. Open this URL: {verification_uri}")
            print(f"2. Enter this code: {user_code}")

            interval = int(data.get("interval", 5))

            print("\nWaiting for verification...", end="", flush=True)
            while True:
                time.sleep(interval)
                print(".", end="", flush=True)
                # Polling payload requires ONLY device_auth_id and user_code.
                token_resp = client.post(
                    "https://auth.openai.com/api/accounts/deviceauth/token",
                    json={
                        "device_auth_id": device_auth_id,
                        "user_code": user_code,
                    },
                    headers=headers,
                )


                if token_resp.status_code == 200:
                    data = token_resp.json()
                    authorization_code = data.get("authorization_code")
                    code_verifier = data.get("code_verifier")
                    if authorization_code and code_verifier:
                        print(" Verified!")
                        break
                    else:
                        print(" Failed.")
                        raise RuntimeError(
                            "deviceauth/token response missing authorization_code or code_verifier"
                        )

                if token_resp.status_code in (403, 404):
                    # Authorization pending, continue polling
                    continue

                print(" Failed.")
                err_data = token_resp.json()
                desc = err_data.get("error", {}).get("message", "no description")
                raise RuntimeError(f"token polling failed: {token_resp.status_code}: {desc}")

            # Exchange authorization_code for access_token
            print("Exchanging code for token...", end="", flush=True)
            oauth_resp = client.post(
                "https://auth.openai.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": authorization_code,
                    "redirect_uri": "https://auth.openai.com/deviceauth/callback",
                    "client_id": CLIENT_ID,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if oauth_resp.status_code != 200:
                print(" Failed.")
                raise RuntimeError(
                    f"token exchange failed: HTTP {oauth_resp.status_code}: {oauth_resp.text}"
                )

            print(" Done!")
            return oauth_resp.json()
