# AGENTS.md

## Cursor Cloud specific instructions

`sync-pre-commit-lock` is a pure Python library/plugin (a PDM/Poetry plugin plus a
standalone `sync-pre-commit-uv` CLI). There are **no long-running services, web
servers, or databases** — "running the app" means running the CLI/plugin against a
project's lockfile + `.pre-commit-config.yaml`, and "end-to-end testing" means the
pytest suite.

Dependencies are managed with **PDM** and installed into the project `.venv` by the
startup update script (`pdm install -G :all --dev`). PDM is installed to
`~/.local/bin`, which is added to `PATH` via `~/.bashrc`.

### Lint / type-check / test / build (see `pyproject.toml` `[tool.pdm.scripts]`)
- Lint: `pdm run lint-ruff` (ruff check) and `pdm run fmt` / `pdm run ruff format --check .`
- Type-check: `pdm run lint-mypy` (mypy strict, `src/` only)
- Test: `pdm run test` (pytest) — or `pdm run test-cov` for coverage
- Full matrix (optional, slow, needs network + multiple Python versions): `pdm run test-all` (tox)
- Build: `pdm build`

### Non-obvious gotchas
- **`NO_COLOR` / `FORCE_COLOR` env vars break 3 color tests.** The Cloud VM sets
  `NO_COLOR=1` and `FORCE_COLOR=0` in the ambient environment. Because `use_color()`
  honors `NO_COLOR`, three tests in `tests/test_shell_printer.py`
  (`test_enable_colors_on_tty[True]`, `test_force_color[True]`, `test_force_color[False]`)
  fail unless those vars are unset. Run the suite with them unset to get a clean pass:
  `env -u NO_COLOR -u FORCE_COLOR pdm run test`. This is an environment quirk, not a
  code bug — do not "fix" it in source.
- The plugin installs itself editable via `[tool.pdm] plugins = ["-e ."]`, so `src/`
  changes are picked up without reinstalling.
- To try the plugin manually, copy a fixture project (e.g. `tests/fixtures/uv_project/`,
  which has a `uv.lock` pinning `ruff` and a stale `.pre-commit-config.yaml`) to a temp
  dir and run `.venv/bin/sync-pre-commit-uv` in it; it rewrites the config's `rev` to
  match the lockfile. Supports `--dry-run`.
