"""llms.txt detection and validation.

llms.txt is a new standard for helping LLMs efficiently discover and
understand website content. Similar to robots.txt but optimized for
AI inference rather than crawling rules.

Specification: https://llmstxt.org
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LlmsTxtLink:
    """A link extracted from llms.txt."""

    text: str
    url: str
    description: str | None = None

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "url": self.url,
            "description": self.description,
        }


@dataclass
class LlmsTxtResult:
    """Result of llms.txt detection and validation."""

    domain: str
    exists: bool
    url: str
    content: str | None = None
    quality_score: float = 0.0  # 0-100
    level: str = "missing"  # missing, poor, good, excellent

    # Structure analysis
    has_title: bool = False
    has_description: bool = False
    has_sections: bool = False
    has_links: bool = False

    # Extracted data
    title: str | None = None
    description: str | None = None
    sections: list[str] = field(default_factory=list)
    links: list[LlmsTxtLink] = field(default_factory=list)
    link_count: int = 0

    # Issues found
    issues: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "exists": self.exists,
            "url": self.url,
            "quality_score": round(self.quality_score, 2),
            "level": self.level,
            "has_title": self.has_title,
            "has_description": self.has_description,
            "has_sections": self.has_sections,
            "has_links": self.has_links,
            "title": self.title,
            "description": self.description,
            "sections": self.sections,
            "link_count": self.link_count,
            "links": [link.to_dict() for link in self.links],
            "issues": self.issues,
            "error": self.error,
        }


class LlmsTxtChecker:
    """Checks for and validates llms.txt files."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def check(self, url: str) -> LlmsTxtResult:
        """
        Check if a site has an llms.txt file and validate its structure.

        Args:
            url: Any URL on the site (will extract domain)

        Returns:
            LlmsTxtResult with existence, content, and quality score
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        base_url = f"{parsed.scheme}://{domain}"
        llms_txt_url = urljoin(base_url, "/llms.txt")

        result = LlmsTxtResult(
            domain=domain,
            exists=False,
            url=llms_txt_url,
        )

        try:
            content = await self._fetch_llms_txt(llms_txt_url)

            if content is None:
                result.exists = False
                result.level = "missing"
                result.quality_score = 0.0
                logger.info("llms_txt_not_found", domain=domain)
                return result

            result.exists = True
            result.content = content

            # Parse and validate
            self._parse_content(result, content)
            self._calculate_quality_score(result)

            logger.info(
                "llms_txt_found",
                domain=domain,
                quality_score=result.quality_score,
                level=result.level,
                link_count=result.link_count,
            )

        except Exception as e:
            result.error = str(e)
            logger.warning("llms_txt_check_error", domain=domain, error=str(e))

        return result

    async def _fetch_llms_txt(self, url: str) -> str | None:
        """Fetch llms.txt content."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "FindableBot/1.0"},
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    # llms.txt should be plain text or markdown
                    if "text/" in content_type or not content_type:
                        return response.text
                    return None
                return None

        except Exception:
            return None

    def _parse_content(self, result: LlmsTxtResult, content: str) -> None:
        """Parse llms.txt content and extract structure."""
        lines = content.strip().split("\n")

        # Check for title (# heading at start)
        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                result.has_title = True
                result.title = line[2:].strip()
                break

        # Check for description (> blockquote)
        for line in lines:
            line = line.strip()
            if line.startswith("> "):
                result.has_description = True
                result.description = line[2:].strip()
                break

        # Check for sections (## headings)
        section_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
        sections = section_pattern.findall(content)
        if sections:
            result.has_sections = True
            result.sections = sections

        # Extract links [text](url) with optional description
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)(?:\s*[-:]?\s*(.+))?")
        for match in link_pattern.finditer(content):
            text = match.group(1).strip()
            url = match.group(2).strip()
            description = match.group(3).strip() if match.group(3) else None

            result.links.append(
                LlmsTxtLink(
                    text=text,
                    url=url,
                    description=description,
                )
            )

        result.link_count = len(result.links)
        result.has_links = result.link_count > 0

        # Check for issues
        if not result.has_title:
            result.issues.append("Missing title (# heading)")
        if not result.has_description:
            result.issues.append("Missing description (> blockquote)")
        if not result.has_links:
            result.issues.append("No links found")
        if result.link_count > 0 and result.link_count < 3:
            result.issues.append("Very few links (recommend 5+)")

        # Check content length
        if len(content) > 50000:
            result.issues.append("File too large (>50KB), may slow parsing")

    def _calculate_quality_score(self, result: LlmsTxtResult) -> None:
        """Calculate quality score based on structure and content."""
        score = 0.0

        # Title (20 points)
        if result.has_title:
            score += 20

        # Description (20 points)
        if result.has_description:
            score += 20

        # Sections (15 points)
        if result.has_sections:
            score += 15

        # Links (45 points, scaled by count)
        if result.has_links:
            # More links = better (up to 10)
            link_score = min(45, result.link_count * 4.5)
            score += link_score

        result.quality_score = score

        # Set level
        if score >= 80:
            result.level = "excellent"
        elif score >= 50:
            result.level = "good"
        elif score > 0:
            result.level = "poor"
        else:
            result.level = "missing"


async def check_llms_txt(url: str, timeout: float = 10.0) -> LlmsTxtResult:
    """
    Convenience function to check for llms.txt.

    Args:
        url: Any URL on the site
        timeout: Request timeout in seconds

    Returns:
        LlmsTxtResult with existence and quality information
    """
    checker = LlmsTxtChecker(timeout=timeout)
    return await checker.check(url)


def generate_llms_txt_template(
    site_name: str,
    description: str,
    sections: dict[str, list[tuple[str, str, str]]],
) -> str:
    """
    Generate a template llms.txt file.

    Args:
        site_name: Name of the site/company
        description: Brief description
        sections: Dict of section name -> list of (link_text, url, description)

    Returns:
        Formatted llms.txt content

    Example:
        sections = {
            "Products": [
                ("Product A", "/products/a", "Our main product"),
                ("Product B", "/products/b", "Secondary offering"),
            ],
            "Documentation": [
                ("Getting Started", "/docs/start", "Quick start guide"),
            ],
        }
    """
    lines = [
        f"# {site_name}",
        "",
        f"> {description}",
        "",
    ]

    for section_name, links in sections.items():
        lines.append(f"## {section_name}")
        lines.append("")
        for text, url, desc in links:
            lines.append(f"- [{text}]({url}): {desc}")
        lines.append("")

    return "\n".join(lines)
