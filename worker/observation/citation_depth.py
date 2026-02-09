"""Citation depth analysis — extracts HOW DEEPLY an AI uses a company as a source.

Two layers:
1. Free text parsing (zero API calls): position, framing, competitor count
2. Batch AI classifier (ONE call per site, ~$0.001): 0-5 depth score per question

Citation Depth Scale:
    0 = NOT_MENTIONED: Company not referenced at all
    1 = PASSING: Name-dropped in a list ("companies like X, Y, Z")
    2 = DESCRIBED: AI knows what the company does, doesn't use as source
    3 = RECOMMENDED: AI suggests the company/product
    4 = FEATURED: Company is a primary example used to answer the question
    5 = AUTHORITY: Company treated as THE definitive source for the answer
"""

import json
import re
from dataclasses import dataclass

import httpx

# ---------------------------------------------------------------------------
# Free text-parsing signals (no API cost)
# ---------------------------------------------------------------------------


def detect_mention_position(content: str, company_name: str) -> str:
    """Where in the response is the company first mentioned?

    Returns: "opening" | "mid" | "closing" | "absent"

    Uses proportional position (0.0-1.0) rather than sentence index,
    since prompted responses almost always name the company early.
    """
    lower = content.lower()
    name_lower = company_name.lower()

    if name_lower not in lower:
        return "absent"

    first_idx = lower.index(name_lower)
    total_len = len(lower)

    if total_len == 0:
        return "absent"

    position_ratio = first_idx / total_len

    if position_ratio < 0.15:
        return "opening"
    elif position_ratio < 0.70:
        return "mid"
    else:
        return "closing"


def detect_source_framing(content: str, company_name: str) -> str:
    """How is the company framed in the response?

    Returns: "authoritative" | "recommended" | "listed" | "passing" | "absent"
    """
    lower = content.lower()
    name_lower = company_name.lower()

    if name_lower not in lower:
        return "absent"

    # Authoritative patterns — company treated as expert/source
    authority_patterns = [
        rf"according to {re.escape(name_lower)}",
        rf"{re.escape(name_lower)} (?:states?|explains?|notes?|reports?|defines?|describes?)",
        rf"as {re.escape(name_lower)} (?:points out|highlights|emphasizes|mentions)",
        rf"{re.escape(name_lower)}(?:'s| is) (?:the )?(?:leading|definitive|authoritative|official)",
        rf"(?:the )?{re.escape(name_lower)} (?:documentation|guide|resource|platform) (?:is|provides|offers)",
    ]

    for pattern in authority_patterns:
        if re.search(pattern, lower):
            return "authoritative"

    # Recommendation patterns — AI suggests using it
    recommend_patterns = [
        rf"(?:i |we )?recommend (?:using |checking out |visiting )?{re.escape(name_lower)}",
        rf"{re.escape(name_lower)} is (?:a |an )?(?:great|excellent|good|top|best|popular|well-known)",
        rf"you (?:should|could|might want to) (?:use|try|check out|visit) {re.escape(name_lower)}",
        rf"consider (?:using )?{re.escape(name_lower)}",
    ]

    for pattern in recommend_patterns:
        if re.search(pattern, lower):
            return "recommended"

    # List patterns — mentioned alongside competitors
    list_patterns = [
        rf"(?:companies|tools|platforms|services|providers) (?:like|such as|including) .*{re.escape(name_lower)}",
        rf"{re.escape(name_lower)}(?:,| and| or) (?:\w+(?:,| and| or) ){{1,}}",
        rf"(?:\w+(?:,| and| or) ){{1,}}{re.escape(name_lower)}",
    ]

    for pattern in list_patterns:
        if re.search(pattern, lower):
            return "listed"

    return "passing"


# Non-competitor entities to exclude from competitor counting
_IGNORELIST = {
    # Platforms / common references
    "wikipedia",
    "reddit",
    "quora",
    "stack overflow",
    "stackoverflow",
    "youtube",
    "twitter",
    "linkedin",
    "facebook",
    "instagram",
    "tiktok",
    "github",
    "medium",
    "substack",
    # Search engines
    "google",
    "bing",
    "yahoo",
    "duckduckgo",
    # Generic tech
    "chrome",
    "safari",
    "firefox",
    "microsoft",
    "apple",
    "amazon",
    "aws",
    # Common proper nouns in AI responses
    "united states",
    "north america",
    "south america",
    "europe",
    "new york",
    "san francisco",
    "los angeles",
    "london",
    # Common abbreviations that match CamelCase patterns
    "json",
    "html",
    "http",
    "https",
    "api",
    "url",
    "seo",
    "roi",
    "saas",
    "crm",
    "cms",
    "erp",
    "smtp",
    "ssl",
    "gdpr",
}


