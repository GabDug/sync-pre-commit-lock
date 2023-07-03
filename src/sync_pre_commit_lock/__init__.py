from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Final

PRE_COMMIT_CONFIG_FILENAME: Final[str] = ".pre-commit-config.yaml"


class Printer(ABC):
    @abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def debug(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def info(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def warning(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def error(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def success(self, msg: str) -> None:
        raise NotImplementedError
