"""Tests for URL normalization and utilities."""

from worker.crawler.url import (
    extract_domain,
    get_url_depth,
    is_internal_url,
    is_same_domain,
    normalize_url,
)


class TestNormalizeUrl:
    """Tests for normalize_url function."""

    def test_basic_normalization(self) -> None:
        """Test basic URL normalization."""
        assert normalize_url("http://example.com") == "https://example.com/"
        assert normalize_url("https://example.com/") == "https://example.com/"
        assert normalize_url("https://example.com/page") == "https://example.com/page"

    def test_removes_www(self) -> None:
        """Test www prefix removal."""
        assert normalize_url("https://www.example.com") == "https://example.com/"
        assert normalize_url("http://www.example.com/page") == "https://example.com/page"

    def test_removes_trailing_slash(self) -> None:
        """Test trailing slash removal from non-root paths."""
        assert normalize_url("https://example.com/page/") == "https://example.com/page"
        assert normalize_url("https://example.com/") == "https://example.com/"  # Root keeps slash

    def test_removes_default_ports(self) -> None:
        """Test default port removal."""
        assert normalize_url("https://example.com:443/page") == "https://example.com/page"
        assert normalize_url("http://example.com:80/page") == "https://example.com/page"

    def test_strips_tracking_params(self) -> None:
        """Test tracking parameter removal."""
        url = "https://example.com/page?utm_source=google&id=123"
        result = normalize_url(url)
        assert result is not None
        assert "utm_source" not in result
        assert "id=123" in result

    def test_strips_fragment(self) -> None:
        """Test fragment removal."""
        # Fragment-only links are skipped
        assert normalize_url("#section") is None

    def test_skips_non_html_extensions(self) -> None:
        """Test skipping non-HTML files."""
        assert normalize_url("https://example.com/image.jpg") is None
        assert normalize_url("https://example.com/doc.pdf") is None
        assert normalize_url("https://example.com/data.json") is None

    def test_skips_feed_urls(self) -> None:
        """Test skipping feed URLs."""
        assert normalize_url("https://example.com/feed/") is None
        assert normalize_url("https://example.com/rss") is None

    def test_relative_urls(self) -> None:
        """Test relative URL resolution."""
        base = "https://example.com/page/"
        assert normalize_url("../other", base) == "https://example.com/other"
        assert normalize_url("/absolute", base) == "https://example.com/absolute"
        assert normalize_url("relative", base) == "https://example.com/page/relative"

    def test_protocol_relative_urls(self) -> None:
        """Test protocol-relative URLs."""
        assert normalize_url("//example.com/page") == "https://example.com/page"

    def test_invalid_urls(self) -> None:
        """Test invalid URL handling."""
        assert normalize_url("") is None
        assert normalize_url("   ") is None
        assert normalize_url("javascript:void(0)") is None
        assert normalize_url("mailto:test@example.com") is None


class TestExtractDomain:
    """Tests for extract_domain function."""

    def test_extract_domain(self) -> None:
        """Test domain extraction."""
        assert extract_domain("https://example.com/page") == "example.com"
        assert extract_domain("https://www.example.com") == "example.com"
        assert extract_domain("https://sub.example.com") == "sub.example.com"

    def test_removes_port(self) -> None:
        """Test port removal."""
        assert extract_domain("https://example.com:8080/page") == "example.com"


class TestIsSameDomain:
    """Tests for is_same_domain function."""

    def test_same_domain(self) -> None:
        """Test same domain detection."""
        assert is_same_domain("https://example.com/page1", "https://example.com/page2") is True

    def test_different_domain(self) -> None:
        """Test different domain detection."""
        assert is_same_domain("https://example.com", "https://other.com") is False

    def test_with_www(self) -> None:
        """Test www handling."""
        assert is_same_domain("https://www.example.com", "https://example.com") is True


class TestIsInternalUrl:
    """Tests for is_internal_url function."""

    def test_internal_url(self) -> None:
        """Test internal URL detection."""
        assert is_internal_url("https://example.com/page", "example.com") is True
        assert is_internal_url("https://www.example.com/page", "example.com") is True

    def test_subdomain_is_internal(self) -> None:
        """Test subdomain as internal."""
        assert is_internal_url("https://blog.example.com/post", "example.com") is True
        assert is_internal_url("https://shop.example.com", "example.com") is True

    def test_external_url(self) -> None:
        """Test external URL detection."""
        assert is_internal_url("https://other.com/page", "example.com") is False
        assert is_internal_url("https://example.org", "example.com") is False


class TestGetUrlDepth:
    """Tests for get_url_depth function."""

    def test_root_depth(self) -> None:
        """Test root URL depth."""
        assert get_url_depth("https://example.com") == 0
        assert get_url_depth("https://example.com/") == 0

    def test_path_depth(self) -> None:
        """Test path depth calculation."""
        assert get_url_depth("https://example.com/page") == 1
        assert get_url_depth("https://example.com/page/sub") == 2
        assert get_url_depth("https://example.com/a/b/c/d") == 4
