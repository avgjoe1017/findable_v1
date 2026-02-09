"""AI crawler access checker for robots.txt.

Tests whether a site allows major AI crawlers (GPTBot, ClaudeBot, etc.)
to access content. This is a binary gate - if blocked, nothing else matters.
"""

from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from worker.crawler.robots import RobotsParser

logger = structlog.get_logger(__name__)


# =============================================================================
# AI VISIBILITY PIPELINE MODEL
# =============================================================================
#
# Most AI answer engines do NOT crawl the web directly. They source content from:
#
# PIPELINE 1: SEARCH-INDEXED (Primary - where you WILL show up)
# -----------------------------------------------------------------------------
# These systems use Google/Bing/Apple search indexes to find and cite content.
# If Googlebot can crawl you → you're visible to most AI answer engines.
#
# | AI System              | Primary Index Used    |
# |------------------------|----------------------|
# | Google AI Overviews    | Google Search        |
# | Bing Copilot           | Bing Search          |
# | ChatGPT (via search)   | Bing Search          |
# | Claude (via search)    | Google Search        |
# | Gemini                 | Google Search        |
# | Apple Intelligence     | Applebot index       |
#
# PIPELINE 2: DIRECT-CRAWL (Secondary - where you might NOT show up)
# -----------------------------------------------------------------------------
# Some systems crawl directly with their own bots. Blocking these means:
# - NOT shown in ChatGPT search results (if OAI-SearchBot blocked)
# - NOT used for AI training (if GPTBot/ClaudeBot blocked)
# - NOT shown in Perplexity (if PerplexityBot blocked)
#
# | Crawler         | Purpose                                      |
# |-----------------|----------------------------------------------|
# | OAI-SearchBot   | ChatGPT search results (distinct from GPTBot)|
# | GPTBot          | OpenAI training data                         |
# | ChatGPT-User    | Real-time browsing for ChatGPT queries       |
# | ClaudeBot       | Anthropic training and browsing              |
# | PerplexityBot   | Perplexity's own search index                |
#
# PIPELINE 3: SOCIAL PREVIEWS (Link sharing visibility)
# -----------------------------------------------------------------------------
# These crawlers fetch content for link previews when URLs are shared.
# Blocking these = broken/missing previews on social platforms.
#
# =============================================================================

# Search engine crawlers - CRITICAL for AI visibility
# These determine whether AI systems can find you via search indexes
# Blocking these = content won't be cited by most AI answer engines
SEARCH_CRAWLERS: dict[str, dict] = {
    "Googlebot": {
        "user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "weight": 35,
        "owner": "Google",
        "purpose": "Primary search index - used by Google AI Overviews, Gemini, ChatGPT (partial), Claude (partial)",
        "pipeline": "search_indexed",
        "visibility_type": "search_answers",
    },
    "Bingbot": {
        "user_agent": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "weight": 20,
        "owner": "Microsoft",
        "purpose": "Bing search index - used by Bing Copilot, ChatGPT search (partial)",
        "pipeline": "search_indexed",
        "visibility_type": "search_answers",
    },
    "Applebot": {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15 (Applebot/0.1)",
        "weight": 5,
        "owner": "Apple",
        "purpose": "Apple search index - used by Siri, Spotlight, Apple Intelligence",
        "pipeline": "search_indexed",
        "visibility_type": "search_answers",
    },
}

