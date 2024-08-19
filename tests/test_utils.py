import pytest

from sync_pre_commit_lock.utils import normalize_git_url, url_diff


# Here are the test cases
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/username/repository/", "https://github.com/username/repository"),
        ("http://github.com:80/username/repository.git", "http://github.com/username/repository"),
        ("https://github.com:443/username/repository.git", "https://github.com/username/repository"),
        ("https://gitlab.com/username/repository.git", "https://gitlab.com/username/repository"),
        ("git://github.com/username/repository.git", "https://github.com/username/repository"),
        ("git://gitlab.com/username/repository.git", "https://gitlab.com/username/repository"),
        ("ssh://git@github.com:443/username/repository.git", "https://github.com/username/repository"),
        ("https://github.com/username/repository", "https://github.com/username/repository"),
        ("https://gitlab.com/username/repository", "https://gitlab.com/username/repository"),
        ("https://GITLAB.com/username/repository", "https://gitlab.com/username/repository"),
        2 * ("file:///path/to/repo.git",),
        2 * ("/path/to/repo.git",),
    ],
)
def test_normalize_git_url(url: str, expected: str) -> None:
    assert normalize_git_url(url) == expected


@pytest.mark.parametrize(
    "old,new,expected",
    [
        ("https://some.place", "https://some.place", "https://some.place"),
        ("https://some.old.place", "https://some.new.place", "https://some.{old -> new}.place"),
        ("https://some.place", "https://another.place", "https://{some -> another}.place"),
        ("https://some.place/old", "https://a.different/place", "https://{some.place/old -> a.different/place}"),
        ("https://some.place/old", "https://some.place/new", "https://some.place/{old -> new}"),
    ],
)
def test_url_diff(old: str, new: str, expected: str):
    assert url_diff(old, new) == expected
