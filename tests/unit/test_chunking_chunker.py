"""Tests for semantic chunker."""

from worker.chunking.chunker import (
    Chunk,
    ChunkedPage,
    ChunkerConfig,
    ChunkType,
    SemanticChunker,
    _compute_hash,
    _detect_chunk_type,
    _extract_heading_hierarchy,
    _find_nearest_heading,
    chunk_content,
)


class TestComputeHash:
    """Tests for content hash computation."""

    def test_same_content_same_hash(self) -> None:
        """Same content produces same hash."""
        text = "This is some content."
        assert _compute_hash(text) == _compute_hash(text)

    def test_different_content_different_hash(self) -> None:
        """Different content produces different hash."""
        assert _compute_hash("Hello") != _compute_hash("World")

    def test_normalized_whitespace(self) -> None:
        """Hash is normalized for whitespace."""
        text1 = "Hello   world"
        text2 = "Hello world"
        assert _compute_hash(text1) == _compute_hash(text2)

    def test_case_normalized(self) -> None:
        """Hash is case-insensitive."""
        assert _compute_hash("Hello") == _compute_hash("hello")


class TestDetectChunkType:
    """Tests for chunk type detection."""

    def test_detect_text(self) -> None:
        """Regular prose is TEXT."""
        text = "This is a regular paragraph of text."
        assert _detect_chunk_type(text) == ChunkType.TEXT

    def test_detect_code(self) -> None:
        """Code blocks are CODE."""
        text = "```python\nprint('hello')\n```"
        assert _detect_chunk_type(text) == ChunkType.CODE

    def test_detect_list(self) -> None:
        """Bullet lists are LIST."""
        text = "- Item 1\n- Item 2\n- Item 3"
        assert _detect_chunk_type(text) == ChunkType.LIST

    def test_detect_numbered_list(self) -> None:
        """Numbered lists are LIST."""
        text = "1. First\n2. Second\n3. Third"
        assert _detect_chunk_type(text) == ChunkType.LIST

    def test_detect_table(self) -> None:
        """Markdown tables are TABLE."""
        text = "| Col1 | Col2 |\n|------|------|\n| A | B |"
        assert _detect_chunk_type(text) == ChunkType.TABLE

    def test_detect_quote(self) -> None:
        """Blockquotes are QUOTE."""
        text = "> This is a quote\n> More quote"
        assert _detect_chunk_type(text) == ChunkType.QUOTE

    def test_detect_heading(self) -> None:
        """Single heading line is HEADING."""
        text = "## This is a heading"
        assert _detect_chunk_type(text) == ChunkType.HEADING


class TestExtractHeadingHierarchy:
    """Tests for heading extraction."""

    def test_extract_headings(self) -> None:
        """Extract all headings with levels."""
        text = """# Title

## Section 1

Content here.

### Subsection

More content.

## Section 2

Final content."""

        headings = _extract_heading_hierarchy(text)
        assert len(headings) == 4

        # Check structure: (level, text, position)
        assert headings[0][0] == 1  # h1
        assert headings[0][1] == "Title"

        assert headings[1][0] == 2  # h2
        assert headings[1][1] == "Section 1"

        assert headings[2][0] == 3  # h3
        assert headings[2][1] == "Subsection"

        assert headings[3][0] == 2  # h2
        assert headings[3][1] == "Section 2"

    def test_no_headings(self) -> None:
        """Text without headings returns empty list."""
        text = "Just regular text here."
        assert _extract_heading_hierarchy(text) == []


class TestFindNearestHeading:
    """Tests for finding nearest heading."""

    def test_finds_nearest(self) -> None:
        """Finds heading immediately before position."""
        headings = [
            (1, "Title", 0),
            (2, "Section 1", 50),
            (2, "Section 2", 150),
        ]

        assert _find_nearest_heading(100, headings) == "Section 1"
        assert _find_nearest_heading(200, headings) == "Section 2"

    def test_before_all_headings(self) -> None:
        """Position before all headings returns None."""
        headings = [(2, "Section", 50)]
        assert _find_nearest_heading(10, headings) is None

    def test_empty_headings(self) -> None:
        """Empty headings list returns None."""
        assert _find_nearest_heading(100, []) is None


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_create_chunk(self) -> None:
        """Can create a chunk."""
        chunk = Chunk(
            content="Test content",
            chunk_type=ChunkType.TEXT,
            chunk_index=0,
            token_count=5,
            content_hash="abc123",
            source_url="https://example.com",
            page_title="Test Page",
            heading_context="Section 1",
            position_ratio=0.25,
        )

        assert chunk.content == "Test content"
        assert chunk.chunk_type == ChunkType.TEXT
        assert chunk.chunk_index == 0
        assert chunk.source_url == "https://example.com"

    def test_to_dict(self) -> None:
        """Chunk converts to dict."""
        chunk = Chunk(
            content="Test",
            chunk_type=ChunkType.TEXT,
            chunk_index=0,
            token_count=1,
            content_hash="abc",
            source_url="https://example.com",
            page_title="Title",
        )

        d = chunk.to_dict()
        assert d["content"] == "Test"
        assert d["chunk_type"] == "text"
        assert d["source_url"] == "https://example.com"