# AI-specific crawlers - IMPORTANT for direct AI access
# Blocking these limits specific AI features but search-indexed visibility remains
#
# Visibility impacts by crawler:
# - SEARCH ANSWERS: Content appears as cited/snippeted source in AI answers
# - LINK ONLY: May appear as navigational link but not as quoted evidence
# - TRAINING: Content used to train/improve AI models
#
AI_CRAWLERS: dict[str, dict] = {
    # OpenAI crawlers (3 distinct purposes per platform.openai.com/docs/bots)
    "OAI-SearchBot": {
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0",
        "weight": 12,
        "owner": "OpenAI",
        "purpose": "ChatGPT search results - blocking = won't appear as cited source in ChatGPT answers (may still appear as link)",
        "pipeline": "direct_crawl",
        "visibility_type": "search_answers",
    },
    "GPTBot": {
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.0",
        "weight": 5,
        "owner": "OpenAI",
        "purpose": "OpenAI training data collection - blocking = excluded from future model training",
        "pipeline": "direct_crawl",
        "visibility_type": "training",
    },
    "ChatGPT-User": {
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0",
        "weight": 4,
        "owner": "OpenAI",
        "purpose": "Real-time browsing when ChatGPT users click links or request page fetch",
        "pipeline": "direct_crawl",
        "visibility_type": "user_browsing",
    },
    # Anthropic crawlers (3 distinct purposes per support.anthropic.com)
    "Claude-SearchBot": {
        "user_agent": "Claude-SearchBot/1.0",
        "weight": 8,
        "owner": "Anthropic",
        "purpose": "Claude search indexing - blocking = won't appear as cited source in Claude answers",
        "pipeline": "direct_crawl",
        "visibility_type": "search_answers",
    },
    "ClaudeBot": {
        "user_agent": "ClaudeBot/1.0",
        "weight": 3,
        "owner": "Anthropic",
        "purpose": "Anthropic training data collection - blocking = excluded from Claude training",
        "pipeline": "direct_crawl",
        "visibility_type": "training",
    },
    "Claude-User": {
        "user_agent": "Claude-User/1.0",
        "weight": 3,
        "owner": "Anthropic",
        "purpose": "User-directed retrieval when Claude users request page fetch",
        "pipeline": "direct_crawl",
        "visibility_type": "user_browsing",
    },
    # Perplexity (per perplexity.ai/help-center)
    "PerplexityBot": {
        "user_agent": "PerplexityBot/1.0",
        "weight": 6,
        "owner": "Perplexity",
        "purpose": "Perplexity search index - blocking = headline-only visibility, not full-text citations",
        "pipeline": "direct_crawl",
        "visibility_type": "search_answers",
    },
    # Google AI training (separate from Googlebot search)
    "Google-Extended": {
        "user_agent": "Google-Extended",
        "weight": 2,
        "owner": "Google",
        "purpose": "Gemini/Bard training data - blocking = excluded from Google AI training (search still works)",
        "pipeline": "direct_crawl",
        "visibility_type": "training",
    },
    # Common Crawl (per commoncrawl.org/ccbot)
    "CCBot": {
        "user_agent": "CCBot/2.0 (https://commoncrawl.org/faq/)",
        "weight": 1,
        "owner": "Common Crawl",
        "purpose": "Open dataset used by many AI systems - blocking = excluded from Common Crawl corpus",
        "pipeline": "direct_crawl",
        "visibility_type": "training",
    },
}

# Social preview crawlers - for link sharing visibility
# Not part of AI scoring but important for complete visibility picture
SOCIAL_CRAWLERS: dict[str, dict] = {
    "facebookexternalhit": {
        "user_agent": "facebookexternalhit/1.1",
        "weight": 3,
        "owner": "Meta",
        "purpose": "Facebook/Instagram link previews when URLs are shared",
        "pipeline": "social_preview",
    },
    "Facebot": {
        "user_agent": "Facebot",
        "weight": 2,
        "owner": "Meta",
        "purpose": "Facebook crawler for content discovery and previews (distinct from facebookexternalhit)",
        "pipeline": "social_preview",
    },
    "Twitterbot": {
        "user_agent": "Twitterbot/1.0",
        "weight": 2,
        "owner": "X/Twitter",
        "purpose": "Twitter/X link previews (cards)",
        "pipeline": "social_preview",
    },
    "LinkedInBot": {
        "user_agent": "LinkedInBot/1.0",
        "weight": 2,
        "owner": "LinkedIn",
        "purpose": "LinkedIn link previews",
        "pipeline": "social_preview",
    },
    "Slackbot": {
        "user_agent": "Slackbot-LinkExpanding 1.0",
        "weight": 1,
        "owner": "Slack",
        "purpose": "Slack link unfurling",
        "pipeline": "social_preview",
    },
}

