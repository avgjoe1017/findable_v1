"""Tests for run schemas."""

from api.schemas.run import RunConfig, RunCreate, RunProgress


def test_run_config_defaults() -> None:
    """Test RunConfig default values."""
    config = RunConfig()
    assert config.include_observation is True
    assert config.include_benchmark is True
    assert config.bands == ["conservative", "typical", "generous"]
    assert config.provider == {"preferred": "router", "model": "auto"}
    assert config.question_set_id is None


def test_run_create_defaults() -> None:
    """Test RunCreate default values."""
    run = RunCreate()
    assert run.run_type == "starter_audit"
    assert run.config.include_observation is True


def test_run_progress() -> None:
    """Test RunProgress model."""
    progress = RunProgress(
        pages_crawled=50,
        pages_total=100,
        chunks_created=150,
        current_step="chunking",
    )
    assert progress.pages_crawled == 50
    assert progress.pages_total == 100
    assert progress.chunks_created == 150
    assert progress.current_step == "chunking"
    assert progress.questions_processed == 0
