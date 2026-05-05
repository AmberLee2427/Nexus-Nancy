# Tool Template

This is a template for creating local tools (Option B) that can be dropped directly into your workspace.

## Quick Start

### Option 1: From Gist (Recommended)
```bash
curl -L -o .agents/tools/mytool.py https://gist.github.com/f53f93730cc25b54dbaa66f8cb6ed8b3/raw/template.py
```

### Option 2: From This Repo
```bash
cp template.py /path/to/your/workspace/.agents/tools/mytool.py
```

Then edit the file to add your tool functionality and verify:
```bash
nnancy doctor
```

## View Embedded

<script src="https://gist.github.com/f53f93730cc25b54dbaa66f8cb6ed8b3.js"></script>

## Gist Workflow

To share tools via gist:

1. Create a public gist with your `.py` file
2. Get the raw URL: `https://gist.github.com/USER/ID/raw/filename.py`
3. Users install with:
   ```bash
   curl -L -o .agents/tools/mytool.py https://gist.github.com/USER/ID/raw/filename.py
   ```

## Structure

```
.agents/tools/
└── mytool.py        # Single file with register_tools() function
```

## Requirements

- The file must define a `register_tools()` function that returns a list of `ToolDefinition` objects
- The file must be importable (no syntax errors)
- Handler functions must be callable and return strings

For more details, see Nancy docs: `docs/PLUGINS.md`