# Combined for backward compatibility and comprehensive checks
ALL_CRAWLERS: dict[str, dict] = {**SEARCH_CRAWLERS, **AI_CRAWLERS, **SOCIAL_CRAWLERS}


@dataclass
class CrawlerAccessResult:
    """Result for a single crawler's access status."""

    crawler_name: str
    allowed: bool
    owner: str
    purpose: str
    weight: int
    pipeline: str  # "search_indexed", "direct_crawl", or "social_preview"
    visibility_type: str = ""  # "search_answers", "training", "user_browsing", or ""

    @property
    def is_search_crawler(self) -> bool:
        return self.pipeline == "search_indexed"

    @property
    def is_ai_crawler(self) -> bool:
        return self.pipeline == "direct_crawl"

    @property
    def is_social_crawler(self) -> bool:
        return self.pipeline == "social_preview"

    def to_dict(self) -> dict:
        return {
            "crawler_name": self.crawler_name,
            "allowed": self.allowed,
            "owner": self.owner,
            "purpose": self.purpose,
            "weight": self.weight,
            "pipeline": self.pipeline,
            "visibility_type": self.visibility_type,
        }


@dataclass
class RobotsTxtAIResult:
    """Complete result of AI crawler access check with multi-pipeline model."""

    domain: str
    robots_txt_exists: bool
    robots_txt_url: str
    crawlers: dict[str, CrawlerAccessResult] = field(default_factory=dict)

    # Combined score for AI visibility (weighted: search=60%, direct=40%)
    score: float = 0.0  # 0-100

    # Pipeline-specific scores
    search_indexed_score: float = 0.0  # Score for search engine access (Google, Bing, Apple)
    direct_crawl_score: float = 0.0  # Score for AI crawler access (GPTBot, ClaudeBot, etc.)
    social_preview_score: float = 0.0  # Score for social link previews (not in main score)

    # Issues by severity
    critical_blocked: list[str] = field(default_factory=list)  # Search engines blocked
    warning_blocked: list[str] = field(default_factory=list)  # AI crawlers blocked
    info_blocked: list[str] = field(default_factory=list)  # Social crawlers blocked (informational)

    all_allowed: bool = False
    error: str | None = None

    @property
    def level(self) -> str:
        """
        Get progress level indicating how far along AI visibility is.

        Levels reflect visibility progression, not severity:
        - "full": Full AI visibility (80%+ combined score)
        - "partial": Partial visibility (some pipelines limited)
        - "limited": Limited visibility (major pipeline blocked)
        """
        if self.score >= 80:
            return "full"
        elif self.search_indexed_score >= 50 and self.direct_crawl_score >= 50:
            return "partial"
        elif self.search_indexed_score >= 50:
            # Search-indexed works, direct-crawl limited
            return "partial"
        else:
            # Search engines blocked = severely limited
            return "limited"

    @property
    def pipeline_summary(self) -> str:
        """Human-readable summary of visibility via each pipeline."""
        search_status = (
            "visible"
            if self.search_indexed_score >= 80
            else "limited" if self.search_indexed_score >= 50 else "blocked"
        )
        direct_status = (
            "visible"
            if self.direct_crawl_score >= 80
            else "limited" if self.direct_crawl_score >= 50 else "blocked"
        )
        social_status = (
            "visible"
            if self.social_preview_score >= 80
            else "limited" if self.social_preview_score >= 50 else "blocked"
        )
        return f"Search-indexed: {search_status}, Direct-crawl: {direct_status}, Social: {social_status}"

    @property
    def ai_system_visibility(self) -> dict[str, str]:
        """Simple map of which AI systems can likely see this content."""
        visibility = {}

        # Search-indexed systems (depend on Googlebot/Bingbot)
        if self.search_indexed_score >= 80:
            visibility["Google AI Overviews"] = "visible"
            visibility["Gemini"] = "visible"
            visibility["Bing Copilot"] = "visible"
        elif self.search_indexed_score >= 50:
            visibility["Google AI Overviews"] = "limited"
            visibility["Gemini"] = "limited"
            visibility["Bing Copilot"] = "limited"
        else:
            visibility["Google AI Overviews"] = "blocked"
            visibility["Gemini"] = "blocked"
            visibility["Bing Copilot"] = "blocked"

        # Direct-crawl systems (depend on their specific bot)
        oai_search = self.crawlers.get("OAI-SearchBot")
        visibility["ChatGPT Search"] = (
            "cited" if (oai_search and oai_search.allowed) else "link_only"
        )

        claude_search = self.crawlers.get("Claude-SearchBot")
        visibility["Claude Search"] = (
            "cited" if (claude_search and claude_search.allowed) else "link_only"
        )

        perplexity = self.crawlers.get("PerplexityBot")
        visibility["Perplexity"] = (
            "cited" if (perplexity and perplexity.allowed) else "headline_only"
        )

        return visibility

    @property
    def detailed_visibility(self) -> dict[str, dict]:
        """
        Detailed visibility breakdown by AI system and visibility type.

        Returns dict with:
        - search_cited: AI systems that can cite this content as a source (via search indexes)
        - direct_cited: AI systems that can cite this content (via direct crawl)
        - link_only: AI systems that may link but won't cite/snippet
        - training: Whether content is used for AI training
        - user_browsing: Whether AI can fetch pages on user request
        """
        visibility: dict[str, dict[str, object]] = {
            "search_cited": {},
            "direct_cited": {},
            "link_only": {},
            "training": {},
            "user_browsing": {},
        }

        # Search-indexed citation (via Google/Bing)
        googlebot = self.crawlers.get("Googlebot")
        bingbot = self.crawlers.get("Bingbot")

        google_indexed = googlebot and googlebot.allowed
        bing_indexed = bingbot and bingbot.allowed

        visibility["search_cited"]["Google AI Overviews"] = "yes" if google_indexed else "no"
        visibility["search_cited"]["Gemini"] = "yes" if google_indexed else "no"
        visibility["search_cited"]["Bing Copilot"] = "yes" if bing_indexed else "no"

        # Direct-crawl citation (via AI's own search bots)
        oai_search = self.crawlers.get("OAI-SearchBot")
        claude_search = self.crawlers.get("Claude-SearchBot")
        perplexity = self.crawlers.get("PerplexityBot")

        visibility["direct_cited"]["ChatGPT Search"] = (
            "yes" if (oai_search and oai_search.allowed) else "no"
        )
        visibility["direct_cited"]["Claude Search"] = (
            "yes" if (claude_search and claude_search.allowed) else "no"
        )
        visibility["direct_cited"]["Perplexity"] = (
            "yes" if (perplexity and perplexity.allowed) else "no"
        )

        # Link-only visibility (blocked from direct crawl but may appear via third-party)
        # Per OpenAI: "may still surface just the link + page title"
        if not (oai_search and oai_search.allowed) and (google_indexed or bing_indexed):
            visibility["link_only"]["ChatGPT Search"] = "link + title only (not cited/snippeted)"
        if not (perplexity and perplexity.allowed) and (google_indexed or bing_indexed):
            visibility["link_only"]["Perplexity"] = "headline-level visibility only"

        # Training data visibility
        gptbot = self.crawlers.get("GPTBot")
        claudebot = self.crawlers.get("ClaudeBot")
        google_ext = self.crawlers.get("Google-Extended")
        ccbot = self.crawlers.get("CCBot")

        visibility["training"]["OpenAI (GPTBot)"] = (
            "included" if (gptbot and gptbot.allowed) else "excluded"
        )
        visibility["training"]["Anthropic (ClaudeBot)"] = (
            "included" if (claudebot and claudebot.allowed) else "excluded"
        )
        visibility["training"]["Google AI (Google-Extended)"] = (
            "included" if (google_ext and google_ext.allowed) else "excluded"
        )
        visibility["training"]["Common Crawl (CCBot)"] = (
            "included" if (ccbot and ccbot.allowed) else "excluded"
        )

        # User-directed browsing (can AI fetch page when user requests?)
        chatgpt_user = self.crawlers.get("ChatGPT-User")
        claude_user = self.crawlers.get("Claude-User")

        visibility["user_browsing"]["ChatGPT Browse"] = (
            "yes" if (chatgpt_user and chatgpt_user.allowed) else "no"
        )
        visibility["user_browsing"]["Claude Fetch"] = (
            "yes" if (claude_user and claude_user.allowed) else "no"
        )

        return visibility

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "robots_txt_exists": self.robots_txt_exists,
            "robots_txt_url": self.robots_txt_url,
            "crawlers": {k: v.to_dict() for k, v in self.crawlers.items()},
            "score": round(self.score, 2),
            "search_indexed_score": round(self.search_indexed_score, 2),
            "direct_crawl_score": round(self.direct_crawl_score, 2),
            "social_preview_score": round(self.social_preview_score, 2),
            "critical_blocked": self.critical_blocked,
            "warning_blocked": self.warning_blocked,
            "info_blocked": self.info_blocked,
            "all_allowed": self.all_allowed,
            "level": self.level,
            "pipeline_summary": self.pipeline_summary,
            "ai_system_visibility": self.ai_system_visibility,
            "detailed_visibility": self.detailed_visibility,
            "error": self.error,
        }