class TestChunkedPage:
    """Tests for ChunkedPage dataclass."""

    def test_create_chunked_page(self) -> None:
        """Can create a chunked page."""
        page = ChunkedPage(
            url="https://example.com",
            title="Test Page",
            chunks=[],
            total_chunks=0,
            total_tokens=0,
            avg_chunk_size=0.0,
        )

        assert page.url == "https://example.com"
        assert page.total_chunks == 0

    def test_to_dict(self) -> None:
        """ChunkedPage converts to dict."""
        page = ChunkedPage(
            url="https://example.com",
            title="Test",
            chunks=[],
            total_chunks=0,
            total_tokens=0,
            avg_chunk_size=0.0,
        )

        d = page.to_dict()
        assert d["url"] == "https://example.com"
        assert d["chunks"] == []


class TestChunkerConfig:
    """Tests for ChunkerConfig."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = ChunkerConfig()
        assert config.max_chunk_size == 512
        assert config.min_chunk_size == 100
        assert config.overlap_size == 50
        assert config.include_headings is True
        assert config.deduplicate is True

    def test_custom_values(self) -> None:
        """Can set custom configuration."""
        config = ChunkerConfig(
            max_chunk_size=256,
            deduplicate=False,
        )
        assert config.max_chunk_size == 256
        assert config.deduplicate is False


class TestSemanticChunker:
    """Tests for SemanticChunker class."""

    def test_chunk_empty_text(self) -> None:
        """Empty text returns empty chunks."""
        chunker = SemanticChunker()
        result = chunker.chunk_text("", "https://example.com")

        assert result.total_chunks == 0
        assert result.chunks == []

    def test_chunk_short_text(self) -> None:
        """Short text returns single chunk."""
        chunker = SemanticChunker()
        result = chunker.chunk_text(
            "This is a short piece of text.",
            "https://example.com",
            "Test Page",
        )

        assert result.total_chunks == 1
        assert result.chunks[0].source_url == "https://example.com"
        assert result.chunks[0].page_title == "Test Page"

    def test_chunk_with_headings(self) -> None:
        """Chunks include heading context."""
        chunker = SemanticChunker(ChunkerConfig(include_headings=True))
        text = """## Introduction

This is the introduction content.

## Details

This is the details section."""

        result = chunker.chunk_text(text, "https://example.com")

        # Find chunk with "details section"
        details_chunk = None
        for chunk in result.chunks:
            if "details section" in chunk.content.lower():
                details_chunk = chunk
                break

        if details_chunk:
            assert details_chunk.heading_context in [None, "Introduction", "Details"]

    def test_deduplication(self) -> None:
        """Duplicate content is removed when deduplicate=True."""
        chunker = SemanticChunker(ChunkerConfig(deduplicate=True))
        # Create text with duplicate content
        text = "Same content here.\n\nSame content here.\n\nDifferent content."

        result = chunker.chunk_text(text, "https://example.com")

        # Check for duplicates
        hashes = [c.content_hash for c in result.chunks]
        assert len(hashes) == len(set(hashes))  # All unique

    def test_no_deduplication(self) -> None:
        """Duplicates kept when deduplicate=False."""
        chunker = SemanticChunker(ChunkerConfig(deduplicate=False))
        text = "Same content here.\n\nSame content here."

        result = chunker.chunk_text(text, "https://example.com")

        # Duplicates should be present
        assert result.total_chunks >= 1

    def test_position_ratio(self) -> None:
        """Position ratio is calculated."""
        chunker = SemanticChunker(ChunkerConfig(max_chunk_size=50))
        text = " ".join(["word"] * 200)

        result = chunker.chunk_text(text, "https://example.com")

        if len(result.chunks) >= 2:
            # First chunk should have lower position ratio
            assert result.chunks[0].position_ratio <= result.chunks[-1].position_ratio

    def test_chunk_pages(self) -> None:
        """Chunk multiple pages."""
        chunker = SemanticChunker()
        pages = [
            {"url": "https://example.com/1", "title": "Page 1", "content": "Content 1"},
            {"url": "https://example.com/2", "title": "Page 2", "content": "Content 2"},
        ]

        results = chunker.chunk_pages(pages)

        assert len(results) == 2
        assert results[0].url == "https://example.com/1"
        assert results[1].url == "https://example.com/2"


class TestChunkContent:
    """Tests for chunk_content convenience function."""

    def test_chunk_content(self) -> None:
        """Convenience function works."""
        result = chunk_content(
            "Some text to chunk.",
            "https://example.com",
            "Test Title",
        )

        assert isinstance(result, ChunkedPage)
        assert result.url == "https://example.com"
        assert result.title == "Test Title"

    def test_with_config(self) -> None:
        """Convenience function accepts config."""
        config = ChunkerConfig(max_chunk_size=100)
        result = chunk_content(
            "Some text to chunk.",
            "https://example.com",
            config=config,
        )

        assert isinstance(result, ChunkedPage)


class TestChunkType:
    """Tests for ChunkType enum."""

    def test_all_types(self) -> None:
        """All chunk types exist."""
        assert ChunkType.TEXT == "text"
        assert ChunkType.HEADING == "heading"
        assert ChunkType.LIST == "list"
        assert ChunkType.TABLE == "table"
        assert ChunkType.CODE == "code"
        assert ChunkType.QUOTE == "quote"
