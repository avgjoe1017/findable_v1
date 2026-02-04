"""Unit tests for Phase 4 Authority Signals checks."""

from datetime import datetime, timedelta

from worker.extraction.authority import (
    analyze_authority,
)
from worker.scoring.authority import (
    AuthoritySignalsScore,
    calculate_authority_score,
)
from worker.tasks.authority_check import (
    aggregate_authority_scores,
    generate_authority_fixes,
    run_authority_checks_sync,
)

# ==============================================================================
# Authority Extraction Tests
# ==============================================================================


class TestAuthorityAnalyzer:
    """Tests for AuthorityAnalyzer class."""

    def test_no_authority_signals(self):
        """Test analysis of page with no authority signals."""
        html = """
        <html>
        <head><title>No Authority</title></head>
        <body><p>Plain content with no authority signals.</p></body>
        </html>
        """
        result = analyze_authority(html, "https://example.com")

        assert result.has_author is False
        assert result.has_credentials is False
        assert result.authoritative_citations == 0
        assert result.has_original_data is False

    def test_author_byline_detection(self):
        """Test detection of author byline."""
        html = """
        <html>
        <head><title>Article</title></head>
        <body>
            <article>
                <h1>Test Article</h1>
                <p class="author">By John Smith</p>
                <p>Article content here.</p>
            </article>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_author is True
        assert result.primary_author is not None
        assert "John Smith" in result.primary_author.name

    def test_author_with_link(self):
        """Test author with link to bio page."""
        html = """
        <html>
        <body>
            <div class="author">
                <a href="/authors/jane-doe">Jane Doe</a>
            </div>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_author is True
        assert result.primary_author.is_linked is True

    def test_author_with_photo(self):
        """Test author with photo."""
        html = """
        <html>
        <body>
            <div class="author">
                <img src="/photos/author.jpg" alt="Author">
                <span>John Smith</span>
            </div>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_author is True
        assert result.has_author_photo is True

    def test_author_credentials_detection(self):
        """Test detection of author credentials."""
        html = """
        <html>
        <body>
            <div class="author">
                <span class="name">Dr. Jane Smith</span>
                <span class="bio">Senior Research Scientist with 15 years of experience. Ph.D. in Computer Science.</span>
            </div>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_author is True
        assert result.has_credentials is True
        assert len(result.credentials_found) > 0

    def test_authoritative_citations(self):
        """Test detection of authoritative citations."""
        html = """
        <html>
        <body>
            <p>According to <a href="https://www.nature.com/study">research</a>,
            and <a href="https://pubmed.ncbi.nlm.nih.gov/12345">this study</a>,
            the findings are significant.</p>
            <p>See also <a href="https://www.gov.uk/guidance">government guidance</a>.</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.total_citations >= 3
        assert result.authoritative_citations >= 2

    def test_non_authoritative_citations(self):
        """Test that non-authoritative links are counted but not as authoritative."""
        html = """
        <html>
        <body>
            <p>Check out <a href="https://randomsite.com">this site</a>
            and <a href="https://anothersite.net">another one</a>.</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.total_citations >= 2
        assert result.authoritative_citations == 0

    def test_original_data_markers(self):
        """Test detection of original data markers."""
        html = """
        <html>
        <body>
            <p>Our research shows that 75% of users prefer this method.</p>
            <p>We found that performance improved by 40%.</p>
            <p>According to our data, the trend is increasing.</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_original_data is True
        assert result.original_data_count >= 2

    def test_visible_date_detection(self):
        """Test detection of visible publication date."""
        recent_date = datetime.now() - timedelta(days=10)
        date_str = recent_date.strftime("%Y-%m-%d")
        display_date = recent_date.strftime("%B %d, %Y")
        html = f"""
        <html>
        <body>
            <time datetime="{date_str}">
                {display_date}
            </time>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_visible_date is True
        assert result.freshness_level == "fresh"

    def test_stale_content_detection(self):
        """Test detection of stale content."""
        old_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        html = f"""
        <html>
        <body>
            <span class="date">Published on {old_date}</span>
            <p>Content</p>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_visible_date is True
        assert result.freshness_level in ["stale", "very_stale"]

    def test_full_authority_page(self):
        """Test page with comprehensive authority signals."""
        recent_date = datetime.now() - timedelta(days=5)
        date_str = recent_date.strftime("%Y-%m-%d")
        display_date = recent_date.strftime("%B %d, %Y")
        html = f"""
        <html>
        <body>
            <article>
                <h1>Expert Analysis</h1>
                <div class="author">
                    <img src="/photo.jpg" alt="Dr. Jane Smith">
                    <a href="/bio/jane"><span class="name">Dr. Jane Smith</span></a>
                    <span class="bio">Senior Researcher with 20 years experience. Ph.D. in Biology.</span>
                </div>
                <time datetime="{date_str}">{display_date}</time>
                <p>Our research shows significant findings.</p>
                <p>According to <a href="https://nature.com/study">Nature</a>
                and <a href="https://pubmed.ncbi.nlm.nih.gov/123">PubMed</a>,
                our data confirms the hypothesis.</p>
            </article>
        </body>
        </html>
        """
        result = analyze_authority(html, "https://example.com/article")

        assert result.has_author is True
        assert result.has_credentials is True
        assert result.has_author_photo is True
        assert result.authoritative_citations >= 2
        assert result.has_original_data is True
        assert result.has_visible_date is True


# ==============================================================================
# Authority Scoring Tests
# ==============================================================================


class TestAuthorityScoreCalculator:
    """Tests for AuthorityScoreCalculator class."""

    def test_excellent_authority_score(self):
        """Test scoring of page with comprehensive authority signals."""
        recent_date = datetime.now() - timedelta(days=5)
        date_str = recent_date.strftime("%Y-%m-%d")
        display_date = recent_date.strftime("%B %d, %Y")
        html = f"""
        <html>
        <body>
            <div class="author">
                <img src="/photo.jpg" alt="Author">
                <a href="/bio/jane"><span>Dr. Jane Smith</span></a>
                <span class="bio">Expert researcher with Ph.D. in Chemistry</span>
            </div>
            <time datetime="{date_str}">{display_date}</time>
            <p>Our research shows findings.</p>
            <p>See <a href="https://nature.com/study">Nature</a>,
            <a href="https://pubmed.ncbi.nlm.nih.gov/123">PubMed</a>,
            <a href="https://science.org/article">Science</a>.</p>
        </body>
        </html>
        """
        analysis = analyze_authority(html, "https://example.com")
        score = calculate_authority_score(analysis)

        assert score.total_score >= 60  # Slightly lower threshold
        assert score.level in ["good", "warning"]

    def test_no_authority_score(self):
        """Test scoring of page with no authority signals."""
        html = "<html><body><p>No authority signals</p></body></html>"
        analysis = analyze_authority(html, "https://example.com")
        score = calculate_authority_score(analysis)

        assert score.total_score < 40
        assert score.level in ["warning", "critical"]

    def test_partial_authority_score(self):
        """Test scoring with some authority signals."""
        html = """
        <html>
        <body>
            <div class="author">John Smith</div>
            <p>Content with no citations or dates.</p>
        </body>
        </html>
        """
        analysis = analyze_authority(html, "https://example.com")
        score = calculate_authority_score(analysis)

        assert score.total_score > 0
        assert score.total_score < 100

    def test_score_components_present(self):
        """Test that score breakdown includes all components."""
        html = """
        <html>
        <body>
            <div class="author">John Smith</div>
            <p>Content</p>
        </body>
        </html>
        """
        analysis = analyze_authority(html, "https://example.com")
        score = calculate_authority_score(analysis)

        assert score.components is not None
        assert len(score.components) >= 5

        component_names = [c.name for c in score.components]
        assert any("Author" in name for name in component_names)
        assert any("Credential" in name for name in component_names)
        assert any("Citation" in name for name in component_names)
        assert any("Freshness" in name for name in component_names)
        assert any("Data" in name or "Original" in name for name in component_names)

    def test_citations_boost_score(self):
        """Test that authoritative citations boost score."""
        html_with_citations = """
        <html>
        <body>
            <p>See <a href="https://nature.com/study">Nature</a>,
            <a href="https://pubmed.ncbi.nlm.nih.gov/123">PubMed</a>,
            <a href="https://gov.uk/data">Gov</a>.</p>
        </body>
        </html>
        """
        html_without_citations = "<html><body><p>No citations</p></body></html>"

        analysis_with = analyze_authority(html_with_citations, "https://example.com")
        analysis_without = analyze_authority(html_without_citations, "https://example.com")

        score_with = calculate_authority_score(analysis_with)
        score_without = calculate_authority_score(analysis_without)

        assert score_with.total_score > score_without.total_score


# ==============================================================================
# Authority Task Runner Tests
# ==============================================================================


class TestAuthorityTaskRunner:
    """Tests for authority check task runner."""

    def test_run_authority_checks_sync(self):
        """Test synchronous authority checks."""
        html = """
        <html>
        <body>
            <div class="author">By John Smith</div>
            <p>Content</p>
        </body>
        </html>
        """
        result = run_authority_checks_sync(html, "https://example.com")

        assert isinstance(result, AuthoritySignalsScore)
        assert result.total_score >= 0

    def test_aggregate_authority_scores_empty(self):
        """Test aggregation with no scores."""
        result = aggregate_authority_scores([])

        assert result.total_score == 0
        assert result.level == "critical"

    def test_aggregate_authority_scores_single(self):
        """Test aggregation with single score."""
        html = """
        <html>
        <body>
            <div class="author">By John Smith</div>
            <p>Content</p>
        </body>
        </html>
        """
        score = run_authority_checks_sync(html, "https://example.com")
        result = aggregate_authority_scores([score])

        assert result.total_score == score.total_score

    def test_aggregate_authority_scores_multiple(self):
        """Test aggregation with multiple scores."""
        html1 = """
        <html>
        <body>
            <div class="author">By Jane Doe, Ph.D.</div>
            <p>Our research shows results.</p>
        </body>
        </html>
        """
        html2 = "<html><body><p>No authority</p></body></html>"

        score1 = run_authority_checks_sync(html1, "https://example.com")
        score2 = run_authority_checks_sync(html2, "https://example.com/page2")

        result = aggregate_authority_scores([score1, score2])

        # Weighted average: homepage (2x) + other pages (1x)
        expected = (score1.total_score * 2 + score2.total_score) / 3
        assert abs(result.total_score - expected) < 0.1


# ==============================================================================
# Fix Generation Tests
# ==============================================================================


class TestAuthorityFixGeneration:
    """Tests for authority fix generation."""

    def test_generate_author_fix(self):
        """Test fix generation for missing author."""
        html = "<html><body><p>No author</p></body></html>"
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "authority_add_author" in fix_ids

    def test_generate_credentials_fix(self):
        """Test fix generation for missing credentials."""
        html = """
        <html>
        <body>
            <div class="author">John Smith</div>
            <p>Content</p>
        </body>
        </html>
        """
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "authority_add_credentials" in fix_ids

    def test_generate_citations_fix(self):
        """Test fix generation for missing citations."""
        html = """
        <html>
        <body>
            <div class="author">John Smith</div>
            <p>Content with no citations.</p>
        </body>
        </html>
        """
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "authority_add_citations" in fix_ids

    def test_generate_date_fix(self):
        """Test fix generation for missing visible date."""
        html = "<html><body><p>No date</p></body></html>"
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "authority_add_dates" in fix_ids

    def test_generate_original_data_fix(self):
        """Test fix generation for missing original data."""
        html = "<html><body><p>Generic content without any proprietary insights.</p></body></html>"
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "authority_add_original_data" in fix_ids

    def test_no_author_fix_when_present(self):
        """Test that author fix isn't generated when author exists."""
        html = """
        <html>
        <body>
            <div class="author">
                <a href="/bio"><span>Dr. Jane Smith</span></a>
                <span class="bio">Expert researcher with Ph.D. credentials</span>
            </div>
            <p>Content</p>
        </body>
        </html>
        """
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        fix_ids = [f["id"] for f in fixes]
        assert "authority_add_author" not in fix_ids

    def test_fixes_have_required_fields(self):
        """Test that generated fixes have all required fields."""
        html = "<html><body><p>No authority</p></body></html>"
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        for fix in fixes:
            assert "id" in fix
            assert "category" in fix
            assert "priority" in fix
            assert "title" in fix
            assert "description" in fix
            assert "estimated_impact" in fix
            assert "effort" in fix

    def test_fixes_sorted_by_priority(self):
        """Test that fixes are sorted by priority."""
        html = "<html><body><p>No authority</p></body></html>"
        score = run_authority_checks_sync(html, "https://example.com")
        fixes = generate_authority_fixes(score)

        if len(fixes) > 1:
            priorities = [f["priority"] for f in fixes]
            assert priorities == sorted(priorities)
