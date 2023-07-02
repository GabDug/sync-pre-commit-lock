# sync-pre-commit-lock

[![Tests](https://github.com/GabDug/sync-pre-commit-lock/actions/workflows/ci.yml/badge.svg)](https://github.com/GabDug/sync-pre-commit-lock/actions/workflows/ci.yml)
[![pypi version](https://img.shields.io/pypi/v/sync-pre-commit-lock.svg)](https://pypi.org/project/sync-pre-commit-lock/)
[![License](https://img.shields.io/pypi/l/sync-pre-commit-lock.svg)](https://pypi.python.org/pypi/sync-pre-commit-lock)
[![Python version](https://img.shields.io/pypi/pyversions/sync-pre-commit-lock.svg)](https://pypi.python.org/pypi/sync-pre-commit-lock)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/GabDug/sync-pre-commit-lock/main.svg)](https://results.pre-commit.ci/latest/github/GabDug/sync-pre-commit-lock/main)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![Ruff](https://img.shields.io/badge/ruff-lint-red)](https://github.com/charliermarsh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

PDM and Poetry plugin to sync your pre-commit versions with your lockfile and automatically install pre-commit hooks.

## Features

- 🔁 Sync pre-commit versions with your lockfile
- ⏩ Run every time you run the lockfile is updated, not as a pre-commit hook
- 🔄 Install pre-commit hooks automatically, no need to run `pre-commit install` manually

## Supported versions

- Python 3.10+
- PDM 2.7.4+
- Poetry 1.6.0+ (currently in development)

## Installation

### For PDM

Install it [just like any other PDM plugin](https://pdm.fming.dev/latest/dev/write/#activate-the-plugin):

```bash
pdm self add "sync-pre-commit-lock[pdm]""
```

Optionally, you can also specify [the plugin in your project](https://pdm.fming.dev/latest/dev/write/#specify-the-plugins-in-project) `pyproject.toml`, to share it with your team:

```toml
[tool.pdm]
plugins = [
    "sync-pre-commit-lock[pdm]"
]
```

> We add the extra group `[pdm]` to the plugin name, to make sure version constraints are met.

### For Poetry

Install like any other Poetry plugin, but beware that it's still in development!

## TODO

- [X] Add tests
- [X] Add "E2E" tests
- [X] Add CI (mypy, testing)
- [ ] Add PDM scripts for dev and CI
- [ ] Add CD (automated releases)
- [ ] Add docs
- [X] Add badges
- [X] Add pre-commit hook to run linting
- [ ] Create a more verbose command
- [X] Add support for poetry
- [ ] Add support for hatch
- [ ] Add support for flit
- [ ] Add CLI?
- [ ] Expose a pre-commit hook to sync the lockfile
- [ ] Support nested params for some repos? Like mypy types
- [ ] Support reading DB from python module?
- [ ] Support reordering DB inputs (file/global config/python module/cli)
- [ ] Test using SSH/file dependencies
- [ ] Check ref existence before writing?
- [ ] Support multiple hooks repos for the same dependency?
- [X] Normalize the URL trailing slash
- [ ] New feature to convert from pre-commit online to local?

## Inspiration

This project is inspired by @floatingpurr's [sync_with_pdm](https://github.com/floatingpurr/sync_with_pdm/) and [sync_with_poetry](https://github.com/floatingpurr/sync_with_poetry/).

The code to install pre-commit hooks automatically is **adapted** from @vstrimaitis's [poetry-pre-commit-plugin](https://github.com/vstrimaitis/poetry-pre-commit-plugin/), licensed under GPL-3.
