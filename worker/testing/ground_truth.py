"""Ground truth collection from AI systems.

Queries AI systems (ChatGPT, Perplexity, Claude) with test queries
and extracts which domains are cited in the responses.
"""

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

from worker.testing.config import AIQueryConfig
from worker.testing.queries import TestQuery

logger = structlog.get_logger(__name__)


@dataclass
class CitedSource:
    """A source cited or mentioned in an AI response."""

    domain: str
    url: str | None = None
    mention_type: str = "mentioned"  # "cited", "mentioned", "linked"
    context: str = ""  # Surrounding text where mentioned

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "url": self.url,
            "mention_type": self.mention_type,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CitedSource":
        return cls(
            domain=data["domain"],
            url=data.get("url"),
            mention_type=data.get("mention_type", "mentioned"),
            context=data.get("context", ""),
        )


@dataclass
class ProviderResponse:
    """Response from a single AI provider."""

    provider: str  # "chatgpt", "perplexity", "claude", "google_aio"
    model: str
    response_text: str
    cited_sources: list[CitedSource] = field(default_factory=list)
    response_time_ms: int = 0
    tokens_used: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "response_text": self.response_text,
            "cited_sources": [s.to_dict() for s in self.cited_sources],
            "response_time_ms": self.response_time_ms,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderResponse":
        return cls(
            provider=data["provider"],
            model=data["model"],
            response_text=data["response_text"],
            cited_sources=[CitedSource.from_dict(s) for s in data.get("cited_sources", [])],
            response_time_ms=data.get("response_time_ms", 0),
            tokens_used=data.get("tokens_used", 0),
            error=data.get("error"),
        )


@dataclass
class GroundTruthResult:
    """Ground truth for a single query."""

    query: str
    query_id: str
    category: str
    provider_responses: list[ProviderResponse] = field(default_factory=list)
    all_cited_domains: list[str] = field(default_factory=list)
    consensus_domains: list[str] = field(default_factory=list)  # Cited by 2+ providers
    queried_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_id": self.query_id,
            "category": self.category,
            "provider_responses": [p.to_dict() for p in self.provider_responses],
            "all_cited_domains": self.all_cited_domains,
            "consensus_domains": self.consensus_domains,
            "queried_at": self.queried_at,
            "cached": self.cached,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroundTruthResult":
        return cls(
            query=data["query"],
            query_id=data["query_id"],
            category=data["category"],
            provider_responses=[
                ProviderResponse.from_dict(p) for p in data.get("provider_responses", [])
            ],
            all_cited_domains=data.get("all_cited_domains", []),
            consensus_domains=data.get("consensus_domains", []),
            queried_at=data.get("queried_at", datetime.now(UTC).isoformat()),
            cached=data.get("cached", False),
        )

    def compute_aggregates(self) -> None:
        """Compute aggregate domain lists from provider responses."""
        domain_counts: dict[str, int] = {}

        for response in self.provider_responses:
            if response.error:
                continue
            for source in response.cited_sources:
                domain = source.domain.lower()
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # All domains mentioned
        self.all_cited_domains = sorted(domain_counts.keys())

        # Consensus domains (mentioned by 2+ providers)
        self.consensus_domains = sorted(d for d, count in domain_counts.items() if count >= 2)


def extract_domains_from_text(text: str) -> list[CitedSource]:
    """
    Extract domain mentions and URLs from AI response text.

    Looks for:
    - Explicit URLs (https://example.com/...)
    - Domain mentions (example.com, www.example.com)
    - Reference patterns ([1] example.com, Source: example.com)
    """
    sources = []
    seen_domains: set[str] = set()

    # Pattern for full URLs
    url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+)(?:[^\s\)\]\}"\',<>]*)?'

    for match in re.finditer(url_pattern, text, re.IGNORECASE):
        domain = match.group(1).lower()
        full_url = match.group(0)

        if domain not in seen_domains:
            # Get context (50 chars before and after)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()

            sources.append(
                CitedSource(
                    domain=domain,
                    url=full_url,
                    mention_type="linked",
                    context=context,
                )
            )
            seen_domains.add(domain)

    # Pattern for domain mentions without protocol
    domain_pattern = r'(?:^|[\s\(\[\{"\',>])(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})(?:[\s\)\]\}"\',<>.]|$)'

    for match in re.finditer(domain_pattern, text, re.IGNORECASE):
        domain = match.group(1).lower()

        # Skip common false positives
        if domain in seen_domains:
            continue
        if domain.endswith((".png", ".jpg", ".gif", ".css", ".js")):
            continue

        # Get context
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end].strip()

        sources.append(
            CitedSource(
                domain=domain,
                url=None,
                mention_type="mentioned",
                context=context,
            )
        )
        seen_domains.add(domain)

    # Pattern for reference-style citations: [1] domain.com, Source: domain.com
    ref_pattern = r"(?:\[\d+\]|\*|Source:?|Reference:?|See:?)\s*(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})"

    for match in re.finditer(ref_pattern, text, re.IGNORECASE):
        domain = match.group(1).lower()

        if domain in seen_domains:
            continue

        # Get context
        start = max(0, match.start() - 30)
        end = min(len(text), match.end() + 30)
        context = text[start:end].strip()

        sources.append(
            CitedSource(
                domain=domain,
                url=None,
                mention_type="cited",
                context=context,
            )
        )
        seen_domains.add(domain)

    return sources


