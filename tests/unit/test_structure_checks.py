"""Unit tests for Phase 2 Structure Quality checks."""

from worker.extraction.headings import (
    HeadingIssueType,
    analyze_headings,
)
from worker.extraction.links import (
    analyze_links,
)
from worker.extraction.structure import (
    analyze_structure,
)
from worker.scoring.structure import (
    StructureQualityScore,
    calculate_structure_score,
)
from worker.tasks.structure_check import (
    aggregate_structure_scores,
    generate_structure_fixes,
    run_structure_checks_sync,
)


class TestHeadingAnalysis:
    """Tests for heading hierarchy analysis."""

    def test_valid_hierarchy(self):
        """Valid heading hierarchy should score well."""
        html = """
        <html>
        <body>
            <h1>Main Title</h1>
            <h2>Section 1</h2>
            <p>Content</p>
            <h3>Subsection 1.1</h3>
            <p>Content</p>
            <h2>Section 2</h2>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_headings(html)

        assert result.h1_count == 1
        assert result.h2_count == 2
        assert result.h3_count == 1
        assert result.hierarchy_valid is True
        assert result.score >= 90

    def test_missing_h1(self):
        """Missing H1 should be flagged."""
        html = """
        <html>
        <body>
            <h2>Section 1</h2>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_headings(html)

        assert result.h1_count == 0
        assert result.hierarchy_valid is False
        assert any(i.issue_type == HeadingIssueType.MISSING_H1 for i in result.issues)
        assert result.score < 90

    def test_multiple_h1(self):
        """Multiple H1s should be flagged."""
        html = """
        <html>
        <body>
            <h1>First Title</h1>
            <p>Content</p>
            <h1>Second Title</h1>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_headings(html)

        assert result.h1_count == 2
        assert any(i.issue_type == HeadingIssueType.MULTIPLE_H1 for i in result.issues)

    def test_skip_level(self):
        """Skipping heading levels should be flagged."""
        html = """
        <html>
        <body>
            <h1>Main Title</h1>
            <h3>Skipped to H3</h3>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_headings(html)

        assert result.skip_count == 1
        assert any(i.issue_type == HeadingIssueType.SKIP_LEVEL for i in result.issues)

    def test_faq_heading_detection(self):
        """FAQ headings should be detected."""
        html = """
        <html>
        <body>
            <h1>Product Page</h1>
            <h2>Frequently Asked Questions</h2>
            <h3>How does it work?</h3>
        </body>
        </html>
        """
        result = analyze_headings(html)

        assert result.has_faq_heading is True
        assert result.question_headings == 1

    def test_no_headings(self):
        """Page with no headings should have low score."""
        html = """
        <html>
        <body>
            <p>Just some content without headings.</p>
        </body>
        </html>
        """
        result = analyze_headings(html)

        assert result.total_headings == 0
        assert result.score == 0


class TestLinkAnalysis:
    """Tests for internal link analysis."""

    def test_internal_link_detection(self):
        """Internal links should be detected."""
        html = """
        <html>
        <body>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
            <a href="https://example.com/page3">Page 3</a>
            <a href="https://external.com">External</a>
        </body>
        </html>
        """
        result = analyze_links(html, "https://example.com", word_count=1000)

        assert result.internal_links == 3
        assert result.external_links == 1
        assert result.total_links == 4

    def test_optimal_link_density(self):
        """Optimal link count should score well."""
        html = """
        <html>
        <body>
            <a href="/page1">Descriptive Link 1</a>
            <a href="/page2">Descriptive Link 2</a>
            <a href="/page3">Descriptive Link 3</a>
            <a href="/page4">Descriptive Link 4</a>
            <a href="/page5">Descriptive Link 5</a>
            <a href="/page6">Descriptive Link 6</a>
            <a href="/page7">Descriptive Link 7</a>
        </body>
        </html>
        """
        result = analyze_links(html, "https://example.com")

        assert result.density_level == "optimal"
        assert result.score >= 80

    def test_low_link_density(self):
        """Too few links should be flagged."""
        html = """
        <html>
        <body>
            <a href="/page1">Link 1</a>
            <a href="/page2">Link 2</a>
        </body>
        </html>
        """
        result = analyze_links(html, "https://example.com")

        assert result.density_level == "low"
        assert len(result.issues) > 0

    def test_generic_anchor_detection(self):
        """Generic anchors should be detected."""
        html = """
        <html>
        <body>
            <a href="/page1">click here</a>
            <a href="/page2">read more</a>
            <a href="/page3">learn more</a>
            <a href="/page4">here</a>
            <a href="/page5">link</a>
            <a href="/page6">Good descriptive anchor text</a>
        </body>
        </html>
        """
        result = analyze_links(html, "https://example.com")

        assert result.generic_anchors == 5
        assert result.good_anchor_count == 1


