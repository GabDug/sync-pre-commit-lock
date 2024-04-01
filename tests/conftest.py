try:
    import pdm  # noqa: F401
except ImportError:
    pass
else:
    pytest_plugins = [
        "pdm.pytest",
    ]