def count_competitors_mentioned(content: str, company_name: str, domain: str) -> int:
    """Count how many other company/brand names appear in the response.

    Uses a heuristic: capitalized multi-word proper nouns that aren't
    common English words or non-competitor entities.
    """
    # Common words to exclude
    common = {
        "the",
        "this",
        "that",
        "these",
        "those",
        "here",
        "there",
        "what",
        "which",
        "when",
        "where",
        "how",
        "why",
        "who",
        "for",
        "not",
        "but",
        "and",
        "with",
        "from",
        "your",
        "their",
        "also",
        "more",
        "most",
        "very",
        "some",
        "many",
        "other",
        "however",
        "therefore",
        "furthermore",
        "additionally",
        "first",
        "second",
        "third",
        "next",
        "then",
        "finally",
        "overall",
        "generally",
        "specifically",
        "particularly",
        "important",
        "key",
        "main",
        "primary",
        "major",
        "based",
        "using",
        "including",
        "regarding",
        "sure",
        "certain",
        "may",
        "might",
        "could",
        "would",
        "should",
        company_name.lower(),
    }

    # Extract capitalized proper noun phrases (2+ words or single known brands)
    # e.g. "Google Analytics", "HubSpot", "Semrush"
    proper_nouns = set()

    # Multi-word capitalized phrases
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", content):
        phrase = match.group(1)
        if phrase.lower() not in common:
            proper_nouns.add(phrase)

    # Single capitalized words that look like brands (PascalCase or ALL_CAPS)
    for match in re.finditer(r"\b([A-Z][a-z]*[A-Z]\w*)\b", content):
        # CamelCase words like HubSpot, SEMrush, etc.
        word = match.group(1)
        if word.lower() not in common and len(word) > 2:
            proper_nouns.add(word)

    # Remove the target company/domain and ignorelisted entities
    cleaned = {
        n
        for n in proper_nouns
        if company_name.lower() not in n.lower()
        and domain.lower() not in n.lower()
        and n.lower() not in _IGNORELIST
    }

    return len(cleaned)


def compute_heuristic_depth(
    mentions_company: bool,
    mentions_url: bool,
    source_framing: str,
    competitors_mentioned: int,
) -> int:
    """Compute a heuristic depth score from free text signals only (no AI call).

    Used as a cross-check against the AI classifier.
    Returns 0-5.
    """
    if not mentions_company:
        return 0

    if source_framing == "absent":
        return 0

    # Base from framing
    framing_scores = {
        "authoritative": 4,
        "recommended": 3,
        "listed": 1,
        "passing": 2,
    }
    base = framing_scores.get(source_framing, 1)

    # Boost for URL citation
    if mentions_url:
        base = min(5, base + 1)

    # Penalize if many competitors listed alongside
    if competitors_mentioned >= 5 and base > 2:
        base = min(base, 2)
    elif competitors_mentioned >= 3 and base > 3:
        base = min(base, 3)

    return base


@dataclass
class TextSignals:
    """Free signals parsed from the observation response text."""

    mention_position: str  # "opening" | "mid" | "closing" | "absent"
    source_framing: str  # "authoritative" | "recommended" | "listed" | "passing" | "absent"
    competitors_mentioned: int
    heuristic_depth: int  # 0-5, cross-check against AI classifier


def parse_text_signals(
    content: str,
    company_name: str,
    domain: str,
    mentions_company: bool = True,
    mentions_url: bool = False,
) -> TextSignals:
    """Extract all free text signals from an observation response."""
    position = detect_mention_position(content, company_name)
    framing = detect_source_framing(content, company_name)
    competitors = count_competitors_mentioned(content, company_name, domain)

    heuristic = compute_heuristic_depth(
        mentions_company=mentions_company,
        mentions_url=mentions_url,
        source_framing=framing,
        competitors_mentioned=competitors,
    )

    return TextSignals(
        mention_position=position,
        source_framing=framing,
        competitors_mentioned=competitors,
        heuristic_depth=heuristic,
    )


