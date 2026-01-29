"""Tests for render delta detection."""

from worker.crawler.render import (
    RenderDelta,
    RendererConfig,
    RenderMode,
    _jaccard_similarity,
)


class TestJaccardSimilarity:
    """Tests for Jaccard similarity calculation."""

    def test_identical_texts(self) -> None:
        """Identical texts have similarity 1.0."""
        text = "hello world this is a test"
        assert _jaccard_similarity(text, text) == 1.0

    def test_completely_different(self) -> None:
        """Completely different texts have low similarity."""
        text1 = "apple banana cherry"
        text2 = "dog elephant frog"
        assert _jaccard_similarity(text1, text2) == 0.0

    def test_partial_overlap(self) -> None:
        """Partially overlapping texts have intermediate similarity."""
        text1 = "hello world test"
        text2 = "hello world example"
        # Overlap: hello, world (2)
        # Union: hello, world, test, example (4)
        # Jaccard = 2/4 = 0.5
        assert _jaccard_similarity(text1, text2) == 0.5

    def test_empty_texts(self) -> None:
        """Empty texts have similarity 1.0."""
        assert _jaccard_similarity("", "") == 1.0

    def test_one_empty(self) -> None:
        """One empty text has similarity 0.0."""
        assert _jaccard_similarity("hello world", "") == 0.0
        assert _jaccard_similarity("", "hello world") == 0.0

    def test_case_insensitive(self) -> None:
        """Comparison is case insensitive."""
        text1 = "Hello World"
        text2 = "hello world"
        assert _jaccard_similarity(text1, text2) == 1.0

    def test_word_order_irrelevant(self) -> None:
        """Word order doesn't affect similarity."""
        text1 = "the quick brown fox"
        text2 = "fox brown quick the"
        assert _jaccard_similarity(text1, text2) == 1.0


class TestRenderDelta:
    """Tests for RenderDelta dataclass."""

    def test_creates_delta(self) -> None:
        """Can create RenderDelta."""
        delta = RenderDelta(
            static_content="static text",
            rendered_content="rendered text with more words",
            static_word_count=2,
            rendered_word_count=5,
            word_delta=3,
            word_delta_ratio=1.5,
            content_similarity=0.4,
            needs_rendering=True,
            detection_url="https://example.com",
        )

        assert delta.static_word_count == 2
        assert delta.rendered_word_count == 5
        assert delta.word_delta == 3
        assert delta.needs_rendering is True


class TestRendererConfig:
    """Tests for RendererConfig."""

    def test_default_values(self) -> None:
        """Check default configuration values."""
        config = RendererConfig()

        assert config.min_word_delta == 50
        assert config.min_delta_ratio == 0.2
        assert config.similarity_threshold == 0.7
        assert config.wait_for_load == 5000
        assert config.timeout == 30000
        assert config.sample_count == 3

    def test_custom_values(self) -> None:
        """Can set custom configuration."""
        config = RendererConfig(
            min_word_delta=100,
            min_delta_ratio=0.5,
            similarity_threshold=0.8,
        )

        assert config.min_word_delta == 100
        assert config.min_delta_ratio == 0.5
        assert config.similarity_threshold == 0.8


class TestRenderMode:
    """Tests for RenderMode enum."""

    def test_modes(self) -> None:
        """All render modes exist."""
        assert RenderMode.STATIC == "static"
        assert RenderMode.RENDERED == "rendered"
        assert RenderMode.AUTO == "auto"


