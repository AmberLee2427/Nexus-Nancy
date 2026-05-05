# Tools (Local Scripts)

Single-file tools that can be dropped directly into `.agents/tools/`.

## Installation

### Option 1: From Gist (Recommended)
```bash
curl -L -o .agents/tools/chat-reloader.py https://gist.github.com/f53f93730cc25b54dbaa66f8cb6ed8b3/raw/chat-reloader.py
```

### Option 2: From This Repo
```bash
cp extras/tools/chat-reloader.py .agents/tools/
```

### Option 3: View Embedded

<script src="https://gist.github.com/f53f93730cc25b54dbaa66f8cb6ed8b3.js?file=chat-reloader.py"></script>

## Available Tools

### chat-reloader
Provides a `/reload` command to restart the current conversation.

**Usage in chat:**
```
/reload
/reload reason=context corrupted
```

**Verification:**
```bash
nnancy doctor
```

Look for "reload" in the tool list.

## Creating New Tools

Copy the template:
```bash
cp extras/templates/tool/template.py .agents/tools/mytool.py
```

Edit the file to add your functionality, then verify with `nnancy doctor`.