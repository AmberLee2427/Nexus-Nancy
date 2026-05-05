# Plugin Template

This is a template for creating pip-installable plugins (Option A) for Nexus-Nancy.

## Two Ways to Use

### Option 1: Cookiecutter (Recommended)
```bash
pip install cookiecutter
cookiecutter https://github.com/AmberLee2427/Nexus-Nancy.git --directory extras/templates/plugin
```

This will prompt for:
- `name` - Plugin name (e.g., `chat-reloader`)
- `description` - One-line description
- `author` - Your name
- `email` - Your email

### Option 2: Manual Copy
```bash
cp -r extras/templates/plugin my-plugin-name
# Then edit files to replace TEMPLATE with your name
```

## Structure

```
nancy-{name}/
├── .github/workflows/
│   ├── ci.yml           # Runs tests on push/PR
│   └── release.yml      # Builds & publishes to PyPI on release
├── pyproject.toml       # Package config with entry point
├── src/
│   └── nancy_{name}/
│       ├── __init__.py  # Version
│       └── plugin.py    # register_tools() + handlers
├── cookiecutter.json    # Default values
└── README.md
```

## Development

```bash
# Install in editable mode
pip install -e .

# Verify it loads
nnancy doctor
```

Your plugin will be auto-discovered via the `nexus_nancy.plugins` entry point.

## CI/CD

- **CI** (ci.yml): Runs on every push/PR - installs nexus-nancy and verifies plugin loads
- **Release** (release.yml): Runs on GitHub release - builds wheel and publishes to PyPI

To enable PyPI publishing:
1. Set `PYPI_API_TOKEN` secret in your repo settings (or use trusted publishing)
2. Create a release on GitHub
3. The workflow will build and publish automatically

## Publishing to PyPI Manually

```bash
pip install build twine
python -m build
twine upload dist/*
```

## Naming Convention

Official Nancy plugins use the prefix `nancy-` (e.g., `nancy-chat-reloader`).

For more details, see Nancy docs: `docs/PLUGINS.md`