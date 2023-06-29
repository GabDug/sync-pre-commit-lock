# sync-pre-commit-lock

[![Tests](https://github.com/GabDug/sync-pre-commit-lock/actions/workflows/ci.yml/badge.svg)](https://github.com/GabDug/sync-pre-commit-lock/actions/workflows/ci.yml)
[![pypi version](https://img.shields.io/pypi/v/sync-pre-commit-lock.svg)](https://pypi.org/project/sync-pre-commit-lock/)
[![License](https://img.shields.io/pypi/l/sync-pre-commit-lock.svg)](https://pypi.python.org/pypi/sync-pre-commit-lock)
[![Python version](https://img.shields.io/pypi/pyversions/sync-pre-commit-lock.svg)](https://pypi.python.org/pypi/sync-pre-commit-lock)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/GabDug/sync-pre-commit-lock/main.svg?badge_token=PzBISUnvTEeYahD7i22qiA)](https://results.pre-commit.ci/latest/github/GabDug/sync-pre-commit-lock/main?badge_token=PzBISUnvTEeYahD7i22qiA)
[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
[![Ruff](https://img.shields.io/badge/ruff-lint-red)](https://github.com/charliermarsh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


PDM plugin to sync your pre-commit versions with your lockfile.

## TODO

- [ ] Add tests
- [ ] Add CI
- [ ] Add docs
- [ ] Add badges
- [ ] Add pre-commit hook to run linting
- [ ] Create a more verbose command
- [ ] Add support for poetry
- [ ] Add support for hatch
- [ ] Add support for flit
- [ ] Add CLI?
- [ ] Expose a pre-commit hook to sync the lockfile
- [ ] Support nested params for some repos? Like mypy types
- [ ] Support reading DB from python module?
- [ ] Support reordering DB inputs (file/global config/python module/cli
- [ ] Test using SSH/file dependencies
- [ ] Check ref existence before writing?


## Inspiration

This project is inspired by @floatingpurr's [sync_with_pdm](https://github.com/floatingpurr/sync_with_pdm/) and [sync_with_poetry](https://github.com/floatingpurr/sync_with_poetry/).
