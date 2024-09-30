import sys
from typing import TypedDict

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


class RepoInfo(TypedDict):
    repo: str
    rev: str


PackageRepoMapping: TypeAlias = dict[str, RepoInfo]

DEPENDENCY_MAPPING: PackageRepoMapping = {
    "autopep8": {
        "repo": "https://github.com/hhatto/autopep8",
        "rev": "v${rev}",
    },
    "bandit": {
        "repo": "https://github.com/PyCQA/bandit",
        "rev": "${rev}",
    },
    "black": {
        "repo": "https://github.com/psf/black-pre-commit-mirror",
        "rev": "${rev}",
    },
    "check-jsonschema": {
        "repo": "https://github.com/python-jsonschema/check-jsonschema",
        "rev": "${rev}",
    },
    "codespell": {
        "repo": "https://github.com/codespell-project/codespell",
        "rev": "v${rev}",
    },
    "commitizen": {
        "repo": "https://github.com/commitizen-tools/commitizen",
        "rev": "v${rev}",
    },
    "djade": {
        "repo": "https://github.com/adamchainz/djade-pre-commit",
        "rev": "${rev}",
    },
    "djhtml": {
        "repo": "https://github.com/rtts/djhtml",
        "rev": "${rev}",
    },
    "docformatter": {
        "repo": "https://github.com/PyCQA/docformatter",
        "rev": "${rev}",
    },
    "flake8": {
        "repo": "https://github.com/pycqa/flake8",
        "rev": "${rev}",
    },
    "flakeheaven": {
        "repo": "https://github.com/flakeheaven/flakeheaven",
        "rev": "${rev}",
    },
    "isort": {
        "repo": "https://github.com/pycqa/isort",
        "rev": "${rev}",
    },
    "mypy": {
        "repo": "https://github.com/pre-commit/mirrors-mypy",
        "rev": "v${rev}",
    },
    "pdm": {
        "repo": "https://github.com/pdm-project/pdm",
        "rev": "${rev}",
    },
    "poetry": {
        "repo": "https://github.com/python-poetry/poetry",
        "rev": "${rev}",
    },
    "pycln": {
        "repo": "https://github.com/hadialqattan/pycln",
        "rev": "v${rev}",
    },
    "pyroma": {
        "repo": "https://github.com/regebro/pyroma",
        "rev": "${rev}",
    },
    "pyupgrade": {
        "repo": "https://github.com/asottile/pyupgrade",
        "rev": "v${rev}",
    },
    "rtscheck": {
        "repo": "https://github.com/rstcheck/rstcheck",
        "rev": "v${rev}",
    },
    "ruff": {
        "repo": "https://github.com/astral-sh/ruff-pre-commit",
        "rev": "v${rev}",
    },
    "yamllint": {
        "repo": "https://github.com/adrienverge/yamllint",
        "rev": "v${rev}",
    },
}

REPOSITORY_ALIASES: dict[str, tuple[str, ...]] = {
    "https://github.com/astral-sh/ruff-pre-commit": ("https://github.com/charliermarsh/ruff-pre-commit",),
    "https://github.com/psf/black-pre-commit-mirror": ("https://github.com/psf/black",),
    "https://github.com/hhatto/autopep8": ("https://github.com/pre-commit/mirrors-autopep8",),
}
