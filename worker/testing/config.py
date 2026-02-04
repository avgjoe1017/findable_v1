"""Configuration for test runner."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineConfig:
    """Configuration for the scoring pipeline during testing."""

    # Crawl settings
    max_pages: int = 50  # Limit pages for faster testing
    max_depth: int = 2
    crawl_timeout: int = 30

    # Feature flags
    run_technical: bool = True
    run_structure: bool = True
    run_schema: bool = True
    run_authority: bool = True
    run_simulation: bool = True

    # Performance
    concurrent_extractions: int = 5

    # Caching
    cache_ttl_hours: int = 24  # How long to cache pipeline results


@dataclass
class AIQueryConfig:
    """Configuration for AI query engine."""

    # Systems to query
    query_chatgpt: bool = True
    query_perplexity: bool = True
    query_google_aio: bool = False  # Requires SerpAPI
    query_claude: bool = True

    # Rate limiting (requests per minute)
    chatgpt_rpm: int = 3
    perplexity_rpm: int = 5
    google_aio_rpm: int = 10
    claude_rpm: int = 5

    # Timeouts
    request_timeout: int = 60

    # Caching
    use_cache: bool = True
    cache_ttl_hours: int = 24


@dataclass
class TestRunConfig:
    """Configuration for a complete test run."""

    # Corpus selection
    corpus: str = "full"  # "full", "quick", "own", "competitors", "known_cited"

    # Query selection
    query_filter: str = "all"  # "all", "informational", "tools", "how_to", "technical"

    # Output
    output_dir: Path = field(default_factory=lambda: Path("results"))
    run_name: str | None = None  # Auto-generated if None

    # Behavior
    skip_ai_queries: bool = False  # Use cached ground truth only
    skip_pipeline: bool = False  # Use cached pipeline results only
    verbose: bool = False
    dry_run: bool = False  # Just show what would be done

    # Pipeline config
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)

    # AI query config
    ai_query: AIQueryConfig = field(default_factory=AIQueryConfig)

    # Concurrency
    site_concurrency: int = 3  # How many sites to process in parallel
    query_concurrency: int = 2  # How many AI queries in parallel

    # Checkpointing
    checkpoint_enabled: bool = True
    checkpoint_interval: int = 5  # Checkpoint every N sites

    def __post_init__(self):
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

    @property
    def run_id(self) -> str:
        """Generate a unique run ID."""
        from datetime import UTC, datetime

        if self.run_name:
            return self.run_name
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"validation_{self.corpus}_{timestamp}"

    @property
    def run_output_dir(self) -> Path:
        """Get the output directory for this run."""
        return self.output_dir / self.run_id

    def to_dict(self) -> dict:
        """Serialize config to dict."""
        return {
            "corpus": self.corpus,
            "query_filter": self.query_filter,
            "output_dir": str(self.output_dir),
            "run_name": self.run_name,
            "run_id": self.run_id,
            "skip_ai_queries": self.skip_ai_queries,
            "skip_pipeline": self.skip_pipeline,
            "verbose": self.verbose,
            "dry_run": self.dry_run,
            "site_concurrency": self.site_concurrency,
            "query_concurrency": self.query_concurrency,
            "pipeline": {
                "max_pages": self.pipeline.max_pages,
                "max_depth": self.pipeline.max_depth,
                "run_technical": self.pipeline.run_technical,
                "run_structure": self.pipeline.run_structure,
                "run_schema": self.pipeline.run_schema,
                "run_authority": self.pipeline.run_authority,
                "run_simulation": self.pipeline.run_simulation,
            },
            "ai_query": {
                "query_chatgpt": self.ai_query.query_chatgpt,
                "query_perplexity": self.ai_query.query_perplexity,
                "query_google_aio": self.ai_query.query_google_aio,
                "query_claude": self.ai_query.query_claude,
                "use_cache": self.ai_query.use_cache,
            },
        }
