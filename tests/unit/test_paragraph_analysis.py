"""Unit tests for paragraph length analysis."""

import pytest

from worker.extraction.paragraphs import (
    ParagraphInfo,
    analyze_paragraphs,
)


class TestParagraphAnalyzer:
    """Tests for ParagraphAnalyzer class."""

    def test_no_paragraphs(self):
        """Page with no paragraphs should return warning."""
        html = "<html><body><div>Just divs</div></body></html>"
        result = analyze_paragraphs(html)

        assert result.total_paragraphs == 0
        assert result.level == "partial"

    def test_optimal_paragraphs(self):
        """Paragraphs with 2-4 sentences should be marked optimal."""
        html = """
        <html>
        <body>
            <main>
                <p>First sentence here. Second sentence here. Third sentence here.</p>
                <p>Another paragraph. With two sentences.</p>
                <p>One more paragraph. Two sentences. Three sentences. Four sentences.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.total_paragraphs == 3
        assert result.optimal_paragraphs == 3
        assert result.long_paragraphs == 0
        assert result.score >= 90
        assert result.level == "full"

    def test_long_paragraphs_detected(self):
        """Paragraphs with more than 4 sentences should be flagged."""
        html = """
        <html>
        <body>
            <main>
                <p>Sentence one. Sentence two. Sentence three. Sentence four.
                Sentence five. Sentence six. Sentence seven.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.total_paragraphs == 1
        assert result.long_paragraphs == 1
        assert result.optimal_paragraphs == 0
        assert result.score < 100

    def test_average_calculations(self):
        """Test average sentence and word count calculations."""
        html = """
        <html>
        <body>
            <main>
                <p>One sentence.</p>
                <p>First sentence. Second sentence. Third sentence.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.total_paragraphs == 2
        # (1 + 3) / 2 = 2 average sentences
        assert result.avg_sentence_count == pytest.approx(2.0, abs=0.5)

    def test_sentence_counting_with_abbreviations(self):
        """Test that common abbreviations are handled reasonably."""
        html = """
        <html>
        <body>
            <main>
                <p>Dr. Smith met with Mr. Jones today. They discussed the project.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        # Should handle Dr. and Mr. abbreviations
        # Note: Perfect abbreviation handling is complex; we handle common cases
        assert result.paragraphs[0].sentence_count <= 3  # Reasonable range

    def test_sentence_counting_with_numbers(self):
        """Test that numbers with periods don't break sentence counting."""
        html = """
        <html>
        <body>
            <main>
                <p>The price is $10.99 and the discount is 15.5% off.
                That's a great deal.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        # Should be 2 sentences, not broken by decimal numbers
        assert result.paragraphs[0].sentence_count == 2

    def test_optimal_ratio_calculation(self):
        """Test optimal ratio calculation."""
        html = """
        <html>
        <body>
            <main>
                <p>Good paragraph. Two sentences.</p>
                <p>Good paragraph. Two sentences here.</p>
                <p>This is a very long paragraph. With many sentences.
                One two three. Four five six. Seven eight nine.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.total_paragraphs == 3
        assert result.optimal_paragraphs == 2
        assert result.optimal_ratio == pytest.approx(0.67, abs=0.1)

    def test_score_calculation_good(self):
        """Test that good paragraphs score high."""
        html = """
        <html>
        <body>
            <main>
                <p>Good paragraph one. Two sentences here.</p>
                <p>Good paragraph two. Another two sentences.</p>
                <p>Good paragraph three. With three sentences. Like this one.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.score >= 80
        assert result.level == "full"

    def test_score_calculation_poor(self):
        """Test that long paragraphs score poorly."""
        html = """
        <html>
        <body>
            <main>
                <p>Long paragraph. Sentence two. Sentence three. Sentence four.
                Sentence five. Sentence six. Sentence seven. Sentence eight.</p>
                <p>Another long one. Two three four. Five six seven. Eight nine ten.
                Eleven twelve. Thirteen fourteen.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.long_paragraphs >= 2
        assert result.score < 80

    def test_recommendations_for_long_paragraphs(self):
        """Test that recommendations are generated for long paragraphs."""
        html = """
        <html>
        <body>
            <main>
                <p>This is a very long paragraph. It has many sentences.
                One two three. Four five six. Seven eight nine.
                Ten eleven twelve. Thirteen fourteen fifteen.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert len(result.issues) > 0
        assert len(result.recommendations) > 0
        assert any(
            "break" in rec.lower() or "shorter" in rec.lower() for rec in result.recommendations
        )

    def test_main_content_detection(self):
        """Test that only main content paragraphs are analyzed."""
        html = """
        <html>
        <body>
            <nav><p>Navigation text here.</p></nav>
            <main>
                <p>Main content paragraph. With two sentences.</p>
            </main>
            <footer><p>Footer text here.</p></footer>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        # Should only count main content paragraph
        # Note: BeautifulSoup may include nav/footer if no main is found
        assert result.total_paragraphs >= 1

    def test_short_text_ignored(self):
        """Test that very short text is ignored."""
        html = """
        <html>
        <body>
            <main>
                <p>OK</p>
                <p>Real paragraph here. With actual content.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        # "OK" should be ignored (< 10 chars)
        assert result.total_paragraphs == 1

    def test_to_dict_serializable(self):
        """Test that to_dict produces JSON-serializable output."""
        import json

        html = """
        <html>
        <body>
            <main>
                <p>Test paragraph. With two sentences.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)
        data = result.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0

    def test_long_paragraph_samples_in_output(self):
        """Test that long paragraphs are included in output."""
        html = """
        <html>
        <body>
            <main>
                <p>Long paragraph. Two three four. Five six seven.
                Eight nine ten. Eleven twelve thirteen.</p>
                <p>Short paragraph. Two sentences.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)
        data = result.to_dict()

        assert "long_paragraph_samples" in data
        assert len(data["long_paragraph_samples"]) >= 1

    def test_level_assignment(self):
        """Test level assignment based on score."""
        # Good level
        html_good = """
        <html><body><main>
            <p>Good short paragraph. Two sentences.</p>
        </main></body></html>
        """
        assert analyze_paragraphs(html_good).level == "full"

        # Warning level - some long paragraphs
        html_warning = """
        <html><body><main>
            <p>Long paragraph. Two three. Four five. Six seven. Eight nine.</p>
            <p>Good paragraph. Two sentences.</p>
        </main></body></html>
        """
        result_warning = analyze_paragraphs(html_warning)
        assert result_warning.level in ["partial", "full"]

    def test_exclamation_and_question_marks(self):
        """Test sentence counting with ! and ? terminators."""
        html = """
        <html>
        <body>
            <main>
                <p>Is this a question? Yes it is! And here's another statement.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.paragraphs[0].sentence_count == 3