def get_cache_key(query: str, providers: list[str]) -> str:
    """Generate cache key for a query + providers combination."""
    key_data = f"{query}:{','.join(sorted(providers))}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def load_cached_result(
    query: str,
    providers: list[str],
    cache_dir: Path,
    cache_ttl_hours: int = 24,
) -> GroundTruthResult | None:
    """Load cached ground truth result if available."""
    cache_key = get_cache_key(query, providers)
    cache_file = cache_dir / f"ground_truth_{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)

        # Check TTL
        queried_at = datetime.fromisoformat(data.get("queried_at", ""))
        age_hours = (datetime.now(UTC) - queried_at).total_seconds() / 3600

        if age_hours > cache_ttl_hours:
            return None

        result = GroundTruthResult.from_dict(data)
        result.cached = True
        return result

    except Exception as e:
        logger.warning("cache_load_failed", query=query[:50], error=str(e))
        return None


def save_cached_result(
    result: GroundTruthResult,
    providers: list[str],
    cache_dir: Path,
) -> None:
    """Save ground truth result to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = get_cache_key(result.query, providers)
    cache_file = cache_dir / f"ground_truth_{cache_key}.json"

    try:
        with open(cache_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
    except Exception as e:
        logger.warning("cache_save_failed", query=result.query[:50], error=str(e))


async def query_provider_mock(
    query: str,
    provider: str,
) -> ProviderResponse:
    """Mock provider for testing without API calls."""
    # Simulate some response time
    await asyncio.sleep(0.1)

    # Generate mock response based on query content
    mock_domains = []
    query_lower = query.lower()

    if "seo" in query_lower:
        mock_domains = ["moz.com", "ahrefs.com", "searchengineland.com"]
    elif "schema" in query_lower:
        mock_domains = ["schema.org", "developers.google.com"]
    elif "marketing" in query_lower:
        mock_domains = ["hubspot.com", "neilpatel.com"]
    else:
        mock_domains = ["wikipedia.org", "example.com"]

    response_text = f"Based on my knowledge, here's information about '{query}'.\n\n"
    response_text += "Key sources include:\n"
    for domain in mock_domains:
        response_text += f"- https://{domain}\n"

    sources = [
        CitedSource(domain=d, url=f"https://{d}", mention_type="cited") for d in mock_domains
    ]

    return ProviderResponse(
        provider=provider,
        model="mock-model",
        response_text=response_text,
        cited_sources=sources,
        response_time_ms=100,
        tokens_used=50,
    )


async def query_chatgpt(
    query: str,
    config: AIQueryConfig,
) -> ProviderResponse:
    """Query ChatGPT/OpenAI with a test query."""
    import os
    import time

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return await query_provider_mock(query, "chatgpt")

    try:
        import httpx

        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=config.request_timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant. When answering, cite your sources with URLs when possible.",
                        },
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 1024,
                },
            )

            response_time_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code != 200:
                return ProviderResponse(
                    provider="chatgpt",
                    model="gpt-4o-mini",
                    response_text="",
                    error=f"API error: {response.status_code}",
                    response_time_ms=response_time_ms,
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)

            # Extract domains from response
            sources = extract_domains_from_text(content)

            return ProviderResponse(
                provider="chatgpt",
                model="gpt-4o-mini",
                response_text=content,
                cited_sources=sources,
                response_time_ms=response_time_ms,
                tokens_used=tokens,
            )

    except Exception as e:
        logger.warning("chatgpt_query_failed", query=query[:50], error=str(e))
        return ProviderResponse(
            provider="chatgpt",
            model="gpt-4o-mini",
            response_text="",
            error=str(e),
        )


async def query_claude(
    query: str,
    config: AIQueryConfig,
) -> ProviderResponse:
    """Query Claude with a test query."""
    import os
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return await query_provider_mock(query, "claude")

    try:
        import httpx

        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=config.request_timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": query}],
                },
            )

            response_time_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code != 200:
                return ProviderResponse(
                    provider="claude",
                    model="claude-3-haiku",
                    response_text="",
                    error=f"API error: {response.status_code}",
                    response_time_ms=response_time_ms,
                )

            data = response.json()
            content = data["content"][0]["text"]
            tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get(
                "output_tokens", 0
            )

            # Extract domains from response
            sources = extract_domains_from_text(content)

            return ProviderResponse(
                provider="claude",
                model="claude-3-haiku",
                response_text=content,
                cited_sources=sources,
                response_time_ms=response_time_ms,
                tokens_used=tokens,
            )

    except Exception as e:
        logger.warning("claude_query_failed", query=query[:50], error=str(e))
        return ProviderResponse(
            provider="claude",
            model="claude-3-haiku",
            response_text="",
            error=str(e),
        )


async def query_perplexity(
    query: str,
    config: AIQueryConfig,
) -> ProviderResponse:
    """Query Perplexity with a test query."""
    import os
    import time

    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        return await query_provider_mock(query, "perplexity")

    try:
        import httpx

        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=config.request_timeout) as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-sonar-small-128k-online",
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 1024,
                },
            )

            response_time_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code != 200:
                return ProviderResponse(
                    provider="perplexity",
                    model="sonar-small",
                    response_text="",
                    error=f"API error: {response.status_code}",
                    response_time_ms=response_time_ms,
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)

            # Extract domains from response
            sources = extract_domains_from_text(content)

            # Perplexity often includes citations in a special format
            citations = data.get("citations", [])
            for url in citations:
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace("www.", "").lower()
                    if domain and not any(s.domain == domain for s in sources):
                        sources.append(
                            CitedSource(
                                domain=domain,
                                url=url,
                                mention_type="cited",
                            )
                        )
                except Exception:
                    pass

            return ProviderResponse(
                provider="perplexity",
                model="sonar-small",
                response_text=content,
                cited_sources=sources,
                response_time_ms=response_time_ms,
                tokens_used=tokens,
            )

    except Exception as e:
        logger.warning("perplexity_query_failed", query=query[:50], error=str(e))
        return ProviderResponse(
            provider="perplexity",
            model="sonar-small",
            response_text="",
            error=str(e),
        )


async def collect_ground_truth(
    query: TestQuery,
    config: AIQueryConfig | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
) -> GroundTruthResult:
    """
    Collect ground truth for a single query from all configured providers.

    Args:
        query: The test query to run
        config: AI query configuration
        cache_dir: Directory for caching results
        use_cache: Whether to use cached results

    Returns:
        GroundTruthResult with citations from each provider
    """
    config = config or AIQueryConfig()
    cache_dir = cache_dir or Path("results/cache/ground_truth")

    # Determine which providers to use
    providers = []
    if config.query_chatgpt:
        providers.append("chatgpt")
    if config.query_claude:
        providers.append("claude")
    if config.query_perplexity:
        providers.append("perplexity")

    # Check cache first
    if use_cache:
        cached = load_cached_result(
            query.query,
            providers,
            cache_dir,
            config.cache_ttl_hours,
        )
        if cached:
            logger.debug("cache_hit", query=query.query[:50])
            return cached

    logger.info("collecting_ground_truth", query=query.query[:50], providers=providers)

    # Query each provider
    tasks = []
    if config.query_chatgpt:
        tasks.append(("chatgpt", query_chatgpt(query.query, config)))
    if config.query_claude:
        tasks.append(("claude", query_claude(query.query, config)))
    if config.query_perplexity:
        tasks.append(("perplexity", query_perplexity(query.query, config)))

    # Run queries with rate limiting
    responses = []
    for provider_name, coro in tasks:
        try:
            response = await coro
            responses.append(response)
        except Exception as e:
            responses.append(
                ProviderResponse(
                    provider=provider_name,
                    model="unknown",
                    response_text="",
                    error=str(e),
                )
            )

        # Rate limiting delay
        await asyncio.sleep(60 / max(config.chatgpt_rpm, config.claude_rpm, config.perplexity_rpm))

    # Build result
    result = GroundTruthResult(
        query=query.query,
        query_id=str(hash(query.query)),
        category=query.category.value,
        provider_responses=responses,
    )

    # Compute aggregates
    result.compute_aggregates()

    # Save to cache
    if use_cache:
        save_cached_result(result, providers, cache_dir)

    return result


async def collect_ground_truth_batch(
    queries: list[TestQuery],
    config: AIQueryConfig | None = None,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    concurrency: int = 2,
) -> list[GroundTruthResult]:
    """
    Collect ground truth for multiple queries with concurrency control.

    Args:
        queries: List of test queries
        config: AI query configuration
        cache_dir: Directory for caching results
        use_cache: Whether to use cached results
        concurrency: Maximum concurrent queries

    Returns:
        List of GroundTruthResult objects
    """
    config = config or AIQueryConfig()
    cache_dir = cache_dir or Path("results/cache/ground_truth")

    semaphore = asyncio.Semaphore(concurrency)

    async def collect_with_semaphore(query: TestQuery) -> GroundTruthResult:
        async with semaphore:
            return await collect_ground_truth(query, config, cache_dir, use_cache)

    tasks = [collect_with_semaphore(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to error results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append(
                GroundTruthResult(
                    query=queries[i].query,
                    query_id=str(hash(queries[i].query)),
                    category=queries[i].category.value,
                    provider_responses=[
                        ProviderResponse(
                            provider="error",
                            model="",
                            response_text="",
                            error=str(result),
                        )
                    ],
                )
            )
        else:
            processed_results.append(result)

    return processed_results
