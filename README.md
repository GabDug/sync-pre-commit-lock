# sync-pre-commit-lock

[![Tests](https://github.com/GabDug/sync-pre-commit-lock/actions/workflows/ci.yml/badge.svg)](https://github.com/GabDug/sync-pre-commit-lock/actions/workflows/ci.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/GabDug/sync-pre-commit-lock/main.svg)](https://results.pre-commit.ci/latest/github/GabDug/sync-pre-commit-lock/main)
[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/7529/badge)](https://bestpractices.coreinfrastructure.org/projects/7529)
[![pypi version](https://img.shields.io/pypi/v/sync-pre-commit-lock.svg)](https://pypi.org/project/sync-pre-commit-lock/)
[![License](https://img.shields.io/pypi/l/sync-pre-commit-lock.svg)](https://pypi.python.org/pypi/sync-pre-commit-lock)
[![Python version](https://img.shields.io/pypi/pyversions/sync-pre-commit-lock.svg)](https://pypi.python.org/pypi/sync-pre-commit-lock)
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

Optionally, you can also specify [the plugin in your project](https://pdm.fming.dev/latest/dev/write/#specify-the-plugins-in-project) `pyproject.toml`, to make it installable with `pdm install --plugins`:

```toml
[tool.pdm]
plugins = [
    "sync-pre-commit-lock[pdm]"
]
```

> We add the extra group `[pdm]` to the plugin name, to make sure version constraints are met.

### For Poetry

Install like any other Poetry plugin, but beware that it's still in development!

## Configuration

This plugin is configured using the `tool.sync-pre-commit-lock` section in your `pyproject.toml` file.

Here is the default configuration:

```toml
[tool.sync-pre-commit-lock]
# Run `pre-commit install` automatically if applicable
automaticall-install-hooks = true
# Should we sync your pre-commit versions with your lockfile (when running lock, add, update, remove, etc.)?
disable-sync-from_lock = false
# Packages to ignore when syncing from lock
ignore = []
# Name of the pre-commit config file to sync with
pre-commit-config-file = "pre-commit-config.yaml"
# Additional mapping of URLs to python packages
# Default is empty, but will merge with the default mapping
# "rev" indicates the format of the Git tags
dependency-mapping = {"package-name"= {"repo"= "https://github.com/example/package-name", "rev"= "v${rev}"}}
```

> Note: the `dependency-mapping` is merged with the default mapping, so you don't need to specify the default mapping if you want to add a new mapping.
> Repos urls will be normalized to http(s), with the trailing slash removed.

## Usage

Once installed, and optionally configured, the plugin usage should be transparent, and trigger when you run applicable PDM or Poetry commands.

There should be a message in the output, when the sync or install or pre-commit is triggered.

## Improvement ideas

Feel free to open an issue or a PR if you have any idea, or if you want to help!

### Release / CI / Dev

- [ ] Upload build artifacts on GitHub release
- [ ] Add a changelog
- [ ] Add "E2E" tests
- [ ] Add PDM scripts for dev and CI
- [ ] Add docs

### Features or fixes

- [ ] Create a more verbose command
- [ ] Add support for other lockfiles / project managers (pipenv, flit, hatch, etc.)
- [ ] Add a dedicated CLI command to manage sync/install
- [ ] Expose a pre-commit hook to sync the lockfile
- [ ] Support nested params for some repos? Like mypy types
- [ ] Support reading DB from a Python module?
- [ ] Support reordering DB inputs (file/global config/python module/cli)?
- [ ] Test using SSH/file dependencies?
- [ ] Check ref existence before writing?
- [ ] Support multiple hooks repos for the same dependency?
- [ ] New feature to convert from pre-commit online to local?
- [ ] Warning if pre-commit CI auto update is also set?

## Inspiration

This project is inspired by @floatingpurr's [sync_with_pdm](https://github.com/floatingpurr/sync_with_pdm/) and [sync_with_poetry](https://github.com/floatingpurr/sync_with_poetry/).

The code to install pre-commit hooks automatically is **adapted** from @vstrimaitis's [poetry-pre-commit-plugin](https://github.com/vstrimaitis/poetry-pre-commit-plugin/), licensed under GPL-3.
