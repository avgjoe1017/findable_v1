"""Heading hierarchy analysis for content structure.

Validates proper heading structure (H1→H2→H3) which is critical
for AI content extraction and understanding.
"""

from dataclasses import dataclass, field
from enum import StrEnum

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class HeadingIssueType(StrEnum):
    """Types of heading hierarchy issues."""

    MISSING_H1 = "missing_h1"
    MULTIPLE_H1 = "multiple_h1"
    SKIP_LEVEL = "skip_level"  # e.g., H1 → H3 (skips H2)
    WRONG_ORDER = "wrong_order"  # e.g., H3 before H2
    EMPTY_HEADING = "empty_heading"
    TOO_LONG = "too_long"
    DUPLICATE = "duplicate"


@dataclass
class HeadingIssue:
    """A single heading hierarchy issue."""

    issue_type: HeadingIssueType
    level: int  # The heading level with the issue
    text: str  # The heading text (truncated)
    position: int  # Position in document order
    details: str  # Human-readable explanation

    def to_dict(self) -> dict:
        return {
            "issue_type": self.issue_type.value,
            "level": self.level,
            "text": self.text[:100],
            "position": self.position,
            "details": self.details,
        }


@dataclass
class HeadingNode:
    """A heading in the document."""

    level: int  # 1-6
    text: str
    position: int  # Order in document


@dataclass
class HeadingAnalysis:
    """Complete heading hierarchy analysis result."""

    # Basic counts
    h1_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    h4_count: int = 0
    h5_count: int = 0
    h6_count: int = 0
    total_headings: int = 0

    # Hierarchy validation
    hierarchy_valid: bool = True
    issues: list[HeadingIssue] = field(default_factory=list)

    # Quality metrics
    score: float = 100.0  # 0-100
    skip_count: int = 0  # Number of level skips
    duplicate_count: int = 0  # Number of duplicate headings

    # Structure info
    max_depth: int = 0  # Deepest heading level used
    avg_heading_length: float = 0.0
    headings: list[HeadingNode] = field(default_factory=list)

    # Semantic analysis
    has_faq_heading: bool = False  # Contains FAQ/Questions heading
    has_how_to_heading: bool = False  # Contains How-to heading
    question_headings: int = 0  # Headings that are questions

    def to_dict(self) -> dict:
        return {
            "counts": {
                "h1": self.h1_count,
                "h2": self.h2_count,
                "h3": self.h3_count,
                "h4": self.h4_count,
                "h5": self.h5_count,
                "h6": self.h6_count,
                "total": self.total_headings,
            },
            "hierarchy_valid": self.hierarchy_valid,
            "issues": [i.to_dict() for i in self.issues],
            "score": round(self.score, 2),
            "skip_count": self.skip_count,
            "duplicate_count": self.duplicate_count,
            "max_depth": self.max_depth,
            "avg_heading_length": round(self.avg_heading_length, 1),
            "has_faq_heading": self.has_faq_heading,
            "has_how_to_heading": self.has_how_to_heading,
            "question_headings": self.question_headings,
        }


# Patterns for detecting FAQ/How-to headings
FAQ_PATTERNS = [
    "faq",
    "frequently asked",
    "common questions",
    "questions and answers",
    "q&a",
    "q & a",
]

HOW_TO_PATTERNS = [
    "how to",
    "how do",
    "step by step",
    "steps to",
    "guide to",
    "tutorial",
    "instructions",
]


