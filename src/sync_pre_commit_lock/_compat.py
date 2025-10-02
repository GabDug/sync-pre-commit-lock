# ruff: noqa: F401
try:
    # 3.11+
    import tomllib as toml  # type: ignore[import,unused-ignore]
except ImportError:
    import tomli as toml  # type: ignore[no-redef,unused-ignore]

__all__ = ["toml"]
