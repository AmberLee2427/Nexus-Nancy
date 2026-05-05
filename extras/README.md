# Nexus-Nancy Extras

Official extensions, tools, and templates for Nexus-Nancy.

## Terminology

| Term | Description |
|------|-------------|
| **Tool** | Single-file script for `.agents/tools/` (Option B) |
| **Plugin** | Pip-installable package with entry points (Option A) |
| **Extension** | Umbrella term for both |

## Tools (Local Scripts)

Located in `tools/` - copy directly to `.agents/tools/`.

### Available
- [chat-reloader](./tools/chat-reloader.py) - `/reload` command to restart conversation

### Installation
```bash
# Copy from repo
cp extras/tools/chat-reloader.py .agents/tools/

# Or from gist
curl -L -o .agents/tools/chat-reloader.py https://gist.github.com/.../raw/chat-reloader.py
```

## Plugins (Pip Installable)

Located in `plugins/` - each is a separate repo (submodule).

[See plugin repos →](./plugins/)

### Installation
```bash
pip install nancy-<plugin-name>
```

## Templates

For creating your own extensions:

- [Tool template](./templates/tool/) - Single-file for `.agents/tools/`
- [Plugin template](./templates/plugin/) - Pip-installable package

## Registry

### Pip Plugins
| Plugin | Description | Status |
|--------|-------------|--------|
| nancy-chat-reloader | /reload command | Coming soon |

### Local Tools
| Tool | Description |
|------|-------------|
| chat-reloader | Session restart command |

## Development

To add a new extension:

1. **Tool**: Create in `tools/` following the template, optionally share via gist
2. **Plugin**: Create in `plugins/` as separate repo, add as submodule, update this README

See `docs/PLUGINS.md` in the main repo for implementation details.