"""Robots.txt parser and handler."""

import contextlib
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

try:
    import structlog

    logger = structlog.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


@dataclass
class RobotsRule:
    """A single robots.txt rule."""

    path: str
    allowed: bool

    def matches(self, url_path: str) -> bool:
        """Check if this rule matches a URL path."""
        # Handle wildcard patterns
        if "*" in self.path:
            pattern = self.path.replace("*", ".*")
            pattern = pattern[:-1] + "$" if self.path.endswith("$") else "^" + pattern
            try:
                return bool(re.match(pattern, url_path))
            except re.error:
                return url_path.startswith(self.path.replace("*", ""))
        else:
            return url_path.startswith(self.path)


@dataclass
class RobotsParser:
    """Parser for robots.txt files."""

    rules: list[RobotsRule] = field(default_factory=list)
    crawl_delay: float | None = None
    sitemaps: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, content: str, user_agent: str = "*") -> "RobotsParser":
        """
        Parse robots.txt content.

        Args:
            content: The robots.txt file content
            user_agent: The user agent to match rules for

        Returns:
            RobotsParser instance with parsed rules
        """
        parser = cls()
        current_agents: list[str] = []
        applies_to_us = False

        # Normalize user agent for matching
        ua_lower = user_agent.lower()
        ua_name = ua_lower.split("/")[0] if "/" in ua_lower else ua_lower

        for line in content.split("\n"):
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse directive
            if ":" not in line:
                continue

            directive, _, value = line.partition(":")
            directive = directive.strip().lower()
            # Strip inline comments
            if "#" in value:
                value = value.split("#")[0]
            value = value.strip()

            if directive == "user-agent":
                # New user-agent block
                if current_agents and not value:
                    current_agents = []
                    applies_to_us = False
                else:
                    current_agents.append(value.lower())
                    # Check if this applies to our bot
                    if value == "*" or ua_name in value.lower():
                        applies_to_us = True

            elif directive == "disallow" and applies_to_us:
                if value:  # Empty disallow means allow all
                    parser.rules.append(RobotsRule(path=value, allowed=False))

            elif directive == "allow" and applies_to_us:
                if value:
                    parser.rules.append(RobotsRule(path=value, allowed=True))

            elif directive == "crawl-delay" and applies_to_us:
                with contextlib.suppress(ValueError):
                    parser.crawl_delay = float(value)

            elif directive == "sitemap" and value.startswith("http"):
                parser.sitemaps.append(value)

        return parser

    def is_allowed(self, url: str) -> bool:
        """
        Check if a URL is allowed to be crawled.

        Args:
            url: The URL to check

        Returns:
            True if crawling is allowed, False otherwise
        """
        try:
            parsed = urlparse(url)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
        except Exception:
            return True  # Allow on parse error

        # Check rules in order (more specific rules take precedence)
        # Sort by path length descending for specificity
        sorted_rules = sorted(self.rules, key=lambda r: len(r.path), reverse=True)

        for rule in sorted_rules:
            if rule.matches(path):
                return rule.allowed

        # Default: allow if no rule matches
        return True


class RobotsChecker:
    """Checker for robots.txt compliance."""

    def __init__(
        self,
        user_agent: str,
        timeout: float = 10.0,
        respect_robots: bool = True,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.respect_robots = respect_robots
        self._cache: dict[str, RobotsParser] = {}

    async def _fetch_robots(self, base_url: str) -> RobotsParser:
        """Fetch and parse robots.txt for a domain."""
        robots_url = urljoin(base_url, "/robots.txt")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    return RobotsParser.parse(response.text, self.user_agent)
                else:
                    # No robots.txt or error - allow all
                    return RobotsParser()

        except Exception as e:
            logger.warning(
                "robots_fetch_failed",
                url=robots_url,
                error=str(e),
            )
            # On error, allow crawling
            return RobotsParser()

    def _get_base_url(self, url: str) -> str:
        """Get the base URL for robots.txt lookup."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def is_allowed(self, url: str) -> bool:
        """
        Check if crawling a URL is allowed by robots.txt.

        Args:
            url: The URL to check

        Returns:
            True if allowed, False if disallowed
        """
        if not self.respect_robots:
            return True

        base_url = self._get_base_url(url)

        # Check cache
        if base_url not in self._cache:
            self._cache[base_url] = await self._fetch_robots(base_url)

        return self._cache[base_url].is_allowed(url)

    def get_crawl_delay(self, url: str) -> float | None:
        """Get the crawl delay for a domain if specified."""
        base_url = self._get_base_url(url)
        if base_url in self._cache:
            return self._cache[base_url].crawl_delay
        return None

    def get_sitemaps(self, url: str) -> list[str]:
        """Get sitemaps listed in robots.txt for a domain."""
        base_url = self._get_base_url(url)
        if base_url in self._cache:
            return self._cache[base_url].sitemaps
        return []
