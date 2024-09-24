from pathlib import Path

import pytest

try:
    import pdm  # noqa: F401
except ImportError:
    pass
else:
    pytest_plugins = [
        "pdm.pytest",
    ]


@pytest.fixture
def fixtures() -> Path:
    return Path(__file__).parent.joinpath("fixtures")
