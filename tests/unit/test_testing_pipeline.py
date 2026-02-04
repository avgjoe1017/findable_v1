"""Tests for the testing pipeline executor module."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from worker.testing.config import PipelineConfig
from worker.testing.pipeline import (
    PillarScores,
    PipelineResult,
    QuestionResult,
    get_cache_key,
    load_cached_result,
    run_pipeline,
    run_pipeline_batch,
    save_cached_result,
)


class TestPillarScores:
    """Tests for PillarScores dataclass."""

    def test_default_values(self):
        """PillarScores has None defaults."""
        scores = PillarScores()

        assert scores.technical is None
        assert scores.structure is None
        assert scores.schema is None
        assert scores.authority is None
        assert scores.retrieval is None
        assert scores.coverage is None

    def test_with_values(self):
        """PillarScores can be created with values."""
        scores = PillarScores(
            technical=85.0,
            structure=72.0,
            schema=90.0,
            authority=65.0,
            retrieval=78.0,
            coverage=80.0,
        )

        assert scores.technical == 85.0
        assert scores.structure == 72.0
        assert scores.schema == 90.0
        assert scores.authority == 65.0
        assert scores.retrieval == 78.0
        assert scores.coverage == 80.0

    def test_to_dict(self):
        """PillarScores serializes correctly."""
        scores = PillarScores(technical=85.0, structure=72.0)

        data = scores.to_dict()

        assert data["technical"] == 85.0
        assert data["structure"] == 72.0
        assert data["schema"] is None


class TestQuestionResult:
    """Tests for QuestionResult dataclass."""

    def test_create_question_result(self):
        """QuestionResult can be created with required fields."""
        result = QuestionResult(
            question_id="q-123",
            question_text="What is SEO?",
            category="informational",
            answerability="fully",
            score=0.85,
            confidence=0.9,
            chunks_found=5,
        )

        assert result.question_id == "q-123"
        assert result.question_text == "What is SEO?"
        assert result.answerability == "fully"
        assert result.score == 0.85
        assert result.chunks_found == 5

    def test_to_dict(self):
        """QuestionResult serializes correctly."""
        result = QuestionResult(
            question_id="q-123",
            question_text="What is SEO?",
            category="informational",
            answerability="fully",
            score=0.85,
            confidence=0.9,
            chunks_found=5,
            top_chunk_relevance=0.92,
        )

        data = result.to_dict()

        assert data["question_id"] == "q-123"
        assert data["score"] == 0.85
        assert data["top_chunk_relevance"] == 0.92


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_create_success_result(self):
        """PipelineResult can be created for success."""
        result = PipelineResult(
            url="https://example.com",
            domain="example.com",
            status="success",
            overall_score=75.0,
            pillar_scores=PillarScores(technical=80.0),
            questions_answered=10,
            questions_partial=3,
            questions_unanswered=2,
            pages_crawled=15,
            chunks_created=50,
        )

        assert result.url == "https://example.com"
        assert result.status == "success"
        assert result.overall_score == 75.0
        assert result.questions_answered == 10

    def test_create_failed_result(self):
        """PipelineResult can be created for failure."""
        result = PipelineResult(
            url="https://example.com",
            domain="example.com",
            status="failed",
            overall_score=0.0,
            pillar_scores=PillarScores(),
            error_message="Connection timeout",
        )

        assert result.status == "failed"
        assert result.error_message == "Connection timeout"

    def test_to_dict(self):
        """PipelineResult serializes correctly."""
        result = PipelineResult(
            url="https://example.com",
            domain="example.com",
            status="success",
            overall_score=75.0,
            pillar_scores=PillarScores(technical=80.0),
            question_results=[
                QuestionResult(
                    question_id="q-1",
                    question_text="test",
                    category="informational",
                    answerability="fully",
                    score=0.9,
                    confidence=0.85,
                    chunks_found=3,
                )
            ],
        )

        data = result.to_dict()

        assert data["url"] == "https://example.com"
        assert data["status"] == "success"
        assert data["pillar_scores"]["technical"] == 80.0
        assert len(data["question_results"]) == 1

    def test_from_dict(self):
        """PipelineResult deserializes correctly."""
        data = {
            "url": "https://example.com",
            "domain": "example.com",
            "status": "success",
            "overall_score": 75.0,
            "pillar_scores": {"technical": 80.0, "structure": None},
            "question_results": [
                {
                    "question_id": "q-1",
                    "question_text": "test",
                    "category": "informational",
                    "answerability": "fully",
                    "score": 0.9,
                    "confidence": 0.85,
                    "chunks_found": 3,
                }
            ],
            "questions_answered": 10,
            "pages_crawled": 15,
            "executed_at": "2026-02-02T12:00:00+00:00",
        }

        result = PipelineResult.from_dict(data)

        assert result.url == "https://example.com"
        assert result.overall_score == 75.0
        assert result.pillar_scores.technical == 80.0
        assert len(result.question_results) == 1

    def test_roundtrip_serialization(self):
        """PipelineResult survives roundtrip serialization."""
        original = PipelineResult(
            url="https://test.com",
            domain="test.com",
            status="success",
            overall_score=82.5,
            pillar_scores=PillarScores(
                technical=85.0,
                structure=80.0,
                schema=75.0,
            ),
            question_results=[
                QuestionResult(
                    question_id="q-1",
                    question_text="What is X?",
                    category="informational",
                    answerability="partially",
                    score=0.6,
                    confidence=0.7,
                    chunks_found=2,
                )
            ],
            questions_answered=8,
            questions_partial=4,
            questions_unanswered=3,
        )

        data = original.to_dict()
        restored = PipelineResult.from_dict(data)

        assert restored.url == original.url
        assert restored.overall_score == original.overall_score
        assert restored.pillar_scores.technical == original.pillar_scores.technical
        assert len(restored.question_results) == len(original.question_results)


class TestCaching:
    """Tests for caching functions."""

    def test_get_cache_key_deterministic(self):
        """Cache key is deterministic for same inputs."""
        config = PipelineConfig(max_pages=20, max_depth=3)

        key1 = get_cache_key("https://example.com", config)
        key2 = get_cache_key("https://example.com", config)

        assert key1 == key2

    def test_get_cache_key_varies_by_url(self):
        """Cache key varies by URL."""
        config = PipelineConfig()

        key1 = get_cache_key("https://example.com", config)
        key2 = get_cache_key("https://other.com", config)

        assert key1 != key2

    def test_get_cache_key_varies_by_config(self):
        """Cache key varies by config."""
        config1 = PipelineConfig(max_pages=20)
        config2 = PipelineConfig(max_pages=50)

        key1 = get_cache_key("https://example.com", config1)
        key2 = get_cache_key("https://example.com", config2)

        assert key1 != key2

    def test_save_and_load_cached_result(self):
        """Can save and load cached results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = PipelineConfig(cache_ttl_hours=24)

            result = PipelineResult(
                url="https://example.com",
                domain="example.com",
                status="success",
                overall_score=75.0,
                pillar_scores=PillarScores(technical=80.0),
            )

            # Save
            save_cached_result(result, config, cache_dir)

            # Load
            loaded = load_cached_result("https://example.com", config, cache_dir)

            assert loaded is not None
            assert loaded.url == "https://example.com"
            assert loaded.overall_score == 75.0
            assert loaded.status == "cached"

    def test_load_cached_result_not_found(self):
        """Returns None when cache miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = PipelineConfig()

            result = load_cached_result("https://nonexistent.com", config, cache_dir)

            assert result is None

    def test_load_cached_result_expired(self):
        """Returns None when cache is expired."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = PipelineConfig(cache_ttl_hours=0)  # Immediate expiry

            result = PipelineResult(
                url="https://example.com",
                domain="example.com",
                status="success",
                overall_score=75.0,
                pillar_scores=PillarScores(),
            )

            # Save with old timestamp
            result.cached_at = "2020-01-01T00:00:00+00:00"
            cache_key = get_cache_key("https://example.com", config)
            cache_file = cache_dir / f"pipeline_{cache_key}.json"
            cache_dir.mkdir(parents=True, exist_ok=True)

            with open(cache_file, "w") as f:
                json.dump(result.to_dict(), f)

            # Load - should return None due to expiry
            loaded = load_cached_result("https://example.com", config, cache_dir)

            assert loaded is None


