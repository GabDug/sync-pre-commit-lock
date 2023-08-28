from urllib.parse import urlparse, urlunparse


def normalize_git_url(url: str) -> str:
    """Normalize a git URL to https://, remove .git from the end of the path, and lowercase the hostname.

    If the URL is malformed, return the original URL.
    """
    # Ignore local paths
    if "://" not in url:
        return url

    # Parse the URL
    parsed_url = urlparse(url)

    # Normalize the scheme: convert git, git+ssh, and ssh to https
    scheme = parsed_url.scheme
    if scheme in ["git", "git+ssh", "ssh"]:
        scheme = "https"

    # Lowercase the hostname and remove default port if it exists
    netloc = parsed_url.hostname.lower() if parsed_url.hostname else ""

    # If netloc is empty (git, ssh URLs), then path contains it.
    if not netloc:
        return url  # malformed URL, we can't normalize it

    path = parsed_url.path

    # Remove .git from the end of path if it's there
    if path.endswith(".git"):
        path = path[:-4]

    # Reconstruct the URL
    normalized_url = urlunparse((scheme, netloc, path, None, None, None))

    if normalized_url.endswith("/"):
        normalized_url = normalized_url[:-1]

    return normalized_url
