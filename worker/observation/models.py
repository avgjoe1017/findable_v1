"""Data models for observation layer."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ProviderType(StrEnum):
    """Supported observation providers."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class ObservationStatus(StrEnum):
    """Status of an observation request."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some responses succeeded


@dataclass
class UsageStats:
    """Token usage and cost tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, other: "UsageStats") -> "UsageStats":
        """Add another UsageStats to this one."""
        return UsageStats(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated_cost_usd=self.estimated_cost_usd + other.estimated_cost_usd,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


@dataclass
class ProviderError:
    """Error from a provider."""

    provider: ProviderType
    error_type: str
    message: str
    retryable: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "provider": self.provider.value,
            "error_type": self.error_type,
            "message": self.message,
            "retryable": self.retryable,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ObservationRequest:
    """A single observation request (question to ask an AI model)."""

    id: UUID = field(default_factory=uuid4)
    question_id: str = ""
    question_text: str = ""
    company_name: str = ""
    domain: str = ""

    # Optional context to include in prompt
    context: str = ""

    # Model settings
    model: str = "openai/gpt-4o-mini"  # Default model
    temperature: float = 0.3  # Low for consistency
    max_tokens: int = 1024

    def to_prompt(self) -> str:
        """Generate the observation prompt."""
        prompt = f"""I'm researching information about {self.company_name}.

Question: {self.question_text}

Please provide a detailed, factual answer based on your knowledge. If you can cite specific sources or websites, please include them. If you're not sure about something, say so."""

        if self.context:
            prompt = f"{self.context}\n\n{prompt}"

        return prompt

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "question_id": self.question_id,
            "question_text": self.question_text,
            "company_name": self.company_name,
            "domain": self.domain,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


@dataclass
class ObservationResponse:
    """Response from a single observation."""

    request_id: UUID
    provider: ProviderType
    model: str

    # Response content
    content: str
    raw_response: dict = field(default_factory=dict)

    # Metrics
    usage: UsageStats = field(default_factory=UsageStats)
    latency_ms: float = 0.0

    # Status
    success: bool = True
    error: ProviderError | None = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "request_id": str(self.request_id),
            "provider": self.provider.value,
            "model": self.model,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "usage": self.usage.to_dict(),
            "latency_ms": round(self.latency_ms, 2),
            "success": self.success,
            "error": self.error.to_dict() if self.error else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ObservationResult:
    """Result of observing a single question."""

    question_id: str
    question_text: str
    company_name: str
    domain: str

    # The response
    response: ObservationResponse | None = None

    # Parsed signals (filled in by parsing layer)
    mentions_company: bool = False
    mentions_domain: bool = False
    mentions_url: bool = False
    cited_urls: list[str] = field(default_factory=list)
    confidence_expressed: str = ""  # "high", "medium", "low", "unknown"

    # Citation depth (0-5 scale, filled by citation_depth module)
    citation_depth: int = 0  # 0=not_mentioned ... 5=authority
    citation_depth_label: str = ""  # Human-readable label
    heuristic_depth: int = 0  # 0-5, cross-check from free text signals
    mention_position: str = ""  # "first_sentence" | "first_paragraph" | "body" | "absent"
    source_framing: str = ""  # "authoritative" | "recommended" | "listed" | "passing" | "absent"
    competitors_mentioned: int = 0

    # For comparison with simulation
    simulation_predicted: str = ""  # What simulation thought
    observation_actual: str = ""  # What model actually said

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "company_name": self.company_name,
            "domain": self.domain,
            "response": self.response.to_dict() if self.response else None,
            "mentions_company": self.mentions_company,
            "mentions_domain": self.mentions_domain,
            "mentions_url": self.mentions_url,
            "cited_urls": self.cited_urls,
            "confidence_expressed": self.confidence_expressed,
            "citation_depth": self.citation_depth,
            "citation_depth_label": self.citation_depth_label,
            "heuristic_depth": self.heuristic_depth,
            "mention_position": self.mention_position,
            "source_framing": self.source_framing,
            "competitors_mentioned": self.competitors_mentioned,
        }


@dataclass
class ObservationRun:
    """A complete observation run for a site."""

    id: UUID = field(default_factory=uuid4)
    site_id: UUID | None = None
    run_id: UUID | None = None  # Link to simulation run
    company_name: str = ""
    domain: str = ""

    # Configuration
    provider: ProviderType = ProviderType.OPENROUTER
    model: str = "openai/gpt-4o-mini"

    # Results
    results: list[ObservationResult] = field(default_factory=list)
    status: ObservationStatus = ObservationStatus.PENDING

    # Aggregates
    total_questions: int = 0
    questions_completed: int = 0
    questions_failed: int = 0

    # Mention rates
    company_mention_rate: float = 0.0
    domain_mention_rate: float = 0.0
    citation_rate: float = 0.0

    # Citation depth (filled by citation_depth module)
    avg_citation_depth: float = 0.0  # 0.0-5.0 scale

    # Usage
    total_usage: UsageStats = field(default_factory=UsageStats)
    total_latency_ms: float = 0.0

    # Errors
    errors: list[ProviderError] = field(default_factory=list)

    # Metadata
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def add_result(self, result: ObservationResult) -> None:
        """Add a result and update aggregates."""
        self.results.append(result)

        if result.response:
            if result.response.success:
                self.questions_completed += 1
                self.total_usage = self.total_usage.add(result.response.usage)
                self.total_latency_ms += result.response.latency_ms
            else:
                self.questions_failed += 1
                if result.response.error:
                    self.errors.append(result.response.error)

        self._update_mention_rates()

    def _update_mention_rates(self) -> None:
        """Update mention rate calculations."""
        if not self.results:
            return

        completed = [r for r in self.results if r.response and r.response.success]
        if not completed:
            return

        total = len(completed)
        self.company_mention_rate = sum(1 for r in completed if r.mentions_company) / total
        self.domain_mention_rate = sum(1 for r in completed if r.mentions_domain) / total
        self.citation_rate = sum(1 for r in completed if r.mentions_url) / total

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "site_id": str(self.site_id) if self.site_id else None,
            "run_id": str(self.run_id) if self.run_id else None,
            "company_name": self.company_name,
            "domain": self.domain,
            "provider": self.provider.value,
            "model": self.model,
            "status": self.status.value,
            "total_questions": self.total_questions,
            "questions_completed": self.questions_completed,
            "questions_failed": self.questions_failed,
            "avg_citation_depth": round(self.avg_citation_depth, 2),
            "company_mention_rate": round(self.company_mention_rate, 3),
            "domain_mention_rate": round(self.domain_mention_rate, 3),
            "citation_rate": round(self.citation_rate, 3),
            "total_usage": self.total_usage.to_dict(),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "errors": [e.to_dict() for e in self.errors],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "results": [r.to_dict() for r in self.results],
        }
