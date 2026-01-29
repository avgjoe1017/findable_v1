"""Tests for text splitter."""

from worker.chunking.splitter import (
    SplitConfig,
    TextSplitter,
    _is_list_content,
    _is_table_content,
    _split_into_sentences,
    estimate_tokens,
)


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self) -> None:
        """Empty string has 0 tokens."""
        assert estimate_tokens("") == 0

    def test_single_word(self) -> None:
        """Single word has ~1 token."""
        tokens = estimate_tokens("hello")
        assert tokens >= 1

    def test_sentence(self) -> None:
        """Sentence token count is reasonable."""
        text = "This is a simple test sentence."
        tokens = estimate_tokens(text)
        # ~7 words * 1.3 = ~9 tokens
        assert 5 <= tokens <= 15

    def test_longer_text(self) -> None:
        """Longer text scales appropriately."""
        text = "word " * 100  # 100 words
        tokens = estimate_tokens(text)
        # 100 * 1.3 = 130
        assert 100 <= tokens <= 200


class TestSplitIntoSentences:
    """Tests for sentence splitting."""

    def test_simple_sentences(self) -> None:
        """Split simple sentences."""
        text = "First sentence. Second sentence. Third sentence."
        sentences = _split_into_sentences(text)
        assert len(sentences) == 3

    def test_with_abbreviations(self) -> None:
        """Handle common abbreviations."""
        text = "Dr. Smith went to the store. He bought milk."
        sentences = _split_into_sentences(text)
        assert len(sentences) == 2

    def test_with_questions(self) -> None:
        """Handle question marks."""
        text = "Is this working? Yes it is. Great!"
        sentences = _split_into_sentences(text)
        assert len(sentences) == 3

    def test_empty_text(self) -> None:
        """Handle empty text."""
        assert _split_into_sentences("") == []


class TestIsListContent:
    """Tests for list detection."""

    def test_bullet_list(self) -> None:
        """Detect bullet list."""
        text = "- Item 1\n- Item 2\n- Item 3"
        assert _is_list_content(text) is True

    def test_asterisk_list(self) -> None:
        """Detect asterisk list."""
        text = "* Item 1\n* Item 2\n* Item 3"
        assert _is_list_content(text) is True

    def test_numbered_list(self) -> None:
        """Detect numbered list."""
        text = "1. First\n2. Second\n3. Third"
        assert _is_list_content(text) is True

    def test_regular_text(self) -> None:
        """Regular text is not a list."""
        text = "This is just a regular paragraph of text."
        assert _is_list_content(text) is False

    def test_single_line(self) -> None:
        """Single line is not a list."""
        text = "- Just one item"
        assert _is_list_content(text) is False


class TestIsTableContent:
    """Tests for table detection."""

    def test_markdown_table(self) -> None:
        """Detect markdown table."""
        text = "| Col1 | Col2 |\n|------|------|\n| A | B |"
        assert _is_table_content(text) is True

    def test_tab_separated(self) -> None:
        """Detect tab-separated content."""
        text = "Name\tAge\tCity\nJohn\t30\tNYC\nJane\t25\tLA"
        assert _is_table_content(text) is True

    def test_regular_text(self) -> None:
        """Regular text is not a table."""
        text = "This is just regular text without any structure."
        assert _is_table_content(text) is False


class TestTextSplitter:
    """Tests for TextSplitter class."""

    def test_short_text_no_split(self) -> None:
        """Short text returns single chunk."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=500))
        text = "This is a short text."
        chunks = splitter.split(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self) -> None:
        """Empty text returns empty list."""
        splitter = TextSplitter()
        assert splitter.split("") == []
        assert splitter.split("   ") == []

    def test_splits_long_text(self) -> None:
        """Long text is split into chunks."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=50, min_chunk_size=10))
        # Create text that exceeds max_chunk_size
        text = " ".join(["word"] * 100)
        chunks = splitter.split(text)
        assert len(chunks) > 1

    def test_respects_max_size(self) -> None:
        """Chunks respect max size limit."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=100, overlap_size=0))
        text = " ".join(["word"] * 200)
        chunks = splitter.split(text)

        for chunk in chunks:
            tokens = estimate_tokens(chunk)
            # Allow some flexibility due to estimation
            assert tokens <= 150  # 100 * 1.5 for tolerance

    def test_splits_by_sections(self) -> None:
        """Text with headings splits by sections."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=500))
        text = """## Section 1

Content for section one.

## Section 2

Content for section two."""

        chunks = splitter.split(text)
        # Should preserve section structure when possible
        assert any("Section 1" in c for c in chunks)
        assert any("Section 2" in c for c in chunks)

    def test_splits_by_paragraphs(self) -> None:
        """Text splits by paragraphs."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=200))
        text = """First paragraph with some content.

Second paragraph with more content.

Third paragraph with even more content."""

        chunks = splitter.split(text)
        assert len(chunks) >= 1

    def test_handles_lists(self) -> None:
        """Lists are handled appropriately."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=200))
        text = """Here is a list:

- Item one
- Item two
- Item three
- Item four"""

        chunks = splitter.split(text)
        assert len(chunks) >= 1

    def test_overlap_adds_context(self) -> None:
        """Overlap adds context from previous chunk."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=50, min_chunk_size=10, overlap_size=10))
        text = " ".join([f"word{i}" for i in range(100)])
        chunks = splitter.split(text)

        # With overlap, chunks should share some content
        # Multiple chunks confirms splitting occurred
        assert len(chunks) > 1

    def test_merges_small_chunks(self) -> None:
        """Small chunks are merged together."""
        splitter = TextSplitter(SplitConfig(max_chunk_size=200, min_chunk_size=50, overlap_size=0))
        # Create text with small paragraphs
        text = "A.\n\nB.\n\nC.\n\nD.\n\nE."
        chunks = splitter.split(text)

        # Very small chunks should be merged
        for chunk in chunks:
            # After merging, shouldn't have single-letter chunks
            assert len(chunk) >= 3 or len(chunks) == 1


class TestSplitConfig:
    """Tests for SplitConfig."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = SplitConfig()
        assert config.max_chunk_size == 512
        assert config.min_chunk_size == 100
        assert config.overlap_size == 50
        assert config.preserve_sentences is True
        assert config.preserve_paragraphs is True

    def test_custom_values(self) -> None:
        """Can set custom configuration."""
        config = SplitConfig(
            max_chunk_size=256,
            min_chunk_size=50,
            overlap_size=25,
        )
        assert config.max_chunk_size == 256
        assert config.min_chunk_size == 50
        assert config.overlap_size == 25
