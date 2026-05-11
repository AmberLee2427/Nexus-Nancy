import json
import httpx
from pathlib import Path

path = Path(".agents/secrets/codex.json")
if not path.exists():
    path = Path("/Users/malpas.1/Code/Nexus-Nancy/.agents/secrets/codex.json")
    if not path.exists():
        print("No codex.json found")
        exit(1)

data = json.loads(path.read_text())
token = data.get("access_token")
account_id = data.get("chatgpt_account_id")
org_id = data.get("organization_id")

headers = {
    "Authorization": f"Bearer {token}",
    "chatgpt-account-id": account_id,
    "openai-organization": org_id,
    "user-agent": "Codex/0.129.0 (darwin; arm64)",
    "x-openai-client-id": "app_EMoamEEZ73f0CkXaXp7hrann"
}

# The search result mentioned https://chatgpt.com/backend-api/models
url = "https://chatgpt.com/backend-api/models"

with httpx.Client() as client:
    r = client.get(url, headers=headers)
    print(f"Status: {r.status_code}")
    try:
        models = r.json()
        print(json.dumps(models, indent=2))
    except:
        print(r.text)