# ---------------------------------------------------------------------------
# Batch AI classifier (one call per site, ~$0.001)
# ---------------------------------------------------------------------------

DEPTH_LABELS = {
    0: "NOT_MENTIONED",
    1: "PASSING",
    2: "DESCRIBED",
    3: "RECOMMENDED",
    4: "FEATURED",
    5: "AUTHORITY",
}


def _build_classifier_prompt(
    company_name: str,
    domain: str,
    qa_pairs: list[tuple[str, str]],  # (question, answer_text)
) -> str:
    """Build the batch classification prompt.

    Tightened rubric: depth 5 requires explicit sourcing from the company,
    not just being a well-known brand that gets mentioned.
    """
    lines = [
        f"Company: {company_name} ({domain})",
        "",
        "For each Q&A pair, rate how deeply the answer relies on this company as an information source.",
        "",
        "STRICT SCALE (do not inflate):",
        "  0 = NOT_MENTIONED: Company name does not appear in the answer",
        "  1 = PASSING: Company name-dropped in a list of 3+ alternatives, or mentioned once without elaboration",
        "  2 = DESCRIBED: Answer explains what the company does or offers, but does not use them as a source of information",
        "  3 = RECOMMENDED: Answer actively suggests using the company/product/service as a solution",
        f"  4 = FEATURED: Company is a primary example used to answer the question AND the answer references specific {company_name} content (features, data, pages)",
        f"  5 = AUTHORITY: Answer explicitly cites {company_name} as THE source of information (e.g. 'According to {company_name}...', quotes their data/research, or references specific {domain} URLs)",
        "",
        "IMPORTANT RULES:",
        f"- If the company is mentioned alongside 3+ competitors, MAX score is 2 even if {company_name} gets more text",
        "- Depth 5 requires EXPLICIT attribution ('According to...', 'as X reports...', direct quotes, or specific URL references)",
        "- Being well-known does NOT equal depth 5 — the answer must actually SOURCE information from the company",
        "- When unsure between two levels, choose the LOWER one",
        "",
        "Respond with ONLY a JSON array of integers. Example: [3, 1, 0, 2, 4]",
        "",
    ]

    for i, (question, answer) in enumerate(qa_pairs, 1):
        # Truncate answer to save tokens but keep enough for context
        truncated = answer[:400] + "..." if len(answer) > 400 else answer
        lines.append(f"Q{i}: {question}")
        lines.append(f"A{i}: {truncated}")
        lines.append("")

    return "\n".join(lines)


async def classify_citation_depth_batch(
    company_name: str,
    domain: str,
    qa_pairs: list[tuple[str, str]],
    api_key: str,
    base_url: str = "https://openrouter.ai/api/v1",
    model: str = "openai/gpt-4o-mini",
    is_openai: bool = False,
) -> list[int]:
    """Classify citation depth for all Q&A pairs in ONE API call.

    Args:
        company_name: The company being evaluated
        domain: Company domain
        qa_pairs: List of (question_text, answer_text) tuples
        api_key: API key for the provider
        base_url: API base URL
        model: Model to use (default gpt-4o-mini)
        is_openai: If True, use OpenAI-style headers instead of OpenRouter

    Returns:
        List of integers (0-5), one per Q&A pair.
        Returns all 0s on failure.

    Cost: ~$0.0003-0.001 per call (one call per site, not per question).
    """
    if not qa_pairs:
        return []

    prompt = _build_classifier_prompt(company_name, domain, qa_pairs)

    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }

    if is_openai:
        headers["Authorization"] = f"Bearer {api_key}"
        # Strip "openai/" prefix for direct OpenAI calls
        if model.startswith("openai/"):
            model = model[7:]
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        headers["HTTP-Referer"] = "https://findable.app"
        headers["X-Title"] = "Findable Score Analyzer"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,  # Deterministic classification
        "max_tokens": 200,  # Just need a JSON array
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                print(f"  [citation_depth] API error: {response.status_code}")
                return [0] * len(qa_pairs)

            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Parse the JSON array from the response
            # Handle potential markdown code blocks
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            depths = json.loads(content)

            # Validate
            if not isinstance(depths, list):
                print(f"  [citation_depth] Expected list, got {type(depths)}")
                return [0] * len(qa_pairs)

            # Clamp values to 0-5 and pad/truncate to match input
            depths = [max(0, min(5, int(d))) for d in depths]

            if len(depths) < len(qa_pairs):
                depths.extend([0] * (len(qa_pairs) - len(depths)))
            elif len(depths) > len(qa_pairs):
                depths = depths[: len(qa_pairs)]

            # Report cost estimate
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            est_cost = (prompt_tokens * 0.15 + completion_tokens * 0.6) / 1_000_000
            print(
                f"  [citation_depth] Classified {len(qa_pairs)} pairs "
                f"({prompt_tokens}+{completion_tokens} tokens, ~${est_cost:.4f})"
            )

            return depths

    except json.JSONDecodeError as e:
        print(f"  [citation_depth] JSON parse error: {e}")
        return [0] * len(qa_pairs)
    except Exception as e:
        print(f"  [citation_depth] Error: {e}")
        return [0] * len(qa_pairs)


