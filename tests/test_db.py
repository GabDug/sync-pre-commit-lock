from sync_pre_commit_lock.db import DEPENDENCY_MAPPING
from sync_pre_commit_lock.utils import normalize_git_url


def test_all_urls_already_normalized() -> None:
    for repos in DEPENDENCY_MAPPING.values():
        assert normalize_git_url(repos["repo"]) == repos["repo"]
