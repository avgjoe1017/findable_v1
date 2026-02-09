"""Semantic chunker for extracted page content."""

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum

from worker.chunking.splitter import SplitConfig, TextSplitter, estimate_tokens


class ChunkType(StrEnum):
    """Type of content in a chunk."""

    TEXT = "text"  # Regular prose
    HEADING = "heading"  # Section heading
    LIST = "list"  # Bullet or numbered list
    TABLE = "table"  # Tabular data
    CODE = "code"  # Code block
    QUOTE = "quote"  # Blockquote


@dataclass
class Chunk:
    """A single content chunk."""

    content: str
    chunk_type: ChunkType
    chunk_index: int
    token_count: int
    content_hash: str

    # Source context
    source_url: str
    page_title: str | None

    # Position info
    heading_context: str | None = None  # Nearest heading above this chunk
    position_ratio: float = 0.0  # 0-1, position in document

    # Metadata
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "chunk_type": self.chunk_type.value,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
            "content_hash": self.content_hash,
            "source_url": self.source_url,
            "page_title": self.page_title,
            "heading_context": self.heading_context,
            "position_ratio": self.position_ratio,
            "metadata": self.metadata,
        }


@dataclass
class ChunkedPage:
    """A page that has been chunked."""

    url: str
    title: str | None
    chunks: list[Chunk]
    total_chunks: int
    total_tokens: int
    avg_chunk_size: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "total_chunks": self.total_chunks,
            "total_tokens": self.total_tokens,
            "avg_chunk_size": self.avg_chunk_size,
            "chunks": [c.to_dict() for c in self.chunks],
        }


@dataclass
class ChunkerConfig:
    """Configuration for semantic chunker."""

    max_chunk_size: int = 512  # Max tokens per chunk
    min_chunk_size: int = 100  # Min tokens per chunk
    overlap_size: int = 50  # Overlap between chunks
    include_headings: bool = True  # Include heading context
    deduplicate: bool = True  # Remove duplicate chunks


# Patterns for content type detection
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
BLOCKQUOTE = re.compile(r"^>\s+.+$", re.MULTILINE)
LIST_PATTERN = re.compile(r"^[\s]*[-*•]\s+.+$", re.MULTILINE)
NUMBERED_LIST = re.compile(r"^[\s]*\d+[.)]\s+.+$", re.MULTILINE)
TABLE_PATTERN = re.compile(r"^\|.+\|$", re.MULTILINE)