class TestDeltaLogic:
    """Tests for delta detection logic (without Playwright)."""

    def test_high_word_delta_needs_rendering(self) -> None:
        """High word delta indicates need for rendering."""
        config = RendererConfig(min_word_delta=50, min_delta_ratio=0.2)

        # 100 static words, 200 rendered words
        # Delta = 100, ratio = 1.0 (100%)
        word_delta = 100
        word_delta_ratio = 1.0
        similarity = 0.5

        needs_rendering = (
            word_delta >= config.min_word_delta and word_delta_ratio >= config.min_delta_ratio
        ) or similarity < config.similarity_threshold

        assert needs_rendering is True

    def test_low_delta_no_rendering(self) -> None:
        """Low word delta doesn't require rendering."""
        config = RendererConfig(min_word_delta=50, min_delta_ratio=0.2)

        # 100 static words, 110 rendered words
        # Delta = 10, ratio = 0.1 (10%)
        word_delta = 10
        word_delta_ratio = 0.1
        similarity = 0.95

        needs_rendering = (
            word_delta >= config.min_word_delta and word_delta_ratio >= config.min_delta_ratio
        ) or similarity < config.similarity_threshold

        assert needs_rendering is False

    def test_low_similarity_needs_rendering(self) -> None:
        """Low content similarity indicates need for rendering."""
        config = RendererConfig(similarity_threshold=0.7)

        # Even with low delta, very different content needs rendering
        word_delta = 10
        word_delta_ratio = 0.1
        similarity = 0.3  # Below threshold

        needs_rendering = (
            word_delta >= config.min_word_delta and word_delta_ratio >= config.min_delta_ratio
        ) or similarity < config.similarity_threshold

        assert needs_rendering is True

    def test_high_delta_but_small_ratio_no_rendering(self) -> None:
        """High absolute delta but small ratio doesn't need rendering."""
        config = RendererConfig(min_word_delta=50, min_delta_ratio=0.2)

        # 10000 static words, 10060 rendered words
        # Delta = 60 (above threshold), ratio = 0.006 (below threshold)
        word_delta = 60
        word_delta_ratio = 0.006
        similarity = 0.99

        needs_rendering = (
            word_delta >= config.min_word_delta and word_delta_ratio >= config.min_delta_ratio
        ) or similarity < config.similarity_threshold

        # Both conditions must be true (AND), so this is False
        assert needs_rendering is False


class TestMajorityVoting:
    """Tests for site-level render mode detection logic."""

    def test_majority_needs_rendering(self) -> None:
        """Site needs rendering if majority of samples do."""
        deltas = [
            RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=100,
                rendered_word_count=200,
                word_delta=100,
                word_delta_ratio=1.0,
                content_similarity=0.5,
                needs_rendering=True,
                detection_url="https://example.com/1",
            ),
            RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=100,
                rendered_word_count=200,
                word_delta=100,
                word_delta_ratio=1.0,
                content_similarity=0.5,
                needs_rendering=True,
                detection_url="https://example.com/2",
            ),
            RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=100,
                rendered_word_count=110,
                word_delta=10,
                word_delta_ratio=0.1,
                content_similarity=0.95,
                needs_rendering=False,
                detection_url="https://example.com/3",
            ),
        ]

        needs_rendering_count = sum(1 for d in deltas if d.needs_rendering)
        mode = RenderMode.RENDERED if needs_rendering_count > len(deltas) / 2 else RenderMode.STATIC

        assert mode == RenderMode.RENDERED

    def test_minority_uses_static(self) -> None:
        """Site uses static if minority of samples need rendering."""
        deltas = [
            RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=100,
                rendered_word_count=200,
                word_delta=100,
                word_delta_ratio=1.0,
                content_similarity=0.5,
                needs_rendering=True,
                detection_url="https://example.com/1",
            ),
            RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=100,
                rendered_word_count=105,
                word_delta=5,
                word_delta_ratio=0.05,
                content_similarity=0.98,
                needs_rendering=False,
                detection_url="https://example.com/2",
            ),
            RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=100,
                rendered_word_count=110,
                word_delta=10,
                word_delta_ratio=0.1,
                content_similarity=0.95,
                needs_rendering=False,
                detection_url="https://example.com/3",
            ),
        ]

        needs_rendering_count = sum(1 for d in deltas if d.needs_rendering)
        mode = RenderMode.RENDERED if needs_rendering_count > len(deltas) / 2 else RenderMode.STATIC

        assert mode == RenderMode.STATIC
