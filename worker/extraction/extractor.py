"""Main content extractor for crawled pages."""

from dataclasses import dataclass
from datetime import datetime

from worker.crawler.crawler import CrawlPage, CrawlResult
from worker.extraction.cleaner import clean_html
from worker.extraction.metadata import PageMetadata, extract_metadata


@dataclass
class ExtractedPage:
    """A page with extracted content and metadata."""

    url: str
    final_url: str
    title: str | None
    main_content: str
    full_text: str
    metadata: PageMetadata
    word_count: int
    depth: int
    fetched_at: datetime

    # Original HTML stats
    html_size: int
    content_size: int
    compression_ratio: float

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "final_url": self.final_url,
            "title": self.title,
            "main_content": self.main_content,
            "full_text": self.full_text,
            "metadata": self.metadata.to_dict(),
            "word_count": self.word_count,
            "depth": self.depth,
            "fetched_at": self.fetched_at.isoformat(),
            "html_size": self.html_size,
            "content_size": self.content_size,
            "compression_ratio": self.compression_ratio,
        }


@dataclass
class ExtractionResult:
    """Result of extracting content from a crawl."""

    domain: str
    pages: list[ExtractedPage]
    total_pages: int
    total_words: int
    extraction_errors: int
    avg_word_count: float
    schema_types_found: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "domain": self.domain,
            "total_pages": self.total_pages,
            "total_words": self.total_words,
            "extraction_errors": self.extraction_errors,
            "avg_word_count": self.avg_word_count,
            "schema_types_found": self.schema_types_found,
        }


@dataclass
class ExtractorConfig:
    """Configuration for content extraction."""

    remove_boilerplate: bool = True
    min_content_length: int = 50
    max_content_length: int = 100000
    extract_metadata: bool = True


class ContentExtractor:
    """Extracts clean content from crawled HTML pages."""

    def __init__(self, config: ExtractorConfig | None = None):
        self.config = config or ExtractorConfig()

    def extract_page(self, page: CrawlPage) -> ExtractedPage | None:
        """
        Extract content from a single crawled page.

        Args:
            page: CrawlPage from crawler

        Returns:
            ExtractedPage or None if extraction fails
        """
        if not page.html:
            return None

        try:
            # Clean HTML and extract text
            cleaned = clean_html(
                page.html,
                remove_boilerplate=self.config.remove_boilerplate,
            )

            # Check minimum content length
            if len(cleaned.main_content) < self.config.min_content_length:
                return None

            # Truncate if too long
            main_content = cleaned.main_content
            if len(main_content) > self.config.max_content_length:
                main_content = main_content[: self.config.max_content_length]

            full_text = cleaned.full_text
            if len(full_text) > self.config.max_content_length:
                full_text = full_text[: self.config.max_content_length]

            # Extract metadata
            if self.config.extract_metadata:
                metadata = extract_metadata(page.html, page.url)
            else:
                metadata = PageMetadata()

            # Calculate stats
            html_size = len(page.html.encode("utf-8"))
            content_size = len(main_content.encode("utf-8"))
            compression_ratio = content_size / html_size if html_size > 0 else 0

            # Word count from main content
            word_count = len(main_content.split())

            return ExtractedPage(
                url=page.url,
                final_url=page.final_url,
                title=page.title or metadata.title,
                main_content=main_content,
                full_text=full_text,
                metadata=metadata,
                word_count=word_count,
                depth=page.depth,
                fetched_at=page.fetched_at,
                html_size=html_size,
                content_size=content_size,
                compression_ratio=compression_ratio,
            )

        except Exception:
            return None

    def extract_crawl(self, crawl: CrawlResult) -> ExtractionResult:
        """
        Extract content from all pages in a crawl result.

        Args:
            crawl: CrawlResult from crawler

        Returns:
            ExtractionResult with all extracted pages
        """
        pages: list[ExtractedPage] = []
        errors = 0
        total_words = 0
        all_schema_types: set[str] = set()

        for page in crawl.pages:
            extracted = self.extract_page(page)
            if extracted:
                pages.append(extracted)
                total_words += extracted.word_count
                all_schema_types.update(extracted.metadata.schema_types)
            else:
                errors += 1

        avg_words = total_words / len(pages) if pages else 0

        return ExtractionResult(
            domain=crawl.domain,
            pages=pages,
            total_pages=len(pages),
            total_words=total_words,
            extraction_errors=errors,
            avg_word_count=round(avg_words, 1),
            schema_types_found=sorted(all_schema_types),
        )


def extract_content(html: str, url: str | None = None) -> tuple[str, PageMetadata]:
    """
    Convenience function to extract content from HTML.

    Args:
        html: HTML content
        url: Optional page URL

    Returns:
        Tuple of (main_content, metadata)
    """
    cleaned = clean_html(html, remove_boilerplate=True)
    metadata = extract_metadata(html, url)
    return cleaned.main_content, metadata