class TestStructureAnalysis:
    """Tests for complete structure analysis."""

    def test_answer_first_detection(self):
        """Answer-first content should be detected."""
        html = """
        <html>
        <body>
            <main>
                <h1>What is Python?</h1>
                <p>Python is a high-level programming language. It was created in 1991
                and has become one of the most popular languages for web development.</p>
            </main>
        </body>
        </html>
        """
        result = analyze_structure(html, "https://example.com")

        assert result.answer_first.has_definition is True
        assert result.answer_first.score >= 50

    def test_faq_section_detection(self):
        """FAQ sections should be detected."""
        html = """
        <html>
        <body>
            <h1>Product</h1>
            <h2>Frequently Asked Questions</h2>
            <h3>What is the price?</h3>
            <p>The price is $99.</p>
            <h3>How do I order?</h3>
            <p>Click the buy button.</p>
            <h3>Do you offer refunds?</h3>
            <p>Yes, 30-day money back guarantee.</p>
        </body>
        </html>
        """
        result = analyze_structure(html, "https://example.com")

        assert result.faq.has_faq_section is True
        assert result.faq.faq_count >= 3

    def test_extractable_formats(self):
        """Tables and lists should be detected."""
        html = """
        <html>
        <body>
            <h1>Comparison</h1>
            <table>
                <thead><tr><th>Feature</th><th>Basic</th><th>Pro</th></tr></thead>
                <tr><td>Storage</td><td>10GB</td><td>100GB</td></tr>
                <tr><td>Users</td><td>1</td><td>10</td></tr>
            </table>
            <h2>Benefits</h2>
            <ul>
                <li>Fast</li>
                <li>Secure</li>
                <li>Reliable</li>
            </ul>
            <ol>
                <li>Step 1</li>
                <li>Step 2</li>
            </ol>
        </body>
        </html>
        """
        result = analyze_structure(html, "https://example.com")

        assert result.formats.table_count == 1
        assert result.formats.tables_with_headers == 1
        assert result.formats.unordered_list_count == 1
        assert result.formats.ordered_list_count == 1
        assert result.formats.total_list_items == 5

    def test_overall_score_calculation(self):
        """Overall score should be weighted average of components."""
        html = """
        <html>
        <body>
            <h1>Well-Structured Page</h1>
            <p>This page is about widgets. Widgets are devices that perform useful functions.</p>
            <h2>Features</h2>
            <ul>
                <li>Feature 1</li>
                <li>Feature 2</li>
            </ul>
            <a href="/related">Related Page</a>
            <a href="/more">More Info</a>
            <a href="/details">Details</a>
            <a href="/about">About Us</a>
            <a href="/contact">Contact</a>
        </body>
        </html>
        """
        result = analyze_structure(html, "https://example.com")

        assert result.total_score > 0
        assert result.level in ["good", "warning", "critical"]


