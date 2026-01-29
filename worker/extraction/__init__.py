"""Content extraction package."""

# Lazy imports - use explicit imports when needed:
# from worker.extraction.extractor import ContentExtractor, ExtractedPage
# from worker.extraction.cleaner import clean_html, CleanedHTML
# from worker.extraction.metadata import extract_metadata, PageMetadata

__all__ = [
    # Extractor
    "ContentExtractor",
    "ExtractorConfig",
    "ExtractedPage",
    "ExtractionResult",
    "extract_content",
    # Cleaner
    "clean_html",
    "extract_visible_text",
    "CleanedHTML",
    # Metadata
    "extract_metadata",
    "PageMetadata",
]
