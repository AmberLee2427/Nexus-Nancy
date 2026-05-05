# Plugin Template

This is a template for creating pip-installable plugins (Option A) for Nexus-Nancy.

## Quick Start

1. Rename `nancy-TEMPLATE` to your plugin name in `pyproject.toml`
2. Rename `src/nancy_TEMPLATE/` directory to match
3. Update entry point in `pyproject.toml` (e.g., `mytool = "nancy_mytool.plugin"`)
4. Edit `plugin.py` to add your tool functionality

## Installation

```bash
# From the plugin directory
pip install .

# Or in editable mode for development
pip install -e .
```

## Verification

```bash
nnancy doctor
```

You should see your plugin listed in the tools count.

## Structure

```
nancy-TEMPLATE/
├── pyproject.toml              # Package config with entry point
├── src/
│   └── nancy_TEMPLATE/
│       ├── __init__.py         # Version
│       └── plugin.py           # register_tools() + handlers
└── README.md
```

## Publishing to PyPI

1. Update `pyproject.toml` with your details (author, description, etc.)
2. Build: `pip install build && python -m build`
3. Upload: `pip install twine && twine upload dist/*`

## Naming Convention

Official Nancy plugins use the prefix `nancy-` (e.g., `nancy-chat-reloader`).

For more details, see Nancy docs: `docs/PLUGINS.md`