class AIRobotsChecker:
    """Checks robots.txt for AI crawler access."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def check(self, url: str) -> RobotsTxtAIResult:
        """
        Check if a site allows AI crawlers.

        Args:
            url: Any URL on the site (will extract domain)

        Returns:
            RobotsTxtAIResult with per-crawler status and overall score
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        base_url = f"{parsed.scheme}://{domain}"
        robots_url = urljoin(base_url, "/robots.txt")

        result = RobotsTxtAIResult(
            domain=domain,
            robots_txt_exists=False,
            robots_txt_url=robots_url,
        )

        try:
            robots_content = await self._fetch_robots_txt(robots_url)

            if robots_content is None:
                # No robots.txt = all crawlers allowed
                result.robots_txt_exists = False
                result.all_allowed = True
                result.score = 100.0
                result.search_indexed_score = 100.0
                result.direct_crawl_score = 100.0
                result.social_preview_score = 100.0

                # Add search engine crawlers
                for name, config in SEARCH_CRAWLERS.items():
                    result.crawlers[name] = CrawlerAccessResult(
                        crawler_name=name,
                        allowed=True,
                        owner=config["owner"],
                        purpose=config["purpose"],
                        weight=config["weight"],
                        pipeline=config["pipeline"],
                        visibility_type=config.get("visibility_type", ""),
                    )

                # Add AI crawlers
                for name, config in AI_CRAWLERS.items():
                    result.crawlers[name] = CrawlerAccessResult(
                        crawler_name=name,
                        allowed=True,
                        owner=config["owner"],
                        purpose=config["purpose"],
                        weight=config["weight"],
                        pipeline=config["pipeline"],
                        visibility_type=config.get("visibility_type", ""),
                    )

                # Add social crawlers
                for name, config in SOCIAL_CRAWLERS.items():
                    result.crawlers[name] = CrawlerAccessResult(
                        crawler_name=name,
                        allowed=True,
                        owner=config["owner"],
                        purpose=config["purpose"],
                        weight=config["weight"],
                        pipeline=config["pipeline"],
                        visibility_type=config.get("visibility_type", ""),
                    )

                logger.info(
                    "robots_txt_not_found",
                    domain=domain,
                    result="all_crawlers_allowed_by_default",
                )
                return result

            result.robots_txt_exists = True

            # Check search engine crawlers (critical for AI visibility)
            search_max = sum(c["weight"] for c in SEARCH_CRAWLERS.values())
            search_earned = 0

            for name, config in SEARCH_CRAWLERS.items():
                parser = RobotsParser.parse(robots_content, name)
                allowed = parser.is_allowed("/")

                result.crawlers[name] = CrawlerAccessResult(
                    crawler_name=name,
                    allowed=allowed,
                    owner=config["owner"],
                    purpose=config["purpose"],
                    weight=config["weight"],
                    pipeline=config["pipeline"],
                    visibility_type=config.get("visibility_type", ""),
                )

                if allowed:
                    search_earned += config["weight"]
                else:
                    # Blocking search engines is CRITICAL
                    result.critical_blocked.append(name)

            # Check AI-specific crawlers (important but not critical)
            ai_max = sum(c["weight"] for c in AI_CRAWLERS.values())
            ai_earned = 0

            for name, config in AI_CRAWLERS.items():
                parser = RobotsParser.parse(robots_content, name)
                allowed = parser.is_allowed("/")

                result.crawlers[name] = CrawlerAccessResult(
                    crawler_name=name,
                    allowed=allowed,
                    owner=config["owner"],
                    purpose=config["purpose"],
                    weight=config["weight"],
                    pipeline=config["pipeline"],
                    visibility_type=config.get("visibility_type", ""),
                )

                if allowed:
                    ai_earned += config["weight"]
                else:
                    # Blocking AI crawlers is a WARNING (not critical)
                    result.warning_blocked.append(name)

            # Check social preview crawlers (informational)
            social_max = sum(c["weight"] for c in SOCIAL_CRAWLERS.values())
            social_earned = 0

            for name, config in SOCIAL_CRAWLERS.items():
                parser = RobotsParser.parse(robots_content, name)
                allowed = parser.is_allowed("/")

                result.crawlers[name] = CrawlerAccessResult(
                    crawler_name=name,
                    allowed=allowed,
                    owner=config["owner"],
                    purpose=config["purpose"],
                    weight=config["weight"],
                    pipeline=config["pipeline"],
                    visibility_type=config.get("visibility_type", ""),
                )

                if allowed:
                    social_earned += config["weight"]
                else:
                    # Blocking social crawlers is INFO (not part of AI visibility score)
                    result.info_blocked.append(name)

            # Calculate pipeline-specific scores
            result.search_indexed_score = (
                (search_earned / search_max) * 100 if search_max > 0 else 100
            )
            result.direct_crawl_score = (ai_earned / ai_max) * 100 if ai_max > 0 else 100
            result.social_preview_score = (
                (social_earned / social_max) * 100 if social_max > 0 else 100
            )

            # Combined score: 60% search-indexed, 40% direct-crawl
            # Social previews are not part of AI visibility score (informational only)
            result.score = (result.search_indexed_score * 0.6) + (result.direct_crawl_score * 0.4)

            result.all_allowed = (
                len(result.critical_blocked) == 0
                and len(result.warning_blocked) == 0
                and len(result.info_blocked) == 0
            )

            logger.info(
                "robots_txt_ai_check_complete",
                domain=domain,
                score=result.score,
                search_indexed_score=result.search_indexed_score,
                direct_crawl_score=result.direct_crawl_score,
                social_preview_score=result.social_preview_score,
                critical_blocked=result.critical_blocked,
                warning_blocked=result.warning_blocked,
                info_blocked=result.info_blocked,
                all_allowed=result.all_allowed,
            )

        except Exception as e:
            result.error = str(e)
            # On error, assume allowed (permissive default)
            result.score = 100.0
            result.all_allowed = True
            logger.warning(
                "robots_txt_check_error",
                domain=domain,
                error=str(e),
            )

        return result

    async def _fetch_robots_txt(self, robots_url: str) -> str | None:
        """Fetch robots.txt content."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": "FindableBot/1.0"},
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    return None
                else:
                    logger.warning(
                        "robots_txt_fetch_non_200",
                        url=robots_url,
                        status=response.status_code,
                    )
                    return None

        except httpx.TimeoutException:
            logger.warning("robots_txt_fetch_timeout", url=robots_url)
            return None
        except Exception as e:
            logger.warning("robots_txt_fetch_error", url=robots_url, error=str(e))
            return None


async def check_ai_crawler_access(url: str, timeout: float = 10.0) -> RobotsTxtAIResult:
    """
    Convenience function to check AI crawler access.

    Args:
        url: Any URL on the site
        timeout: Request timeout in seconds

    Returns:
        RobotsTxtAIResult with access status for all major AI crawlers
    """
    checker = AIRobotsChecker(timeout=timeout)
    return await checker.check(url)
