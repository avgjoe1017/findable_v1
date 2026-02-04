"""Content extraction package."""

# Lazy imports - use explicit imports when needed:
# from worker.extraction.extractor import ContentExtractor, ExtractedPage
# from worker.extraction.cleaner import clean_html, CleanedHTML
# from worker.extraction.metadata import extract_metadata, PageMetadata
# from worker.extraction.js_detection import detect_js_dependency
# from worker.extraction.headings import analyze_headings
# from worker.extraction.links import analyze_links
# from worker.extraction.structure import analyze_structure
# from worker.extraction.schema import analyze_schema

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
    # JS Detection (v2)
    "JSDetector",
    "JSDetectionResult",
    "detect_js_dependency",
    "needs_rendering",
    # Headings (v2)
    "HeadingAnalyzer",
    "HeadingAnalysis",
    "HeadingIssue",
    "analyze_headings",
    # Links (v2)
    "LinkAnalyzer",
    "LinkAnalysis",
    "analyze_links",
    # Structure (v2)
    "StructureAnalyzer",
    "StructureAnalysis",
    "analyze_structure",
    # Schema (v2)
    "SchemaAnalyzer",
    "SchemaAnalysis",
    "analyze_schema",
    # Authority (v2)
    "AuthorityAnalyzer",
    "AuthorityAnalysis",
    "analyze_authority",
]
