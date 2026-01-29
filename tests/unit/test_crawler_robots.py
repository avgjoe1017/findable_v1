"""Tests for robots.txt parser."""

from worker.crawler.robots import RobotsParser, RobotsRule


class TestRobotsRule:
    """Tests for RobotsRule class."""

    def test_simple_path_match(self) -> None:
        """Test simple path matching."""
        rule = RobotsRule(path="/admin", allowed=False)
        assert rule.matches("/admin") is True
        assert rule.matches("/admin/users") is True
        assert rule.matches("/about") is False

    def test_wildcard_match(self) -> None:
        """Test wildcard pattern matching."""
        rule = RobotsRule(path="/page/*.html", allowed=False)
        assert rule.matches("/page/test.html") is True
        assert rule.matches("/page/other.html") is True
        assert rule.matches("/page/test.php") is False

    def test_end_anchor(self) -> None:
        """Test end anchor pattern."""
        rule = RobotsRule(path="/*.pdf$", allowed=False)
        assert rule.matches("/doc.pdf") is True
        assert rule.matches("/doc.pdf?query") is False


class TestRobotsParser:
    """Tests for RobotsParser class."""

    def test_empty_robots(self) -> None:
        """Test empty robots.txt allows all."""
        parser = RobotsParser.parse("")
        assert parser.is_allowed("/any/path") is True

    def test_disallow_all(self) -> None:
        """Test disallow all directive."""
        content = """
User-agent: *
Disallow: /
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/") is False
        assert parser.is_allowed("/any/path") is False

    def test_allow_all(self) -> None:
        """Test allow all directive."""
        content = """
User-agent: *
Disallow:
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/any/path") is True

    def test_specific_disallow(self) -> None:
        """Test specific path disallow."""
        content = """
User-agent: *
Disallow: /admin
Disallow: /private
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/admin") is False
        assert parser.is_allowed("/admin/users") is False
        assert parser.is_allowed("/private") is False
        assert parser.is_allowed("/public") is True

    def test_allow_override(self) -> None:
        """Test allow overriding disallow."""
        content = """
User-agent: *
Disallow: /admin
Allow: /admin/public
"""
        parser = RobotsParser.parse(content)
        # More specific rule wins
        assert parser.is_allowed("/admin") is False
        assert parser.is_allowed("/admin/public") is True
        assert parser.is_allowed("/admin/private") is False

    def test_crawl_delay(self) -> None:
        """Test crawl delay parsing."""
        content = """
User-agent: *
Crawl-delay: 2.5
"""
        parser = RobotsParser.parse(content)
        assert parser.crawl_delay == 2.5

    def test_sitemaps(self) -> None:
        """Test sitemap parsing."""
        content = """
User-agent: *
Disallow: /admin

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-news.xml
"""
        parser = RobotsParser.parse(content)
        assert len(parser.sitemaps) == 2
        assert "https://example.com/sitemap.xml" in parser.sitemaps

    def test_user_agent_specific(self) -> None:
        """Test user-agent specific rules."""
        content = """
User-agent: Googlebot
Disallow: /google-only

User-agent: *
Disallow: /admin
"""
        # Default user agent
        parser = RobotsParser.parse(content, user_agent="FindableBot")
        assert parser.is_allowed("/google-only") is True
        assert parser.is_allowed("/admin") is False

    def test_comments_ignored(self) -> None:
        """Test comments are ignored."""
        content = """
# This is a comment
User-agent: *
Disallow: /admin  # inline comment
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/admin") is False

    def test_case_insensitive_directives(self) -> None:
        """Test case insensitive directive parsing."""
        content = """
USER-AGENT: *
DISALLOW: /admin
ALLOW: /admin/public
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/admin") is False
        assert parser.is_allowed("/admin/public") is True


class TestRobotsParserEdgeCases:
    """Edge case tests for RobotsParser."""

    def test_malformed_lines(self) -> None:
        """Test handling of malformed lines."""
        content = """
User-agent: *
This is not a valid directive
Disallow: /admin
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/admin") is False

    def test_query_string_in_path(self) -> None:
        """Test URL with query string."""
        content = """
User-agent: *
Disallow: /search
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/search?q=test") is False

    def test_unicode_paths(self) -> None:
        """Test unicode paths."""
        content = """
User-agent: *
Disallow: /über
"""
        parser = RobotsParser.parse(content)
        assert parser.is_allowed("/über") is False
