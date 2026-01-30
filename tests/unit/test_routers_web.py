"""Tests for web routes (Jinja2 HTML pages)."""

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestDashboardRoute:
    """Tests for dashboard route."""

    def test_dashboard_returns_html(self, client: TestClient) -> None:
        """Dashboard returns HTML response."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_contains_title(self, client: TestClient) -> None:
        """Dashboard contains expected title."""
        response = client.get("/")

        assert b"Findable" in response.content
        assert b"Your Sites" in response.content

    def test_dashboard_has_add_site_link(self, client: TestClient) -> None:
        """Dashboard has link to add site."""
        response = client.get("/")

        assert b"/sites/new" in response.content


class TestNewSiteRoute:
    """Tests for new site route."""

    def test_new_site_form_returns_html(self, client: TestClient) -> None:
        """New site form returns HTML response."""
        response = client.get("/sites/new")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_new_site_form_has_fields(self, client: TestClient) -> None:
        """New site form has required fields."""
        response = client.get("/sites/new")

        assert b'name="domain"' in response.content
        assert b'name="name"' in response.content
        assert b'name="business_model"' in response.content
        assert b'name="competitors"' in response.content

    def test_new_site_form_has_business_models(self, client: TestClient) -> None:
        """New site form has business model options."""
        response = client.get("/sites/new")

        assert b"B2B SaaS" in response.content
        assert b"E-Commerce" in response.content


class TestTemplateFilters:
    """Tests for template filters."""

    def test_get_grade_class(self) -> None:
        """Test grade class helper."""
        from api.routers.web import get_grade_class

        assert get_grade_class("A") == "grade-a"
        assert get_grade_class("B+") == "grade-b"
        assert get_grade_class("C-") == "grade-c"
        assert get_grade_class("D") == "grade-d"
        assert get_grade_class("F") == "grade-f"
        assert get_grade_class("") == "grade-c"

    def test_get_score_class(self) -> None:
        """Test score class helper."""
        from api.routers.web import get_score_class

        assert get_score_class(85) == "score-excellent"
        assert get_score_class(65) == "score-good"
        assert get_score_class(45) == "score-fair"
        assert get_score_class(30) == "score-poor"
        assert get_score_class(None) == "score-fair"

    def test_format_trend(self) -> None:
        """Test trend formatting."""
        from api.routers.web import format_trend

        assert format_trend(80, 70) == "+10"
        assert format_trend(70, 80) == "-10"
        assert format_trend(70, 70) == "0"
        assert format_trend(None, 70) == "—"
        assert format_trend(70, None) == "—"


class TestScoreToGrade:
    """Tests for score to grade conversion."""

    def test_score_to_grade(self) -> None:
        """Test score to grade mapping."""
        from api.routers.web import _score_to_grade

        assert _score_to_grade(95) == "A"
        assert _score_to_grade(85) == "A-"
        assert _score_to_grade(77) == "B+"
        assert _score_to_grade(72) == "B"
        assert _score_to_grade(67) == "B-"
        assert _score_to_grade(62) == "C+"
        assert _score_to_grade(57) == "C"
        assert _score_to_grade(52) == "C-"
        assert _score_to_grade(47) == "D+"
        assert _score_to_grade(42) == "D"
        assert _score_to_grade(35) == "F"
        assert _score_to_grade(None) == "—"


class TestPriorityToSeverity:
    """Tests for priority to severity conversion."""

    def test_priority_mapping(self) -> None:
        """Test priority to severity mapping."""
        from api.routers.web import _priority_to_severity

        assert _priority_to_severity(1) == "critical"
        assert _priority_to_severity(2) == "high"
        assert _priority_to_severity(3) == "medium"
        assert _priority_to_severity(4) == "low"
        assert _priority_to_severity(5) == "low"


class TestFormatLastRun:
    """Tests for last run formatting."""

    def test_format_last_run_never(self) -> None:
        """Returns Never for no report."""
        from api.routers.web import _format_last_run

        assert _format_last_run(None) == "Never"

    def test_format_last_run_with_report(self) -> None:
        """Returns human-readable time for report."""
        from datetime import UTC, datetime, timedelta

        from api.routers.web import _format_last_run

        class MockReport:
            created_at = datetime.now(UTC) - timedelta(hours=2)

        result = _format_last_run(MockReport())
        assert "hour" in result


class TestCategoryWeight:
    """Tests for category weight lookup."""

    def test_get_category_weight(self) -> None:
        """Test category weight lookup."""
        from api.routers.web import _get_category_weight

        assert _get_category_weight("identity") == 0.25
        assert _get_category_weight("offerings") == 0.30
        assert _get_category_weight("contact") == 0.15
        assert _get_category_weight("trust") == 0.15
        assert _get_category_weight("differentiation") == 0.15
        # Unknown category gets default weight
        assert _get_category_weight("unknown") == 0.20


class TestFormatDate:
    """Tests for date formatting."""

    def test_format_date_iso(self) -> None:
        """Formats ISO date string."""
        from api.routers.web import _format_date

        result = _format_date("2026-01-28T10:30:00Z")
        assert "January" in result
        assert "28" in result
        assert "2026" in result

    def test_format_date_none(self) -> None:
        """Returns Unknown for None."""
        from api.routers.web import _format_date

        assert _format_date(None) == "Unknown"
