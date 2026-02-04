"""Unit tests for Phase 1 Technical Readiness checks."""

from unittest.mock import patch

import pytest

from worker.crawler.llms_txt import (
    LlmsTxtChecker,
    LlmsTxtResult,
)
from worker.crawler.performance import (
    TTFBResult,
    _calculate_ttfb_score,
)
from worker.crawler.robots_ai import (
    AI_CRAWLERS,
    AIRobotsChecker,
    RobotsTxtAIResult,
)
from worker.extraction.js_detection import (
    JSDetectionResult,
    detect_js_dependency,
    needs_rendering,
)
from worker.scoring.technical import (
    calculate_technical_score,
)


class TestRobotsAI:
    """Tests for AI crawler access checking."""

    def test_ai_crawlers_defined(self):
        """Verify all major AI crawlers are defined."""
        assert "GPTBot" in AI_CRAWLERS
        assert "ClaudeBot" in AI_CRAWLERS
        assert "PerplexityBot" in AI_CRAWLERS
        assert "Google-Extended" in AI_CRAWLERS

    def test_required_crawlers_marked(self):
        """Verify critical crawlers are marked as required."""
        assert AI_CRAWLERS["GPTBot"]["required"] is True
        assert AI_CRAWLERS["ClaudeBot"]["required"] is True
        assert AI_CRAWLERS["PerplexityBot"]["required"] is True

    @pytest.mark.asyncio
    async def test_no_robots_txt_allows_all(self):
        """When robots.txt doesn't exist, all crawlers should be allowed."""
        checker = AIRobotsChecker()

        with patch.object(checker, "_fetch_robots_txt", return_value=None):
            result = await checker.check("https://example.com")

        assert result.robots_txt_exists is False
        assert result.all_allowed is True
        assert result.score == 100.0
        assert len(result.critical_blocked) == 0

    @pytest.mark.asyncio
    async def test_blocking_gptbot_reduces_score(self):
        """Blocking GPTBot should significantly reduce score."""
        checker = AIRobotsChecker()
        robots_content = """
User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""

        with patch.object(checker, "_fetch_robots_txt", return_value=robots_content):
            result = await checker.check("https://example.com")

        assert result.robots_txt_exists is True
        assert result.crawlers["GPTBot"].allowed is False
        assert "GPTBot" in result.critical_blocked
        assert result.score < 100.0


class TestPerformance:
    """Tests for TTFB measurement."""

    def test_ttfb_score_excellent(self):
        """TTFB under 200ms should score 100."""
        score, level = _calculate_ttfb_score(150)
        assert score == 100.0
        assert level == "excellent"

    def test_ttfb_score_good(self):
        """TTFB 200-500ms should score well."""
        score, level = _calculate_ttfb_score(350)
        assert 80 <= score <= 100
        assert level == "good"

    def test_ttfb_score_critical(self):
        """TTFB over 2000ms should be critical."""
        score, level = _calculate_ttfb_score(2500)
        assert score < 25
        assert level == "critical"

    def test_ttfb_result_properties(self):
        """Test TTFBResult helper properties."""
        result = TTFBResult(
            url="https://example.com",
            ttfb_ms=300,
            score=90,
            level="good",
        )
        assert result.is_acceptable is True
        assert result.is_critical is False

        critical = TTFBResult(
            url="https://example.com",
            ttfb_ms=2500,
            score=0,
            level="critical",
        )
        assert critical.is_critical is True


class TestLlmsTxt:
    """Tests for llms.txt detection."""

    @pytest.mark.asyncio
    async def test_no_llms_txt(self):
        """Missing llms.txt should return exists=False."""
        checker = LlmsTxtChecker()

        with patch.object(checker, "_fetch_llms_txt", return_value=None):
            result = await checker.check("https://example.com")

        assert result.exists is False
        assert result.quality_score == 0.0
        assert result.level == "missing"

    @pytest.mark.asyncio
    async def test_well_formed_llms_txt(self):
        """Well-formed llms.txt should score well."""
        checker = LlmsTxtChecker()
        content = """# Example Company

> We provide AI-powered analytics

## Products
- [Product A](/products/a): Main product
- [Product B](/products/b): Secondary product

## Documentation
- [Getting Started](/docs/start): Quick start guide
"""

        with patch.object(checker, "_fetch_llms_txt", return_value=content):
            result = await checker.check("https://example.com")

        assert result.exists is True
        assert result.has_title is True
        assert result.has_description is True
        assert result.has_sections is True
        assert result.has_links is True
        assert result.link_count == 3  # 3 links in the content
        assert result.quality_score >= 60  # Good score with 3 links


class TestJSDetection:
    """Tests for JavaScript dependency detection."""

    def test_static_html_not_js_dependent(self):
        """Plain HTML should not be flagged as JS dependent."""
        # Need sufficient content length (500+ chars in main area)
        long_content = "x" * 600
        html = f"""
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <main>
        <h1>Welcome to Our Site</h1>
        <p>{long_content}</p>
    </main>
