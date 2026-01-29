"""HTML cleaning and boilerplate removal."""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# Tags that typically contain boilerplate content
BOILERPLATE_TAGS = frozenset(
    [
        "nav",
        "header",
        "footer",
        "aside",
        "sidebar",
        "menu",
        "navigation",
        "breadcrumb",
        "breadcrumbs",
    ]
)

# Tags to completely remove (including content)
REMOVE_TAGS = frozenset(
    [
        "script",
        "style",
        "noscript",
        "iframe",
        "object",
        "embed",
        "svg",
        "canvas",
        "video",
        "audio",
        "source",
        "track",
        "template",
        "slot",
        "dialog",
    ]
)

# Tags that are inline (don't add newlines)
INLINE_TAGS = frozenset(
    [
        "a",
        "abbr",
        "acronym",
        "b",
        "bdo",
        "big",
        "br",
        "button",
        "cite",
        "code",
        "dfn",
        "em",
        "i",
        "img",
        "input",
        "kbd",
        "label",
        "map",
        "object",
        "output",
        "q",
        "samp",
        "select",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "textarea",
        "time",
        "tt",
        "u",
        "var",
        "wbr",
        "mark",
        "del",
        "ins",
        "s",
    ]
)

# Class/ID patterns that indicate boilerplate
BOILERPLATE_PATTERNS = [
    re.compile(r"(nav|menu|sidebar|footer|header|breadcrumb)", re.I),
    re.compile(r"(comment|share|social|widget|banner|ad|promo)", re.I),
    re.compile(r"(cookie|consent|popup|modal|overlay)", re.I),
    re.compile(r"(related|recommended|trending|popular)", re.I),
    re.compile(r"(subscribe|newsletter|signup)", re.I),
]

# Patterns indicating main content
CONTENT_PATTERNS = [
    re.compile(r"(article|content|main|post|entry|body)", re.I),
    re.compile(r"(story|text|copy|description)", re.I),
]


@dataclass
class CleanedHTML:
    """Result of HTML cleaning."""

    main_content: str
    full_text: str
    removed_boilerplate: int
    tag_counts: dict[str, int]


def _is_boilerplate_element(tag: Tag) -> bool:
    """Check if an element is likely boilerplate based on tag/class/id."""
    # Check tag name
    if tag.name in BOILERPLATE_TAGS:
        return True

    # Check class and id attributes
    classes = tag.get("class", [])
    if isinstance(classes, str):
        classes = [classes]
    tag_id = tag.get("id", "")

    attrs_text = " ".join(classes) + " " + str(tag_id)

    return any(pattern.search(attrs_text) for pattern in BOILERPLATE_PATTERNS)


def _is_content_element(tag: Tag) -> bool:
    """Check if an element is likely main content."""
    classes = tag.get("class", [])
    if isinstance(classes, str):
        classes = [classes]
    tag_id = tag.get("id", "")

    attrs_text = " ".join(classes) + " " + str(tag_id)

    for pattern in CONTENT_PATTERNS:
        if pattern.search(attrs_text):
            return True

    # Check for article or main tag
    return tag.name in ("article", "main")


def _get_text_density(tag: Tag) -> float:
    """Calculate text density (text length / total HTML length)."""
    text = tag.get_text(strip=True)
    html = str(tag)

    if not html:
        return 0.0

    return len(text) / len(html)


def _extract_text_from_tag(tag: Tag, preserve_structure: bool = True) -> str:
    """Extract text from a tag with optional structure preservation."""
    if tag.name in REMOVE_TAGS:
        return ""

    parts: list[str] = []

    for child in tag.children:
        if isinstance(child, NavigableString):
            if isinstance(child, Comment):
                continue
            text = str(child).strip()
            if text:
                parts.append(text)
        elif isinstance(child, Tag):
            child_text = _extract_text_from_tag(child, preserve_structure)
            if child_text:
                if preserve_structure and child.name not in INLINE_TAGS:
                    parts.append("\n" + child_text + "\n")
                else:
                    parts.append(child_text)

    return " ".join(parts)


def clean_html(html: str, remove_boilerplate: bool = True) -> CleanedHTML:
    """
    Clean HTML and extract text content.

    Args:
        html: Raw HTML string
        remove_boilerplate: Whether to remove boilerplate elements

    Returns:
        CleanedHTML with extracted text and statistics
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted tags completely
    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Count tags before removal
    tag_counts: dict[str, int] = {}
    for tag in soup.find_all(True):
        tag_counts[tag.name] = tag_counts.get(tag.name, 0) + 1

    # Extract full text (before boilerplate removal)
    full_text = soup.get_text(separator=" ", strip=True)
    # Normalize whitespace
    full_text = re.sub(r"\s+", " ", full_text).strip()

    boilerplate_removed = 0

    if remove_boilerplate:
        # First, try to find main content container
        main_content_tag = None

        # Look for explicit main/article tags
        for tag in soup.find_all(["main", "article"]):
            if _get_text_density(tag) > 0.1:
                main_content_tag = tag
                break

        # Look for content-indicating classes/ids
        if not main_content_tag:
            for tag in soup.find_all(["div", "section"]):
                if _is_content_element(tag) and _get_text_density(tag) > 0.1:
                    main_content_tag = tag
                    break

        if main_content_tag:
            # Use the main content container
            main_content = _extract_text_from_tag(main_content_tag)
        else:
            # Fall back to removing boilerplate from body
            for tag in soup.find_all(True):
                if _is_boilerplate_element(tag):
                    tag.decompose()
                    boilerplate_removed += 1

            main_content = soup.get_text(separator=" ", strip=True)

        # Normalize whitespace
        main_content = re.sub(r"\s+", " ", main_content).strip()
    else:
        main_content = full_text

    return CleanedHTML(
        main_content=main_content,
        full_text=full_text,
        removed_boilerplate=boilerplate_removed,
        tag_counts=tag_counts,
    )


def extract_visible_text(html: str) -> str:
    """
    Extract only visible text from HTML.

    This is a simpler extraction that just gets readable text
    without trying to identify main content.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-visible elements
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()

    # Get text
    text = soup.get_text(separator=" ", strip=True)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text