# ---------------------------------------------------------------------------
# Combined analysis
# ---------------------------------------------------------------------------


@dataclass
class CitationDepthResult:
    """Full citation depth analysis for a single question."""

    question_id: str
    question_text: str

    # AI-classified depth (0-5)
    depth: int
    depth_label: str

    # Heuristic depth from free text parsing (cross-check)
    heuristic_depth: int

    # Free text signals
    mention_position: str
    source_framing: str
    competitors_mentioned: int

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "depth": self.depth,
            "depth_label": self.depth_label,
            "heuristic_depth": self.heuristic_depth,
            "mention_position": self.mention_position,
            "source_framing": self.source_framing,
            "competitors_mentioned": self.competitors_mentioned,
        }


@dataclass
class CitationDepthSummary:
    """Aggregate citation depth for a site observation."""

    avg_depth: float
    avg_heuristic_depth: float
    depth_distribution: dict[int, int]  # {0: 3, 1: 2, 3: 5, ...}
    results: list[CitationDepthResult]

    # Free-signal aggregates
    position_distribution: dict[str, int]  # {"opening": 5, "mid": 3, ...}
    framing_distribution: dict[str, int]  # {"authoritative": 2, "listed": 8, ...}
    avg_competitors: float

    # Batch classifier cost
    classifier_cost_usd: float

    # Divergence between AI classifier and heuristic
    depth_divergence: float  # avg |ai_depth - heuristic_depth|

    # Citable index: % of questions at each depth threshold
    pct_citable: float  # % depth >= 3 ("citable" threshold)
    pct_strongly_sourced: float  # % depth >= 4 ("strongly sourced")

    # Confidence in depth scores based on AI vs heuristic agreement
    confidence: str  # "high" | "medium" | "low"

    def to_dict(self) -> dict:
        return {
            "avg_depth": round(self.avg_depth, 2),
            "avg_heuristic_depth": round(self.avg_heuristic_depth, 2),
            "depth_divergence": round(self.depth_divergence, 2),
            "depth_distribution": self.depth_distribution,
            "pct_citable": round(self.pct_citable, 1),
            "pct_strongly_sourced": round(self.pct_strongly_sourced, 1),
            "confidence": self.confidence,
            "position_distribution": self.position_distribution,
            "framing_distribution": self.framing_distribution,
            "avg_competitors": round(self.avg_competitors, 2),
            "classifier_cost_usd": round(self.classifier_cost_usd, 6),
            "results": [r.to_dict() for r in self.results],
        }


