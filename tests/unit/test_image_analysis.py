"""Unit tests for image alt text analysis."""

import pytest

from worker.extraction.images import (
    ImageInfo,
    analyze_images,
)


class TestImageAnalyzer:
    """Tests for ImageAnalyzer class."""

    def test_no_images(self):
        """Page with no images should score 100."""
        html = "<html><body><p>No images here</p></body></html>"
        result = analyze_images(html)

        assert result.total_images == 0
        assert result.score == 100.0
        assert result.level == "good"

    def test_image_with_good_alt(self):
        """Image with descriptive alt text should be marked good."""
        html = """
        <html>
        <body>
            <main>
                <img src="product.jpg" alt="Red leather handbag with gold clasp">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 1
        assert result.images_good_alt == 1
        assert result.images_missing_alt == 0
        assert result.score >= 90

    def test_image_missing_alt(self):
        """Image without alt attribute should be flagged."""
        html = """
        <html>
        <body>
            <main>
                <img src="product.jpg">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 1
        assert result.images_missing_alt == 1
        assert result.score < 100
        assert len(result.issues) > 0

    def test_image_empty_alt(self):
        """Image with empty alt but not decorative should be flagged."""
        html = """
        <html>
        <body>
            <main>
                <img src="important-chart.jpg" alt="">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 1
        # Empty alt on content image is poor quality
        assert result.images_poor_alt == 1 or result.images_decorative == 1

    def test_image_generic_alt(self):
        """Image with generic alt text should be flagged."""
        html = """
        <html>
        <body>
            <main>
                <img src="photo.jpg" alt="image">
                <img src="picture.jpg" alt="photo">
                <img src="screen.jpg" alt="screenshot">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 3
        assert result.images_poor_alt >= 2
        assert result.score < 80

    def test_image_filename_as_alt(self):
        """Alt text that is just a filename should be flagged."""
        html = """
        <html>
        <body>
            <main>
                <img src="photo.jpg" alt="IMG_1234.jpg">
                <img src="screen.jpg" alt="screenshot.png">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.images_poor_alt >= 2

    def test_decorative_image_with_role(self):
        """Decorative image with role=presentation should be allowed."""
        html = """
        <html>
        <body>
            <main>
                <img src="divider.gif" alt="" role="presentation">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 1
        assert result.images_decorative == 1
        assert result.images_missing_alt == 0
        assert result.images_poor_alt == 0

    def test_decorative_image_aria_hidden(self):
        """Decorative image with aria-hidden should be allowed."""
        html = """
        <html>
        <body>
            <main>
                <img src="icon.svg" alt="" aria-hidden="true">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.images_decorative == 1

    def test_decorative_by_source_pattern(self):
        """Image with decorative source pattern should be recognized."""
        html = """
        <html>
        <body>
            <img src="spacer.gif" alt="">
            <img src="divider-line.png" alt="">
            <img src="bullet-point.svg" alt="">
        </body>
        </html>
        """
        result = analyze_images(html)

        # These should be recognized as decorative
        assert result.images_decorative >= 2

    def test_content_vs_nav_images(self):
        """Test differentiation between content and nav images."""
        html = """
        <html>
        <body>
            <nav>
                <img src="logo.png" alt="Company Logo">
            </nav>
            <main>
                <img src="product.jpg" alt="Product photo showing features">
                <img src="chart.png" alt="Sales growth chart">
            </main>
            <footer>
                <img src="social.png" alt="Social icons">
            </footer>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 4
        assert result.images_in_content == 2

    def test_short_alt_text(self):
        """Alt text that is too short should be flagged."""
        html = """
        <html>
        <body>
            <main>
                <img src="product.jpg" alt="pic">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.images_poor_alt == 1

    def test_quality_ratio_calculation(self):
        """Test alt quality ratio calculation."""
        html = """
        <html>
        <body>
            <main>
                <img src="good1.jpg" alt="A detailed description of image one">
                <img src="good2.jpg" alt="Another detailed description here">
                <img src="bad.jpg" alt="img">
                <img src="decorative.gif" alt="" role="presentation">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 4
        assert result.images_decorative == 1
        # 3 non-decorative, 2 good = 66.7%
        assert result.alt_quality_ratio == pytest.approx(0.67, abs=0.1)

    def test_score_calculation(self):
        """Test score calculation logic."""
        # All good images
        html_good = """
        <html><body><main>
            <img src="a.jpg" alt="Descriptive alt text for image A">
            <img src="b.jpg" alt="Descriptive alt text for image B">
        </main></body></html>
        """
        result_good = analyze_images(html_good)
        assert result_good.score >= 90

        # All missing alt
        html_bad = """
        <html><body><main>
            <img src="a.jpg">
            <img src="b.jpg">
        </main></body></html>
        """
        result_bad = analyze_images(html_bad)
        assert result_bad.score < 50

    def test_recommendations_generated(self):
        """Test that appropriate recommendations are generated."""
        html = """
        <html>
        <body>
            <main>
                <img src="missing.jpg">
                <img src="poor.jpg" alt="image">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert len(result.issues) >= 1
        assert len(result.recommendations) >= 1
        assert any("alt" in rec.lower() for rec in result.recommendations)

    def test_to_dict_serializable(self):
        """Test that to_dict produces JSON-serializable output."""
        import json

        html = """
        <html>
        <body>
            <main>
                <img src="test.jpg" alt="Test image">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)
        data = result.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0

    def test_problem_images_in_output(self):
        """Test that problem images are included in output."""
        html = """
        <html>
        <body>
            <main>
                <img src="missing.jpg">
                <img src="poor.jpg" alt="img">
                <img src="good.jpg" alt="A detailed description">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)
        data = result.to_dict()

        assert "problem_images" in data
        assert len(data["problem_images"]) >= 2

    def test_level_assignment(self):
        """Test level assignment based on score."""
        # Good - high score
        html_good = """
        <html><body><main>
            <img src="a.jpg" alt="Good descriptive alt text">
        </main></body></html>
        """
        assert analyze_images(html_good).level == "good"

        # Warning - medium score
        html_warning = """
        <html><body><main>
            <img src="a.jpg" alt="Good alt text">
            <img src="b.jpg" alt="img">
            <img src="c.jpg">
        </main></body></html>
        """
        result_warning = analyze_images(html_warning)
        assert result_warning.level in ["warning", "critical"]

    def test_data_src_handling(self):
        """Test handling of lazy-loaded images with data-src."""
        html = """
        <html>
        <body>
            <main>
                <img data-src="lazy.jpg" alt="Lazy loaded image description">
            </main>
        </body>
        </html>
        """
        result = analyze_images(html)

        assert result.total_images == 1
        assert result.images[0].src == "lazy.jpg"


class TestImageInfo:
    """Tests for ImageInfo dataclass."""

    def test_to_dict(self):
        """Test ImageInfo to_dict method."""
        info = ImageInfo(
            src="test.jpg",
            alt="Test alt text",
            has_alt=True,
            alt_quality="good",
            is_decorative=False,
            is_in_content=True,
            issues=[],
        )
        data = info.to_dict()

        assert data["src"] == "test.jpg"
        assert data["alt"] == "Test alt text"
        assert data["alt_quality"] == "good"
        assert data["is_in_content"] is True

    def test_long_src_truncation(self):
        """Test that long src is truncated."""
        long_src = "https://example.com/" + "a" * 300 + ".jpg"
        info = ImageInfo(
            src=long_src,
            alt="Alt",
            has_alt=True,
            alt_quality="good",
            is_decorative=False,
            is_in_content=True,
        )
        data = info.to_dict()

        assert len(data["src"]) <= 200
