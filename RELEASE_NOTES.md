# Gulls v1.0.2 Release Notes

**Release Date:** 2026-05-04

## Patch Release


### Changed
- Expanded CLI help text to comprehensively list all available interactive chat commands (`/copy`, `/config`, `/key`, `/quit`, etc.).

### Fixed
- Fixed a 404 error during `nnancy auth login` caused by an incorrect OpenAI Auth0 domain (`auth0.openai.com` -> `auth.openai.com`).
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

**Previous Release:** v1.0.1