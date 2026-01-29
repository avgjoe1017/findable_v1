"""Tests for HTML cleaning and boilerplate removal."""

from worker.extraction.cleaner import clean_html, extract_visible_text


class TestCleanHTML:
    """Tests for clean_html function."""

    def test_basic_cleaning(self) -> None:
        """Test basic HTML to text extraction."""
        html = "<html><body><p>Hello world</p></body></html>"
        result = clean_html(html)

        assert "Hello world" in result.main_content
        assert "Hello world" in result.full_text

    def test_removes_script_tags(self) -> None:
        """Test script tag removal."""
        html = """
        <html>
        <body>
            <p>Content</p>
            <script>alert('test');</script>
            <p>More content</p>
        </body>
        </html>
        """
        result = clean_html(html)

        assert "alert" not in result.main_content
        assert "Content" in result.main_content
        assert "More content" in result.main_content

    def test_removes_style_tags(self) -> None:
        """Test style tag removal."""
        html = """
        <html>
        <head><style>.test { color: red; }</style></head>
        <body><p>Content</p></body>
        </html>
        """
        result = clean_html(html)

        assert "color: red" not in result.main_content
        assert "Content" in result.main_content

    def test_removes_comments(self) -> None:
        """Test HTML comment removal."""
        html = """
        <html>
        <body>
            <!-- This is a comment -->
            <p>Visible content</p>
        </body>
        </html>
        """
        result = clean_html(html)

        assert "This is a comment" not in result.main_content
        assert "Visible content" in result.main_content

    def test_boilerplate_removal_nav(self) -> None:
        """Test navigation boilerplate removal."""
        html = """
        <html>
        <body>
            <nav><a href="/">Home</a><a href="/about">About</a></nav>
            <main><p>Main content here</p></main>
        </body>
        </html>
        """
        result = clean_html(html, remove_boilerplate=True)

        assert "Main content" in result.main_content

    def test_boilerplate_removal_footer(self) -> None:
        """Test footer boilerplate removal."""
        html = """
        <html>
        <body>
            <article><p>Article content</p></article>
            <footer>Copyright 2024</footer>
        </body>
        </html>
        """
        result = clean_html(html, remove_boilerplate=True)

        assert "Article content" in result.main_content

    def test_preserves_main_content(self) -> None:
        """Test that main content is preserved."""
        html = """
        <html>
        <body>
            <header>Header</header>
            <main>
                <h1>Title</h1>
                <p>This is the main content of the page.</p>
                <p>It should be preserved.</p>
            </main>
            <footer>Footer</footer>
        </body>
        </html>
        """
        result = clean_html(html, remove_boilerplate=True)

        assert "main content" in result.main_content
        assert "preserved" in result.main_content

    def test_handles_empty_html(self) -> None:
        """Test handling of empty HTML."""
        result = clean_html("")

        assert result.main_content == ""
        assert result.full_text == ""

    def test_normalizes_whitespace(self) -> None:
        """Test whitespace normalization."""
        html = """
        <html>
        <body>
            <p>Multiple    spaces    here</p>
            <p>And
            newlines</p>
        </body>
        </html>
        """
        result = clean_html(html)

        # Should normalize to single spaces
        assert "  " not in result.main_content

    def test_tag_counts(self) -> None:
        """Test tag counting."""
        html = """
        <html>
        <body>
            <p>Paragraph 1</p>
            <p>Paragraph 2</p>
            <div>
                <p>Nested paragraph</p>
            </div>
        </body>
        </html>
        """
        result = clean_html(html)

        assert "p" in result.tag_counts
        assert result.tag_counts["p"] == 3

    def test_disable_boilerplate_removal(self) -> None:
        """Test with boilerplate removal disabled."""
        html = """
        <html>
        <body>
            <nav>Navigation</nav>
            <p>Content</p>
        </body>
        </html>
        """
        result = clean_html(html, remove_boilerplate=False)

        # Full text should contain everything
        assert "Navigation" in result.full_text


class TestExtractVisibleText:
    """Tests for extract_visible_text function."""

    def test_basic_extraction(self) -> None:
        """Test basic text extraction."""
        html = "<p>Hello world</p>"
        text = extract_visible_text(html)

        assert text == "Hello world"

    def test_removes_scripts(self) -> None:
        """Test script removal."""
        html = "<p>Text</p><script>code</script>"
        text = extract_visible_text(html)

        assert "code" not in text
        assert "Text" in text

    def test_handles_nested_tags(self) -> None:
        """Test nested tag handling."""
        html = "<div><p><span>Nested</span> text</p></div>"
        text = extract_visible_text(html)

        assert "Nested" in text
        assert "text" in text
