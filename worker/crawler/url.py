"""URL normalization and utilities for the crawler."""

import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

# File extensions to skip during crawling
SKIP_EXTENSIONS = frozenset(
    [
        # Images
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".bmp",
        ".tiff",
        # Documents
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Media
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".wav",
        # Archives
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        # Code/Data
        ".json",
        ".xml",
        ".csv",
        ".txt",
        ".log",
        # Other
        ".exe",
        ".dmg",
        ".apk",
        ".ipa",
    ]
)

# URL patterns to skip
SKIP_PATTERNS = [
    re.compile(r"/feed/?$", re.IGNORECASE),
    re.compile(r"/rss/?$", re.IGNORECASE),
    re.compile(r"/atom/?$", re.IGNORECASE),
    re.compile(r"\.(xml|json)$", re.IGNORECASE),
    re.compile(r"/wp-admin/", re.IGNORECASE),
    re.compile(r"/wp-includes/", re.IGNORECASE),
    re.compile(r"/wp-content/uploads/", re.IGNORECASE),
    re.compile(r"/cdn-cgi/", re.IGNORECASE),
    re.compile(r"#.*$"),  # Fragment identifiers
]

# Query parameters to strip (tracking, session, etc.)
STRIP_PARAMS = frozenset(
    [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "msclkid",
        "dclid",
        "ref",
        "source",
        "mc_cid",
        "mc_eid",
        "_ga",
        "_gl",
        "_hsenc",
        "_hsmi",
        "sessionid",
        "sid",
        "session",
    ]
)


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """
    Normalize a URL for consistent comparison and storage.

    Args:
        url: The URL to normalize
        base_url: Optional base URL for resolving relative URLs

    Returns:
        Normalized URL string or None if URL should be skipped
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    # Handle relative URLs
    if base_url and not url.startswith(("http://", "https://", "//")):
        url = urljoin(base_url, url)
    elif url.startswith("//"):
        url = "https:" + url

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    # Must have valid scheme and netloc
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None

    # Normalize scheme to https
    scheme = "https"

    # Normalize host (lowercase, remove www prefix for consistency)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    # Remove default ports
    if ":443" in host:
        host = host.replace(":443", "")
    if ":80" in host:
        host = host.replace(":80", "")

    # Normalize path
    path = parsed.path or "/"

    # Check for skip extensions
    path_lower = path.lower()
    for ext in SKIP_EXTENSIONS:
        if path_lower.endswith(ext):
            return None

    # Check for skip patterns
    for pattern in SKIP_PATTERNS:
        if pattern.search(url):
            return None

    # Remove trailing slash from non-root paths for consistency
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Normalize empty path to /
    if not path:
        path = "/"

    # Filter query parameters
    query = ""
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=False)
        # Remove tracking parameters
        filtered = {k: v for k, v in params.items() if k.lower() not in STRIP_PARAMS}
        if filtered:
            # Sort for consistency
            query = urlencode(sorted(filtered.items()), doseq=True)

    # Reconstruct URL without fragment
    normalized = urlunparse((scheme, host, path, "", query, ""))

    return normalized


def extract_domain(url: str) -> str | None:
    """Extract the domain from a URL."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        # Remove port
        if ":" in host:
            host = host.split(":")[0]
        return host if host else None
    except Exception:
        return None


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs have the same domain."""
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    return domain1 is not None and domain1 == domain2


def is_internal_url(url: str, base_domain: str) -> bool:
    """Check if a URL is internal to the base domain."""
    url_domain = extract_domain(url)
    if not url_domain:
        return False

    # Normalize base domain
    base = base_domain.lower()
    if base.startswith("www."):
        base = base[4:]

    # Exact match or subdomain
    return url_domain == base or url_domain.endswith("." + base)


def get_url_depth(url: str) -> int:
    """Get the depth of a URL based on path segments."""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            return 0
        return len(path.split("/"))
    except Exception:
        return 0