async def analyze_citation_depth(
    company_name: str,
    domain: str,
    observation_results: list,  # list[ObservationResult]
    api_key: str,
    base_url: str = "https://openrouter.ai/api/v1",
    model: str = "openai/gpt-4o-mini",
    is_openai: bool = False,
) -> CitationDepthSummary:
    """Run full citation depth analysis on observation results.

    This is the main entry point. Does both:
    1. Free text parsing on all results
    2. One batch AI call for depth classification

    Cost: ~$0.001 per site (one call, not per question).
    """
    # Collect Q&A pairs and free signals
    qa_pairs: list[tuple[str, str]] = []
    text_signals: list[TextSignals] = []

    for result in observation_results:
        answer = result.response.content if result.response and result.response.success else ""
        mentions_url = result.mentions_url if hasattr(result, "mentions_url") else False
        mentions_company = result.mentions_company if hasattr(result, "mentions_company") else True
        qa_pairs.append((result.question_text, answer))
        text_signals.append(
            parse_text_signals(
                answer,
                company_name,
                domain,
                mentions_company=mentions_company,
                mentions_url=mentions_url,
            )
        )

    # Batch AI classification (ONE call)
    depths = await classify_citation_depth_batch(
        company_name=company_name,
        domain=domain,
        qa_pairs=qa_pairs,
        api_key=api_key,
        base_url=base_url,
        model=model,
        is_openai=is_openai,
    )

    # Estimate cost from token count (rough)
    prompt_chars = sum(len(q) + min(len(a), 400) for q, a in qa_pairs) + 800
    est_cost = (prompt_chars / 4 * 0.15 + 50 * 0.6) / 1_000_000

    # Build per-question results
    results: list[CitationDepthResult] = []
    for i, result in enumerate(observation_results):
        depth = depths[i] if i < len(depths) else 0
        signals = text_signals[i]

        # URL-floor rule: if the response contains a target-domain URL,
        # the AI is actively linking to the company — depth cannot be < 3.
        # Prevents "linked yet not citable" contradictions (e.g. citation_rate=0.85
        # but avg_depth=1.8).
        mentions_url = result.mentions_url if hasattr(result, "mentions_url") else False
        if mentions_url and depth < 3:
            depth = 3

        results.append(
            CitationDepthResult(
                question_id=result.question_id,
                question_text=result.question_text,
                depth=depth,
                depth_label=DEPTH_LABELS.get(depth, "UNKNOWN"),
                heuristic_depth=signals.heuristic_depth,
                mention_position=signals.mention_position,
                source_framing=signals.source_framing,
                competitors_mentioned=signals.competitors_mentioned,
            )
        )

    # Aggregates
    depth_dist: dict[int, int] = {}
    for r in results:
        depth_dist[r.depth] = depth_dist.get(r.depth, 0) + 1

    position_dist: dict[str, int] = {}
    for r in results:
        position_dist[r.mention_position] = position_dist.get(r.mention_position, 0) + 1

    framing_dist: dict[str, int] = {}
    for r in results:
        framing_dist[r.source_framing] = framing_dist.get(r.source_framing, 0) + 1

    avg_depth = sum(r.depth for r in results) / len(results) if results else 0.0
    avg_heuristic = sum(r.heuristic_depth for r in results) / len(results) if results else 0.0
    avg_comp = sum(r.competitors_mentioned for r in results) / len(results) if results else 0.0

    # Divergence: how much do AI and heuristic disagree?
    divergence = (
        sum(abs(r.depth - r.heuristic_depth) for r in results) / len(results) if results else 0.0
    )

    # Citable index thresholds
    n = len(results) if results else 1
    pct_citable = sum(1 for r in results if r.depth >= 3) / n * 100 if results else 0.0
    pct_strongly_sourced = sum(1 for r in results if r.depth >= 4) / n * 100 if results else 0.0

    # Confidence based on AI vs heuristic divergence
    # Low = avg divergence >= 2, Medium = >= 1, High = < 1
    if divergence >= 2.0:
        confidence = "low"
    elif divergence >= 1.0:
        confidence = "medium"
    else:
        confidence = "high"

    return CitationDepthSummary(
        avg_depth=avg_depth,
        avg_heuristic_depth=avg_heuristic,
        depth_distribution=dict(sorted(depth_dist.items())),
        results=results,
        position_distribution=dict(sorted(position_dist.items(), key=lambda x: -x[1])),
        framing_distribution=dict(sorted(framing_dist.items(), key=lambda x: -x[1])),
        avg_competitors=avg_comp,
        classifier_cost_usd=est_cost,
        depth_divergence=divergence,
        pct_citable=pct_citable,
        pct_strongly_sourced=pct_strongly_sourced,
        confidence=confidence,
    )