class HeadingAnalyzer:
    """Analyzes heading hierarchy for AI extractability."""

    def __init__(
        self,
        max_heading_length: int = 200,
        penalize_missing_h1: float = 20.0,
        penalize_multiple_h1: float = 10.0,
        penalize_skip: float = 5.0,
        penalize_duplicate: float = 2.0,
    ):
        self.max_heading_length = max_heading_length
        self.penalize_missing_h1 = penalize_missing_h1
        self.penalize_multiple_h1 = penalize_multiple_h1
        self.penalize_skip = penalize_skip
        self.penalize_duplicate = penalize_duplicate

    def analyze(self, html: str) -> HeadingAnalysis:
        """
        Analyze heading hierarchy in HTML.

        Args:
            html: HTML content to analyze

        Returns:
            HeadingAnalysis with hierarchy validation and score
        """
        soup = BeautifulSoup(html, "html.parser")
        result = HeadingAnalysis()

        # Extract all headings in document order
        headings = []

        for position, tag in enumerate(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
            level = int(tag.name[1])
            text = tag.get_text(strip=True)

            headings.append(HeadingNode(level=level, text=text, position=position))

        result.headings = headings
        result.total_headings = len(headings)

        if not headings:
            result.hierarchy_valid = False
            result.score = 0.0
            result.issues.append(
                HeadingIssue(
                    issue_type=HeadingIssueType.MISSING_H1,
                    level=1,
                    text="",
                    position=0,
                    details="Page has no headings at all",
                )
            )
            return result

        # Count by level
        for h in headings:
            if h.level == 1:
                result.h1_count += 1
            elif h.level == 2:
                result.h2_count += 1
            elif h.level == 3:
                result.h3_count += 1
            elif h.level == 4:
                result.h4_count += 1
            elif h.level == 5:
                result.h5_count += 1
            elif h.level == 6:
                result.h6_count += 1

        # Max depth
        result.max_depth = max(h.level for h in headings)

        # Average heading length
        if headings:
            result.avg_heading_length = sum(len(h.text) for h in headings) / len(headings)

        # Validate hierarchy
        issues = []
        penalties = 0.0

        # Check H1 presence
        if result.h1_count == 0:
            issues.append(
                HeadingIssue(
                    issue_type=HeadingIssueType.MISSING_H1,
                    level=1,
                    text="",
                    position=0,
                    details="Page is missing an H1 heading",
                )
            )
            penalties += self.penalize_missing_h1

        # Check multiple H1s
        if result.h1_count > 1:
            h1_positions = [h for h in headings if h.level == 1]
            for i, h in enumerate(h1_positions[1:], start=1):
                issues.append(
                    HeadingIssue(
                        issue_type=HeadingIssueType.MULTIPLE_H1,
                        level=1,
                        text=h.text[:100],
                        position=h.position,
                        details=f"Multiple H1 headings found (this is #{i + 1})",
                    )
                )
            penalties += self.penalize_multiple_h1

        # Check for level skips
        prev_level = 0
        for h in headings:
            if prev_level > 0 and h.level > prev_level + 1:
                # Skip detected (e.g., H1 → H3)
                issues.append(
                    HeadingIssue(
                        issue_type=HeadingIssueType.SKIP_LEVEL,
                        level=h.level,
                        text=h.text[:100],
                        position=h.position,
                        details=f"Skips from H{prev_level} to H{h.level}",
                    )
                )
                result.skip_count += 1
                penalties += self.penalize_skip
            prev_level = h.level

        # Check for duplicates
        seen_headings = set()
        for h in headings:
            normalized = h.text.lower().strip()
            if normalized and normalized in seen_headings:
                issues.append(
                    HeadingIssue(
                        issue_type=HeadingIssueType.DUPLICATE,
                        level=h.level,
                        text=h.text[:100],
                        position=h.position,
                        details="Duplicate heading text",
                    )
                )
                result.duplicate_count += 1
                penalties += self.penalize_duplicate
            seen_headings.add(normalized)

        # Check for empty headings
        for h in headings:
            if not h.text.strip():
                issues.append(
                    HeadingIssue(
                        issue_type=HeadingIssueType.EMPTY_HEADING,
                        level=h.level,
                        text="",
                        position=h.position,
                        details="Empty heading found",
                    )
                )
                penalties += 2.0

        # Check for overly long headings
        for h in headings:
            if len(h.text) > self.max_heading_length:
                issues.append(
                    HeadingIssue(
                        issue_type=HeadingIssueType.TOO_LONG,
                        level=h.level,
                        text=h.text[:100],
                        position=h.position,
                        details=f"Heading too long ({len(h.text)} chars)",
                    )
                )
                penalties += 1.0

        # Semantic analysis
        for h in headings:
            text_lower = h.text.lower()

            # Check for FAQ headings
            if any(pattern in text_lower for pattern in FAQ_PATTERNS):
                result.has_faq_heading = True

            # Check for How-to headings
            if any(pattern in text_lower for pattern in HOW_TO_PATTERNS):
                result.has_how_to_heading = True

            # Check for question headings
            if h.text.strip().endswith("?"):
                result.question_headings += 1

        # Calculate final score
        result.issues = issues
        result.hierarchy_valid = len(issues) == 0
        result.score = max(0.0, 100.0 - penalties)

        logger.debug(
            "heading_analysis_complete",
            total_headings=result.total_headings,
            h1_count=result.h1_count,
            issues=len(issues),
            score=result.score,
        )

        return result


def analyze_headings(html: str) -> HeadingAnalysis:
    """
    Convenience function to analyze heading hierarchy.

    Args:
        html: HTML content to analyze

    Returns:
        HeadingAnalysis with hierarchy validation and score
    """
    analyzer = HeadingAnalyzer()
    return analyzer.analyze(html)
