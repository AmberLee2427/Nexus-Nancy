# Gulls v1.1.1 Release Notes

**Release Date:** 2026-05-04

## Patch Release


### Added
- New `nnancy secrets` command to securely open and edit the API key file (`.agents/secrets/openai.key`). This provides a discoverable way to add an API key before first run.

### Changed
- [Add changes here]

### Fixed
- Fix: Resolved a failing test in the Windows CI matrix. The test `test_native_route_executes_native_tool_call_and_returns_plain_response` had an incorrect assertion checking for temporary directory paths in the tool output.

### Security
- [Add security fixes here]
## What's New

This release includes the following changes:

## What's Included

- **Source code**: Complete Gulls source with CMake build system
- **Binaries**: Linux executables (GSL fallbacks - testing only)
- **Documentation**: Built HTML documentation
- **Smoke test plots**: Visual proof that the release works

## Getting Started

1. **Install Gulls** - See the [Installation Guide](https://gulls.readthedocs.io/en/latest/install_gulls.html)
2. **Validate your inputs** - Use `python scripts/validate_inputs.py your_file.prm`
3. **Run simulations** - See the [Running Guide](https://gulls.readthedocs.io/en/latest/run_simulations.html)

## Full Changelog

See [CHANGELOG.md](CHANGELOG.md) for the complete list of changes.

---

**Previous Release:** v1.1.0