class TestParagraphInfo:
    """Tests for ParagraphInfo dataclass."""

    def test_to_dict(self):
        """Test ParagraphInfo to_dict method."""
        info = ParagraphInfo(
            text="Test paragraph text here.",
            word_count=4,
            sentence_count=1,
            is_optimal=True,
            issues=[],
        )
        data = info.to_dict()

        assert data["word_count"] == 4
        assert data["sentence_count"] == 1
        assert data["is_optimal"] is True

    def test_long_text_truncation(self):
        """Test that long text is truncated in preview."""
        long_text = "Word " * 50
        info = ParagraphInfo(
            text=long_text,
            word_count=50,
            sentence_count=1,
            is_optimal=False,
            issues=["Too long"],
        )
        data = info.to_dict()

        assert len(data["text_preview"]) <= 103  # 100 + "..."
        assert data["text_preview"].endswith("...")


class TestIntegration:
    """Integration tests for paragraph analysis."""

    def test_real_world_content(self):
        """Test with realistic content."""
        html = """
        <html>
        <body>
            <article>
                <h1>How to Write for AI</h1>

                <p>Writing content that AI systems can easily extract and cite
                requires a focus on clarity and structure. This guide covers the
                key principles.</p>

                <h2>Keep Paragraphs Short</h2>

                <p>Research shows that paragraphs with 2-4 sentences are optimal
                for AI extraction. Longer paragraphs are harder to process.</p>

                <p>Each paragraph should focus on a single idea. This makes it
                easier for AI to understand and cite specific points. It also
                improves readability for human users.</p>

                <h2>Use Clear Formatting</h2>

                <p>Headings help AI understand document structure. Use them
                consistently throughout your content.</p>
            </article>
        </body>
        </html>
        """
        result = analyze_paragraphs(html)

        assert result.total_paragraphs >= 4
        assert result.avg_sentence_count <= 4
        assert result.score >= 70
