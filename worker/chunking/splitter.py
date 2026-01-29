"""Text splitting utilities for semantic chunking."""

import re
from dataclasses import dataclass
from enum import Enum


class SplitLevel(str, Enum):
    """Hierarchy of split points, from coarsest to finest."""

    SECTION = "section"  # ## Headings, <h2>, etc.
    PARAGRAPH = "paragraph"  # Double newlines
    SENTENCE = "sentence"  # Period/question/exclamation
    WORD = "word"  # Individual words (last resort)


@dataclass
class SplitConfig:
    """Configuration for text splitting."""

    max_chunk_size: int = 512  # Maximum tokens per chunk
    min_chunk_size: int = 100  # Minimum tokens per chunk
    overlap_size: int = 50  # Token overlap between chunks
    preserve_sentences: bool = True  # Don't split mid-sentence if possible
    preserve_paragraphs: bool = True  # Try to keep paragraphs together


# Patterns for detecting structure
HEADING_PATTERN = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)
PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
LIST_ITEM = re.compile(r"^[\s]*[-*•]\s+", re.MULTILINE)
NUMBERED_LIST = re.compile(r"^[\s]*\d+[.)]\s+", re.MULTILINE)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token on average.
    This is a rough approximation that works for English text.
    """
    if not text:
        return 0
    # More accurate: count words and punctuation separately
    words = len(text.split())
    # Roughly 1.3 tokens per word for English
    return int(words * 1.3)


def _split_by_pattern(text: str, pattern: re.Pattern) -> list[str]:
    """Split text by regex pattern, keeping separators."""
    parts = pattern.split(text)
    return [p for p in parts if p.strip()]


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Handle common abbreviations that shouldn't trigger splits
    text = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|Jr|Sr)\.", r"\1<DOT>", text)
    text = re.sub(r"\b([A-Z])\.", r"\1<DOT>", text)  # Initials

    sentences = SENTENCE_END.split(text)

    # Restore dots
    sentences = [s.replace("<DOT>", ".") for s in sentences]

    return [s.strip() for s in sentences if s.strip()]


def _is_list_content(text: str) -> bool:
    """Check if text appears to be list content."""
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return False

    list_lines = 0
    for line in lines:
        if LIST_ITEM.match(line) or NUMBERED_LIST.match(line):
            list_lines += 1

    return list_lines / len(lines) > 0.5


def _is_table_content(text: str) -> bool:
    """Check if text appears to be table content."""
    lines = text.strip().split("\n")
    if len(lines) < 2:
        return False

    # Check for markdown table pattern
    pipe_lines = sum(1 for line in lines if "|" in line)
    if pipe_lines / len(lines) > 0.5:
        return True

    # Check for consistent column structure (tabs or multiple spaces)
    tab_lines = sum(1 for line in lines if "\t" in line or "  " in line)
    return tab_lines / len(lines) > 0.7


class TextSplitter:
    """Splits text into chunks while preserving structure."""

    def __init__(self, config: SplitConfig | None = None):
        self.config = config or SplitConfig()

    def split(self, text: str) -> list[str]:
        """
        Split text into chunks respecting size limits.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        total_tokens = estimate_tokens(text)

        # If text fits in one chunk, return as-is
        if total_tokens <= self.config.max_chunk_size:
            return [text]

        # Try hierarchical splitting
        chunks = self._split_hierarchically(text)

        # Merge small chunks
        chunks = self._merge_small_chunks(chunks)

        # Add overlap between chunks
        if self.config.overlap_size > 0:
            chunks = self._add_overlap(chunks)

        return chunks

    def _split_hierarchically(self, text: str) -> list[str]:
        """Split text using hierarchical approach."""
        # First, split by sections (headings)
        sections = self._split_by_sections(text)

        chunks: list[str] = []
        for section in sections:
            section_tokens = estimate_tokens(section)

            if section_tokens <= self.config.max_chunk_size:
                chunks.append(section)
            else:
                # Split section into paragraphs
                paragraph_chunks = self._split_by_paragraphs(section)
                chunks.extend(paragraph_chunks)

        return chunks

    def _split_by_sections(self, text: str) -> list[str]:
        """Split text by section headings."""
        # Find all heading positions
        headings = list(HEADING_PATTERN.finditer(text))

        if not headings:
            return [text]

        sections: list[str] = []

        # Content before first heading
        if headings[0].start() > 0:
            pre_content = text[: headings[0].start()].strip()
            if pre_content:
                sections.append(pre_content)

        # Each heading and its content
        for i, match in enumerate(headings):
            start = match.start()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            section = text[start:end].strip()
            if section:
                sections.append(section)

        return sections

    def _split_by_paragraphs(self, text: str) -> list[str]:
        """Split text by paragraphs, handling oversized paragraphs."""
        paragraphs = PARAGRAPH_SPLIT.split(text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks: list[str] = []
        for para in paragraphs:
            para_tokens = estimate_tokens(para)

            if para_tokens <= self.config.max_chunk_size:
                chunks.append(para)
            elif _is_list_content(para) or _is_table_content(para):
                # Keep lists/tables together if possible, or split by lines
                line_chunks = self._split_structured_content(para)
                chunks.extend(line_chunks)
            else:
                # Split by sentences
                sentence_chunks = self._split_by_sentences(para)
                chunks.extend(sentence_chunks)

        return chunks

    def _split_structured_content(self, text: str) -> list[str]:
        """Split list or table content by lines."""
        lines = text.split("\n")
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for line in lines:
            line_tokens = estimate_tokens(line)

            if current_tokens + line_tokens <= self.config.max_chunk_size:
                current_chunk.append(line)
                current_tokens += line_tokens
            else:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_tokens = line_tokens

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split text by sentences, grouping to meet size limits."""
        sentences = _split_into_sentences(text)

        if not sentences:
            return [text] if text.strip() else []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = estimate_tokens(sentence)

            # If single sentence exceeds max, we have to include it anyway
            if sentence_tokens > self.config.max_chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                # Split by words as last resort
                word_chunks = self._split_by_words(sentence)
                chunks.extend(word_chunks)
            elif current_tokens + sentence_tokens <= self.config.max_chunk_size:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_by_words(self, text: str) -> list[str]:
        """Last resort: split by words."""
        words = text.split()
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_tokens = 0

        for word in words:
            word_tokens = estimate_tokens(word)

            if current_tokens + word_tokens <= self.config.max_chunk_size:
                current_chunk.append(word)
                current_tokens += word_tokens
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_tokens = word_tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _merge_small_chunks(self, chunks: list[str]) -> list[str]:
        """Merge chunks that are too small."""
        if not chunks:
            return []

        merged: list[str] = []
        current = chunks[0]

        for chunk in chunks[1:]:
            combined_tokens = estimate_tokens(current + " " + chunk)

            if (
                estimate_tokens(current) < self.config.min_chunk_size
                and combined_tokens <= self.config.max_chunk_size
            ):
                current = current + "\n\n" + chunk
            else:
                merged.append(current)
                current = chunk

        merged.append(current)
        return merged

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        """Add overlapping content between chunks for context continuity."""
        if len(chunks) <= 1:
            return chunks

        overlapped: list[str] = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            curr_chunk = chunks[i]

            # Get overlap from end of previous chunk
            prev_words = prev_chunk.split()
            overlap_words = prev_words[-self.config.overlap_size :]

            if overlap_words:
                overlap_text = " ".join(overlap_words)
                # Only add overlap if it doesn't exceed max size
                combined = overlap_text + " " + curr_chunk
                if estimate_tokens(combined) <= self.config.max_chunk_size * 1.2:
                    overlapped.append(combined)
                else:
                    overlapped.append(curr_chunk)
            else:
                overlapped.append(curr_chunk)

        return overlapped
