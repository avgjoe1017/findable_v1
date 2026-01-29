"""Tests for metadata extraction."""

from worker.extraction.metadata import PageMetadata, extract_metadata


class TestExtractMetadata:
    """Tests for extract_metadata function."""

    def test_extracts_title(self) -> None:
        """Test title extraction."""
        html = "<html><head><title>Page Title</title></head></html>"
        meta = extract_metadata(html)

        assert meta.title == "Page Title"

    def test_extracts_description(self) -> None:
        """Test meta description extraction."""
        html = """
        <html>
        <head>
            <meta name="description" content="This is a description">
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.description == "This is a description"

    def test_extracts_keywords(self) -> None:
        """Test keywords extraction."""
        html = """
        <html>
        <head>
            <meta name="keywords" content="python, web, scraping">
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert "python" in meta.keywords
        assert "web" in meta.keywords
        assert len(meta.keywords) == 3

    def test_extracts_author(self) -> None:
        """Test author extraction."""
        html = """
        <html>
        <head>
            <meta name="author" content="John Doe">
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.author == "John Doe"

    def test_extracts_canonical(self) -> None:
        """Test canonical URL extraction."""
        html = """
        <html>
        <head>
            <link rel="canonical" href="https://example.com/page">
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.canonical_url == "https://example.com/page"

    def test_extracts_language(self) -> None:
        """Test language extraction."""
        html = '<html lang="en-US"><head></head></html>'
        meta = extract_metadata(html)

        assert meta.language == "en-US"

    def test_extracts_og_tags(self) -> None:
        """Test Open Graph tag extraction."""
        html = """
        <html>
        <head>
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
            <meta property="og:image" content="https://example.com/image.jpg">
            <meta property="og:type" content="article">
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.og_title == "OG Title"
        assert meta.og_description == "OG Description"
        assert meta.og_image == "https://example.com/image.jpg"
        assert meta.og_type == "article"

    def test_extracts_twitter_cards(self) -> None:
        """Test Twitter Card extraction."""
        html = """
        <html>
        <head>
            <meta name="twitter:title" content="Twitter Title">
            <meta name="twitter:description" content="Twitter Desc">
            <meta name="twitter:image" content="https://example.com/twitter.jpg">
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.twitter_title == "Twitter Title"
        assert meta.twitter_description == "Twitter Desc"
        assert meta.twitter_image == "https://example.com/twitter.jpg"

    def test_extracts_headings(self) -> None:
        """Test heading extraction."""
        html = """
        <html>
        <body>
            <h1>Main Title</h1>
            <h2>Section 1</h2>
            <h2>Section 2</h2>
            <h3>Subsection</h3>
        </body>
        </html>
        """
        meta = extract_metadata(html)

        assert "h1" in meta.headings
        assert "Main Title" in meta.headings["h1"]
        assert "h2" in meta.headings
        assert len(meta.headings["h2"]) == 2
        assert "h3" in meta.headings

    def test_counts_links(self) -> None:
        """Test link counting."""
        html = """
        <html>
        <body>
            <a href="/page1">Internal 1</a>
            <a href="/page2">Internal 2</a>
            <a href="https://other.com">External</a>
        </body>
        </html>
        """
        meta = extract_metadata(html, url="https://example.com/")

        assert meta.links_internal == 2
        assert meta.links_external == 1

    def test_counts_images(self) -> None:
        """Test image counting."""
        html = """
        <html>
        <body>
            <img src="image1.jpg">
            <img src="image2.jpg">
            <img src="image3.jpg">
        </body>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.images == 3

    def test_counts_words(self) -> None:
        """Test word counting."""
        html = """
        <html>
        <body>
            <p>This is a test paragraph with some words.</p>
        </body>
        </html>
        """
        meta = extract_metadata(html)

        assert meta.word_count > 0
        assert meta.word_count == 8  # "This is a test paragraph with some words"

    def test_extracts_schema_types_jsonld(self) -> None:
        """Test JSON-LD schema type extraction."""
        html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": "Test Article"
            }
            </script>
        </head>
        </html>
        """
        meta = extract_metadata(html)

        assert "Article" in meta.schema_types

    def test_extracts_schema_types_microdata(self) -> None:
        """Test microdata schema type extraction."""
        html = """
        <html>
        <body>
            <div itemscope itemtype="https://schema.org/Product">
                <span itemprop="name">Product Name</span>
            </div>
        </body>
        </html>
        """
        meta = extract_metadata(html)

        assert "Product" in meta.schema_types

    def test_handles_missing_metadata(self) -> None:
        """Test handling of pages with no metadata."""
        html = "<html><body><p>Just content</p></body></html>"
        meta = extract_metadata(html)

        assert meta.title is None
        assert meta.description is None
        assert meta.keywords == []

    def test_to_dict(self) -> None:
        """Test metadata to_dict conversion."""
        html = """
        <html>
        <head>
            <title>Test</title>
            <meta name="description" content="Description">
        </head>
        </html>
        """
        meta = extract_metadata(html)
        result = meta.to_dict()

        assert result["title"] == "Test"
        assert result["description"] == "Description"
        assert "og" in result
        assert "twitter" in result
        assert "counts" in result


class TestPageMetadata:
    """Tests for PageMetadata dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        meta = PageMetadata()

        assert meta.title is None
        assert meta.description is None
        assert meta.keywords == []
        assert meta.headings == {}
        assert meta.word_count == 0
