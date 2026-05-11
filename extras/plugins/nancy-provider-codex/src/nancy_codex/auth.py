import json
import time
from pathlib import Path
import jwt
import httpx

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

class CodexAuth:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.secret_path = workspace_root / ".agents/secrets/codex.json"

    def run(self):
        print("\n--- Codex Authentication (Step 1: Discovery) ---")
        tokens = self._get_device_tokens()
        if not tokens: return
        
        claims = jwt.decode(tokens["id_token"], options={"verify_signature": False})
        auth_claim = claims.get("https://api.openai.com/auth", {})
        org_id = auth_claim.get("organization_id")
        account_id = auth_claim.get("chatgpt_account_id")

        if org_id:
            print(f"\nDetected Organization: {org_id}")
            print("Detected Account: {account_id}")
            print("\n--- Codex Authentication (Step 2: Scoped Token) ---")
            tokens = self._get_device_tokens(org_id)
            if not tokens: return

        self.secret_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "access_token": tokens["access_token"],
            "organization_id": org_id,
            "chatgpt_account_id": account_id,
            "updated_at": time.time()
        }
        self.secret_path.write_text(json.dumps(data, indent=2))
        print(f"\n[OK] Codex secrets saved to {self.secret_path}")
        return "Authentication successful."

    def _get_device_tokens(self, organization_id=None):
        headers = {
            "User-Agent": "Codex/0.129.0 (darwin; arm64)",
            "Accept": "application/json",
        }
        with httpx.Client() as client:
            resp = client.post(
                "https://auth.openai.com/api/accounts/deviceauth/usercode",
                data={"client_id": CLIENT_ID},
                headers=headers
            )
            
            if resp.status_code != 200:
                print(f"\nError requesting device code: HTTP {resp.status_code}")
                print(f"Response: {resp.text}")
                return None

            data = resp.json()
            verification_uri = data.get("verification_uri")
            if not verification_uri:
                print(f"\nError: 'verification_uri' missing from response. Keys: {list(data.keys())}")
                return None

            if organization_id:
                verification_uri += f"?organization={organization_id}"

            print(f"\n1. Open this URL: {verification_uri}")
            print(f"2. Enter this code: {data['user_code']}")

            interval = data.get("interval", 5)
            device_code = data["device_code"]
            
            print("\nWaiting for verification...", end="", flush=True)
            while True:
                time.sleep(interval)
                print(".", end="", flush=True)
                token_resp = client.post(
                    "https://auth.openai.com/api/accounts/deviceauth/token",
                    data={"client_id": CLIENT_ID, "device_code": device_code},
                    headers=headers
                ).json()

                if "access_token" in token_resp:
                    print(" Done!")
                    return token_resp
                if token_resp.get("error") != "authorization_pending":
                    print(f"\nError: {token_resp.get('error_description', 'Unknown error')}")
                    return None
