from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from sync_pre_commit_lock.pre_commit_config import PreCommitRepo

PRE_COMMIT_CONFIG_FILENAME: Final[str] = ".pre-commit-config.yaml"


class Printer(ABC):
    success_list_token: str

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

    def list_updated_packages(self, packages: dict[str, tuple[PreCommitRepo, str]]) -> None:
        raise NotImplementedError