class TestRunPipeline:
    """Tests for run_pipeline function."""

    @pytest.mark.asyncio
    async def test_run_pipeline_uses_cache(self):
        """run_pipeline uses cached results when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = PipelineConfig(cache_ttl_hours=24)

            # Pre-populate cache
            cached_result = PipelineResult(
                url="https://cached.com",
                domain="cached.com",
                status="success",
                overall_score=85.0,
                pillar_scores=PillarScores(technical=90.0),
                cached_at=datetime.now(UTC).isoformat(),
            )
            save_cached_result(cached_result, config, cache_dir)

            # Run pipeline - should use cache
            result = await run_pipeline(
                url="https://cached.com",
                config=config,
                cache_dir=cache_dir,
                use_cache=True,
            )

            assert result.status == "cached"
            assert result.overall_score == 85.0

    @pytest.mark.asyncio
    @patch("worker.testing.pipeline.crawl_site")
    async def test_run_pipeline_handles_crawl_failure(self, mock_crawl):
        """run_pipeline handles crawl failures gracefully."""
        mock_crawl.side_effect = Exception("Connection refused")

        result = await run_pipeline(
            url="https://failing.com",
            use_cache=False,
        )

        assert result.status == "failed"
        assert "Connection refused" in result.error_message

    @pytest.mark.asyncio
    @patch("worker.testing.pipeline.crawl_site")
    async def test_run_pipeline_handles_empty_crawl(self, mock_crawl):
        """run_pipeline handles empty crawl results."""
        mock_result = MagicMock()
        mock_result.pages = []
        mock_crawl.return_value = mock_result

        result = await run_pipeline(
            url="https://empty.com",
            use_cache=False,
        )

        assert result.status == "failed"
        assert "No pages crawled" in result.error_message


class TestRunPipelineBatch:
    """Tests for run_pipeline_batch function."""

    @pytest.mark.asyncio
    async def test_run_pipeline_batch_uses_cache(self):
        """run_pipeline_batch uses cached results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            config = PipelineConfig(cache_ttl_hours=24)

            # Pre-populate cache for one URL
            cached_result = PipelineResult(
                url="https://cached.com",
                domain="cached.com",
                status="success",
                overall_score=85.0,
                pillar_scores=PillarScores(),
                cached_at=datetime.now(UTC).isoformat(),
            )
            save_cached_result(cached_result, config, cache_dir)

            # Run batch with one cached URL
            results = await run_pipeline_batch(
                urls=["https://cached.com"],
                config=config,
                cache_dir=cache_dir,
                use_cache=True,
                concurrency=1,
            )

            assert len(results) == 1
            assert results[0].status == "cached"

    @pytest.mark.asyncio
    @patch("worker.testing.pipeline.run_pipeline")
    async def test_run_pipeline_batch_handles_exceptions(self, mock_run):
        """run_pipeline_batch handles exceptions gracefully."""
        # First call succeeds, second fails
        mock_run.side_effect = [
            PipelineResult(
                url="https://success.com",
                domain="success.com",
                status="success",
                overall_score=80.0,
                pillar_scores=PillarScores(),
            ),
            Exception("Network error"),
        ]

        results = await run_pipeline_batch(
            urls=["https://success.com", "https://failing.com"],
            use_cache=False,
            concurrency=2,
        )

        assert len(results) == 2
        assert results[0].status == "success"
        assert results[1].status == "failed"
        assert "Network error" in results[1].error_message

    @pytest.mark.asyncio
    @patch("worker.testing.pipeline.run_pipeline")
    async def test_run_pipeline_batch_respects_concurrency(self, mock_run):
        """run_pipeline_batch respects concurrency limit."""
        import asyncio

        concurrent_count = 0
        max_concurrent = 0

        async def track_concurrency(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate work
            concurrent_count -= 1
            return PipelineResult(
                url=args[0],
                domain="test.com",
                status="success",
                overall_score=80.0,
                pillar_scores=PillarScores(),
            )

        mock_run.side_effect = track_concurrency

        await run_pipeline_batch(
            urls=[f"https://site{i}.com" for i in range(10)],
            use_cache=False,
            concurrency=3,
        )

        # Max concurrent should not exceed limit
        assert max_concurrent <= 3


class TestPipelineConfig:
    """Tests for PipelineConfig integration."""

    def test_default_config(self):
        """PipelineConfig has sensible defaults."""
        config = PipelineConfig()

        assert config.max_pages == 50
        assert config.max_depth == 2
        assert config.cache_ttl_hours == 24

    def test_custom_config(self):
        """PipelineConfig accepts custom values."""
        config = PipelineConfig(
            max_pages=100,
            max_depth=5,
            cache_ttl_hours=48,
        )

        assert config.max_pages == 100
        assert config.max_depth == 5
        assert config.cache_ttl_hours == 48