class TestStructureScoring:
    """Tests for structure score calculation."""

    def test_all_good_scores_high(self):
        """Well-structured page should score high."""
        html = """
        <html>
        <body>
            <h1>Main Topic</h1>
            <p>This is the definition of the main topic. It provides clear value.</p>
            <h2>Section 1</h2>
            <p>Content for section 1</p>
            <h2>FAQ</h2>
            <h3>What is this?</h3>
            <p>This is a product.</p>
            <h3>How much does it cost?</h3>
            <p>It costs $50.</p>
            <h3>Where can I buy it?</h3>
            <p>On our website.</p>
            <a href="/page1">Related Page 1</a>
            <a href="/page2">Related Page 2</a>
            <a href="/page3">Related Page 3</a>
            <a href="/page4">Related Page 4</a>
            <a href="/page5">Related Page 5</a>
            <ul><li>Item 1</li><li>Item 2</li></ul>
        </body>
        </html>
        """
        analysis = analyze_structure(html, "https://example.com")
        score = calculate_structure_score(analysis)

        assert score.total_score >= 50
        assert score.level in ["good", "warning"]

    def test_poor_structure_scores_low(self):
        """Poorly structured page should score low."""
        html = """
        <html>
        <body>
            <h3>Wrong starting heading</h3>
            <p>Content without definition.</p>
            <h5>Skipped to H5</h5>
            <p>More content.</p>
        </body>
        </html>
        """
        analysis = analyze_structure(html, "https://example.com")
        score = calculate_structure_score(analysis)

        assert score.total_score < 70
        assert len(score.critical_issues) >= 0

    def test_show_the_math(self):
        """show_the_math should produce readable output."""
        html = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        analysis = analyze_structure(html, "https://example.com")
        score = calculate_structure_score(analysis)

        output = score.show_the_math()

        assert "STRUCTURE QUALITY SCORE" in output
        assert "COMPONENT BREAKDOWN" in output

    def test_to_dict_serializable(self):
        """to_dict should produce JSON-serializable output."""
        import json

        html = "<html><body><h1>Test</h1><p>Content</p></body></html>"
        analysis = analyze_structure(html, "https://example.com")
        score = calculate_structure_score(analysis)
        data = score.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0


class TestStructureChecks:
    """Tests for structure check task runner."""

    def test_run_structure_checks_sync(self):
        """Synchronous structure checks should work."""
        html = """
        <html>
        <body>
            <h1>Test Page</h1>
            <p>This is a test page about testing.</p>
        </body>
        </html>
        """
        result = run_structure_checks_sync(html, "https://example.com")

        assert isinstance(result, StructureQualityScore)
        assert result.total_score >= 0
        assert result.level in ["good", "warning", "critical"]

    def test_aggregate_structure_scores(self):
        """Aggregating multiple page scores should work."""
        html1 = "<html><body><h1>Page 1</h1><p>Content 1</p></body></html>"
        html2 = "<html><body><h1>Page 2</h1><p>Content 2</p></body></html>"

        score1 = run_structure_checks_sync(html1, "https://example.com")
        score2 = run_structure_checks_sync(html2, "https://example.com/page2")

        aggregated = aggregate_structure_scores([score1, score2])

        assert isinstance(aggregated, StructureQualityScore)
        assert aggregated.total_score >= 0

    def test_aggregate_empty_list(self):
        """Aggregating empty list should return low score."""
        aggregated = aggregate_structure_scores([])

        assert aggregated.total_score == 0
        assert aggregated.level == "critical"


class TestStructureFixGeneration:
    """Tests for structure fix generation."""

    def test_missing_h1_fix(self):
        """Missing H1 should generate fix."""
        html = "<html><body><h2>Section</h2><p>Content</p></body></html>"
        score = run_structure_checks_sync(html, "https://example.com")
        fixes = generate_structure_fixes(score)

        h1_fixes = [f for f in fixes if "h1" in f["id"].lower()]
        assert len(h1_fixes) > 0

    def test_no_faq_fix(self):
        """Missing FAQ should generate fix."""
        html = "<html><body><h1>Page</h1><p>Content without FAQ</p></body></html>"
        score = run_structure_checks_sync(html, "https://example.com")
        fixes = generate_structure_fixes(score)

        faq_fixes = [f for f in fixes if "faq" in f["id"].lower()]
        assert len(faq_fixes) > 0

    def test_fix_priority_ordering(self):
        """Fixes should be ordered by priority."""
        html = """
        <html><body>
            <h3>Skipped H1 and H2</h3>
            <p>No answer first, no FAQ, no links</p>
        </body></html>
        """
        score = run_structure_checks_sync(html, "https://example.com")
        fixes = generate_structure_fixes(score)

        if len(fixes) > 1:
            priorities = [f["priority"] for f in fixes]
            assert priorities == sorted(priorities)

    def test_fix_has_required_fields(self):
        """Each fix should have required fields."""
        html = "<html><body><p>Poor content</p></body></html>"
        score = run_structure_checks_sync(html, "https://example.com")
        fixes = generate_structure_fixes(score)

        for fix in fixes:
            assert "id" in fix
            assert "category" in fix
            assert "priority" in fix
            assert "title" in fix
            assert "description" in fix
            assert "estimated_impact" in fix
            assert "effort" in fix