def _compute_hash(content: str) -> str:
    """Compute hash for content deduplication."""
    normalized = " ".join(content.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _detect_chunk_type(text: str) -> ChunkType:
    """Detect the type of content in a chunk."""
    text = text.strip()

    # Check for code blocks
    if CODE_BLOCK.search(text) or text.startswith("```"):
        return ChunkType.CODE

    # Check for tables
    lines = text.split("\n")
    pipe_lines = sum(1 for line in lines if "|" in line)
    if len(lines) >= 2 and pipe_lines / len(lines) > 0.5:
        return ChunkType.TABLE

    # Check for lists
    list_lines = sum(1 for line in lines if LIST_PATTERN.match(line) or NUMBERED_LIST.match(line))
    if len(lines) >= 2 and list_lines / len(lines) > 0.5:
        return ChunkType.LIST

    # Check for blockquotes
    quote_lines = sum(1 for line in lines if line.strip().startswith(">"))
    if len(lines) >= 1 and quote_lines / len(lines) > 0.5:
        return ChunkType.QUOTE

    # Check for heading
    if len(lines) == 1 and HEADING_PATTERN.match(text):
        return ChunkType.HEADING

    return ChunkType.TEXT


def _extract_heading_hierarchy(text: str) -> list[tuple[int, str, int]]:
    """
    Extract heading hierarchy from text.

    Returns list of (level, heading_text, position).
    """
    headings: list[tuple[int, str, int]] = []

    for match in HEADING_PATTERN.finditer(text):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        position = match.start()
        headings.append((level, heading_text, position))

    return headings


def _find_nearest_heading(position: int, headings: list[tuple[int, str, int]]) -> str | None:
    """Find the nearest heading above a given position."""
    nearest: str | None = None

    for _level, heading_text, heading_pos in headings:
        if heading_pos < position:
            nearest = heading_text
        else:
            break

    return nearest


class SemanticChunker:
    """Chunks page content semantically for embedding."""

    def __init__(self, config: ChunkerConfig | None = None):
        self.config = config or ChunkerConfig()
        self._splitter = TextSplitter(
            SplitConfig(
                max_chunk_size=self.config.max_chunk_size,
                min_chunk_size=self.config.min_chunk_size,
                overlap_size=self.config.overlap_size,
            )
        )

    def chunk_text(
        self,
        text: str,
        url: str,
        title: str | None = None,
    ) -> ChunkedPage:
        """
        Chunk text content into semantic chunks.

        Args:
            text: Text content to chunk
            url: Source URL
            title: Page title

        Returns:
            ChunkedPage with all chunks
        """
        if not text or not text.strip():
            return ChunkedPage(
                url=url,
                title=title,
                chunks=[],
                total_chunks=0,
                total_tokens=0,
                avg_chunk_size=0.0,
            )

        # Extract heading hierarchy for context
        headings = _extract_heading_hierarchy(text)

        # Split text into raw chunks
        raw_chunks = self._splitter.split(text)

        # Process chunks with metadata
        chunks: list[Chunk] = []
        seen_hashes: set[str] = set()
        total_text_len = len(text)
        current_pos = 0

        for i, chunk_text in enumerate(raw_chunks):
            # Compute hash for deduplication
            content_hash = _compute_hash(chunk_text)

            if self.config.deduplicate and content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            # Detect chunk type
            chunk_type = _detect_chunk_type(chunk_text)

            # Find position in original text
            chunk_pos = text.find(chunk_text, current_pos)
            if chunk_pos >= 0:
                current_pos = chunk_pos + len(chunk_text)
                position_ratio = chunk_pos / total_text_len if total_text_len > 0 else 0
            else:
                position_ratio = i / len(raw_chunks) if raw_chunks else 0

            # Find nearest heading for context
            heading_context = None
            if self.config.include_headings and headings:
                heading_context = _find_nearest_heading(
                    chunk_pos if chunk_pos >= 0 else current_pos, headings
                )

            # Create chunk
            chunk = Chunk(
                content=chunk_text,
                chunk_type=chunk_type,
                chunk_index=len(chunks),
                token_count=estimate_tokens(chunk_text),
                content_hash=content_hash,
                source_url=url,
                page_title=title,
                heading_context=heading_context,
                position_ratio=round(position_ratio, 3),
            )
            chunks.append(chunk)

        # Calculate stats
        total_tokens = sum(c.token_count for c in chunks)
        avg_size = total_tokens / len(chunks) if chunks else 0

        return ChunkedPage(
            url=url,
            title=title,
            chunks=chunks,
            total_chunks=len(chunks),
            total_tokens=total_tokens,
            avg_chunk_size=round(avg_size, 1),
        )

    def chunk_pages(
        self,
        pages: list[dict],
    ) -> list[ChunkedPage]:
        """
        Chunk multiple pages.

        Args:
            pages: List of page dicts with 'url', 'title', 'content' keys

        Returns:
            List of ChunkedPage objects
        """
        results: list[ChunkedPage] = []

        for page in pages:
            url = page.get("url", "")
            title = page.get("title")
            content = page.get("content", "")

            chunked = self.chunk_text(content, url, title)
            results.append(chunked)

        return results


def chunk_content(
    text: str,
    url: str,
    title: str | None = None,
    config: ChunkerConfig | None = None,
) -> ChunkedPage:
    """
    Convenience function to chunk content.

    Args:
        text: Text to chunk
        url: Source URL
        title: Page title
        config: Chunker configuration

    Returns:
        ChunkedPage with chunks
    """
    chunker = SemanticChunker(config)
    return chunker.chunk_text(text, url, title)