</body>
</html>
"""
        result = detect_js_dependency(html)

        assert result.likely_js_dependent is False
        assert result.score >= 80

    def test_react_spa_detected(self):
        """React SPA with minimal content should be flagged."""
        html = """
<!DOCTYPE html>
<html>
<head><title>React App</title></head>
<body>
    <div id="root"></div>
    <script src="/bundle.js"></script>
</body>
</html>
"""
        result = detect_js_dependency(html)

        assert result.framework_detected == "React"
        assert result.likely_js_dependent is True
        assert result.score < 50

    def test_nextjs_ssr_not_flagged(self):
        """Next.js with SSR content should not be flagged as JS dependent."""
        # SSR Next.js has real content, need 500+ chars
        long_content = "x" * 600
        html = f"""
<!DOCTYPE html>
<html>
<head><title>Next.js SSR</title></head>
<body>
    <div id="__next">
        <main>
            <h1>Server Rendered Content</h1>
            <p>{long_content}</p>
        </main>
    </div>
</body>
</html>
"""
        result = detect_js_dependency(html)

        assert result.framework_detected == "Next.js"
        # SSR Next.js should have content, so not JS dependent
        assert result.main_content_length > 500
        # With sufficient content, should not be flagged despite framework detection
        assert result.likely_js_dependent is False

    def test_needs_rendering_helper(self):
        """Test the needs_rendering convenience function."""
        spa_html = '<div id="root"></div>'
        assert needs_rendering(spa_html) is True

        static_html = "<main><p>" + "x" * 600 + "</p></main>"
        assert needs_rendering(static_html) is False


class TestTechnicalScore:
    """Tests for combined technical score calculation."""

    def test_all_good_scores_100(self):
        """All good results should score near 100."""
        robots = RobotsTxtAIResult(
            domain="example.com",
            robots_txt_exists=False,
            robots_txt_url="https://example.com/robots.txt",
            score=100.0,
            all_allowed=True,
        )

        ttfb = TTFBResult(
            url="https://example.com",
            ttfb_ms=150,
            score=100.0,
            level="excellent",
        )

        llms = LlmsTxtResult(
            domain="example.com",
            exists=True,
            url="https://example.com/llms.txt",
            quality_score=100.0,
            level="excellent",
            has_title=True,
            has_description=True,
            has_links=True,
            link_count=10,
        )

        js = JSDetectionResult(
            url="https://example.com",
            likely_js_dependent=False,
            confidence="low",
            score=100.0,
            main_content_length=5000,  # Good content length
            content_length=10000,
        )

        score = calculate_technical_score(
            robots_result=robots,
            ttfb_result=ttfb,
            llms_txt_result=llms,
            js_result=js,
            is_https=True,
        )

        assert score.total_score == 100.0
        assert score.level == "good"
        assert len(score.critical_issues) == 0

    def test_blocked_crawlers_critical(self):
        """Blocked AI crawlers should create critical issues."""
        robots = RobotsTxtAIResult(
            domain="example.com",
            robots_txt_exists=True,
            robots_txt_url="https://example.com/robots.txt",
            score=50.0,
            critical_blocked=["GPTBot", "ClaudeBot"],
        )

        score = calculate_technical_score(robots_result=robots)

        assert len(score.critical_issues) > 0
        assert any("GPTBot" in issue for issue in score.critical_issues)
        assert score.level in ["warning", "critical"]

    def test_show_the_math_output(self):
        """show_the_math should produce readable output."""
        score = calculate_technical_score(is_https=True)

        output = score.show_the_math()

        assert "TECHNICAL READINESS SCORE" in output
        assert "COMPONENT BREAKDOWN" in output
        assert "robots.txt" in output.lower() or "robots" in output.lower()

    def test_to_dict_serializable(self):
        """to_dict should produce JSON-serializable output."""
        import json

        score = calculate_technical_score(is_https=True)
        data = score.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0


class TestIntegration:
    """Integration tests for the complete technical check flow."""

    @pytest.mark.asyncio
    async def test_full_check_flow(self):
        """Test the complete technical check flow."""
        from worker.tasks.technical_check import run_technical_checks

        # Mock all network calls
        with (
            patch("worker.crawler.robots_ai.AIRobotsChecker.check") as mock_robots,
            patch("worker.crawler.performance.PerformanceChecker.measure_ttfb") as mock_ttfb,
            patch("worker.crawler.llms_txt.LlmsTxtChecker.check") as mock_llms,
        ):

            mock_robots.return_value = RobotsTxtAIResult(
                domain="example.com",
                robots_txt_exists=False,
                robots_txt_url="https://example.com/robots.txt",
                score=100.0,
                all_allowed=True,
            )

            mock_ttfb.return_value = TTFBResult(
                url="https://example.com",
                ttfb_ms=200,
                score=100.0,
                level="excellent",
            )

            mock_llms.return_value = LlmsTxtResult(
                domain="example.com",
                exists=False,
                url="https://example.com/llms.txt",
                quality_score=0.0,
            )

            result = await run_technical_checks(
                url="https://example.com",
                html="<html><body><main>Test content</main></body></html>",
            )

            assert result.total_score > 0
            assert isinstance(result.to_dict(), dict)
