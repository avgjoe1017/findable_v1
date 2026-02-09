"""Image accessibility and AI-readability analysis.

Analyzes image alt text quality for AI systems that are increasingly
multimodal. Good alt text helps AI understand and cite visual content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


# Patterns that indicate poor/generic alt text
POOR_ALT_PATTERNS = [
    r"^image\d*$",
    r"^img\d*$",
    r"^photo\d*$",
    r"^picture\d*$",
    r"^screenshot\d*$",
    r"^untitled\d*$",
    r"^dsc_?\d+$",  # Camera default names
    r"^img_?\d+$",
    r"^screen\s*shot",
    r"^\d+$",  # Just numbers
    r"^\.+$",  # Just dots
    r"^image\s*\d*\s*of\s*\d*$",  # "image 1 of 5"
]

# File extension patterns (alt text shouldn't be just a filename)
FILENAME_PATTERN = r"^[\w\-\.]+\.(jpg|jpeg|png|gif|webp|svg|bmp)$"

# Decorative image indicators (these are OK to have empty alt)
DECORATIVE_PATTERNS = [
    r"icon",
    r"logo",
    r"spacer",
    r"divider",
    r"bullet",
    r"arrow",
    r"decoration",
    r"background",
]


@dataclass
class ImageInfo:
    """Information about a single image."""

    src: str
    alt: str
    has_alt: bool  # Has alt attribute (even if empty)
    alt_quality: str  # good, poor, missing, decorative
    is_decorative: bool
    is_in_content: bool  # In main content vs nav/footer
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "src": self.src[:200] if self.src else "",
            "alt": self.alt[:200] if self.alt else "",
            "has_alt": self.has_alt,
            "alt_quality": self.alt_quality,
            "is_decorative": self.is_decorative,
            "is_in_content": self.is_in_content,
            "issues": self.issues,
        }


@dataclass
class ImageAnalysis:
    """Complete image accessibility analysis."""

    # Counts
    total_images: int = 0
    images_in_content: int = 0

    # Alt text quality
    images_with_alt: int = 0
    images_missing_alt: int = 0
    images_poor_alt: int = 0
    images_good_alt: int = 0
    images_decorative: int = 0

    # Quality ratio
    alt_quality_ratio: float = 0.0  # % with good alt text

    # Score
    score: float = 100.0  # 0-100
    level: str = "unknown"

    # Issues
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Detailed data
    images: list[ImageInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_images": self.total_images,
            "images_in_content": self.images_in_content,
            "alt_text": {
                "with_alt": self.images_with_alt,
                "missing_alt": self.images_missing_alt,
                "poor_alt": self.images_poor_alt,
                "good_alt": self.images_good_alt,
                "decorative": self.images_decorative,
                "quality_ratio": round(self.alt_quality_ratio, 2),
            },
            "score": round(self.score, 1),
            "level": self.level,
            "issues": self.issues[:5],
            "recommendations": self.recommendations[:3],
            # Include sample of problematic images
            "problem_images": [
                img.to_dict() for img in self.images if img.alt_quality in ["missing", "poor"]
            ][:5],
        }


class ImageAnalyzer:
    """Analyzes image alt text for AI accessibility."""

    def __init__(
        self,
        min_alt_length: int = 5,
        max_alt_length: int = 150,
    ):
        self.min_alt_length = min_alt_length
        self.max_alt_length = max_alt_length

    def analyze(self, html: str, _url: str = "") -> ImageAnalysis:
        """
        Analyze images in HTML for alt text quality.

        Args:
            html: HTML content
            url: Page URL (for context)

        Returns:
            ImageAnalysis with alt text scoring
        """
        soup = BeautifulSoup(html, "html.parser")
        result = ImageAnalysis()

        # Find main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(class_="content")
        )

        # Find all images
        images = soup.find_all("img")
        result.total_images = len(images)

        if not images:
            result.score = 100  # No images = no issues
            result.level = "full"
            return result

        for img in images:
            image_info = self._analyze_image(img, main_content)
            result.images.append(image_info)

            # Update counts
            if image_info.is_in_content:
                result.images_in_content += 1

            if image_info.is_decorative:
                result.images_decorative += 1
            elif image_info.alt_quality == "missing":
                result.images_missing_alt += 1
            elif image_info.alt_quality == "poor":
                result.images_poor_alt += 1
            elif image_info.alt_quality == "good":
                result.images_good_alt += 1

            if image_info.has_alt:
                result.images_with_alt += 1

        # Calculate quality ratio (excluding decorative)
        non_decorative = result.total_images - result.images_decorative
        if non_decorative > 0:
            result.alt_quality_ratio = result.images_good_alt / non_decorative

        # Calculate score
        result.score = self._calculate_score(result)

        # Determine level
        if result.score >= 80:
            result.level = "full"
        elif result.score >= 50:
            result.level = "partial"
        else:
            result.level = "limited"

        # Generate issues and recommendations
        self._generate_recommendations(result)

        logger.debug(
            "image_analysis_complete",
            total_images=result.total_images,
            good_alt=result.images_good_alt,
            missing_alt=result.images_missing_alt,
            score=result.score,
        )

        return result

    def _analyze_image(self, img: Any, main_content: Any) -> ImageInfo:
        """Analyze a single image element."""
        src = img.get("src", "") or img.get("data-src", "") or ""
        alt = img.get("alt")
        has_alt = alt is not None
        alt_text = (alt or "").strip()

        # Check if in main content
        is_in_content = main_content is not None and img in main_content.descendants

        # Check if decorative
        is_decorative = self._is_decorative(img, src, alt_text)

        # Determine quality
        issues = []
        if is_decorative:
            alt_quality = "decorative"
        elif not has_alt:
            alt_quality = "missing"
            issues.append("Missing alt attribute")
        elif self._is_poor_alt(alt_text, src):
            alt_quality = "poor"
            if not alt_text:
                issues.append("Empty alt text on non-decorative image")
            elif len(alt_text) < self.min_alt_length:
                issues.append(f"Alt text too short ({len(alt_text)} chars)")
            elif self._is_filename(alt_text):
                issues.append("Alt text is just a filename")
            elif self._is_generic(alt_text):
                issues.append("Alt text is generic (e.g., 'image', 'photo')")
        else:
            alt_quality = "good"

        return ImageInfo(
            src=src,
            alt=alt_text,
            has_alt=has_alt,
            alt_quality=alt_quality,
            is_decorative=is_decorative,
            is_in_content=is_in_content,
            issues=issues,
        )

    def _is_decorative(self, img: Any, src: str, alt_text: str) -> bool:
        """Check if image is likely decorative."""
        # Explicit decorative markers
        if img.get("role") == "presentation":
            return True
        if img.get("aria-hidden") == "true":
            return True

        # Empty alt is often intentional for decorative
        if alt_text == "":
            # Check if source suggests decorative
            src_lower = src.lower()
            for pattern in DECORATIVE_PATTERNS:
                if pattern in src_lower:
                    return True

        # Check CSS classes
        classes = " ".join(img.get("class", []))
        return any(pattern in classes.lower() for pattern in DECORATIVE_PATTERNS)

    def _is_poor_alt(self, alt_text: str, _src: str) -> bool:
        """Check if alt text is poor quality."""
        if not alt_text:
            return True

        if len(alt_text) < self.min_alt_length:
            return True

        if self._is_filename(alt_text):
            return True

        return bool(self._is_generic(alt_text))

    def _is_filename(self, alt_text: str) -> bool:
        """Check if alt text is just a filename."""
        return bool(re.match(FILENAME_PATTERN, alt_text.lower()))

    def _is_generic(self, alt_text: str) -> bool:
        """Check if alt text is generic."""
        alt_lower = alt_text.lower().strip()
        return any(re.match(pattern, alt_lower) for pattern in POOR_ALT_PATTERNS)

    def _calculate_score(self, result: ImageAnalysis) -> float:
        """Calculate image accessibility score."""
        if result.total_images == 0:
            return 100.0

        non_decorative = result.total_images - result.images_decorative
        if non_decorative == 0:
            return 100.0  # All images are decorative

        score = 100.0

        # Penalize missing alt heavily
        missing_ratio = result.images_missing_alt / non_decorative
        score -= missing_ratio * 50

        # Penalize poor alt
        poor_ratio = result.images_poor_alt / non_decorative
        score -= poor_ratio * 30

        # Extra penalty for content images with issues
        if result.images_in_content > 0:
            content_issues = sum(
                1
                for img in result.images
                if img.is_in_content and img.alt_quality in ["missing", "poor"]
            )
            content_issue_ratio = content_issues / result.images_in_content
            score -= content_issue_ratio * 20

        return max(0, score)

    def _generate_recommendations(self, result: ImageAnalysis) -> None:
        """Generate issues and recommendations."""
        if result.images_missing_alt > 0:
            result.issues.append(
                f"{result.images_missing_alt} image(s) missing alt attributes. "
                "AI systems cannot understand images without alt text."
            )
            result.recommendations.append(
                "Add descriptive alt text to all content images. "
                "Describe what the image shows and why it's relevant."
            )

        if result.images_poor_alt > 0:
            result.issues.append(
                f"{result.images_poor_alt} image(s) have poor alt text "
                "(generic, too short, or just filenames)."
            )
            result.recommendations.append(
                "Replace generic alt text like 'image.jpg' or 'photo' with "
                "specific descriptions of the image content."
            )

        # Check for decorative images that might not be
        suspicious_decorative = sum(
            1 for img in result.images if img.is_decorative and img.is_in_content and img.src
        )
        if suspicious_decorative > 0:
            result.recommendations.append(
                f"{suspicious_decorative} content image(s) marked as decorative. "
                "Verify these don't convey important information."
            )


def analyze_images(html: str, url: str = "") -> ImageAnalysis:
    """
    Convenience function to analyze images.

    Args:
        html: HTML content
        url: Page URL

    Returns:
        ImageAnalysis with alt text scoring
    """
    analyzer = ImageAnalyzer()
    return analyzer.analyze(html, url)
