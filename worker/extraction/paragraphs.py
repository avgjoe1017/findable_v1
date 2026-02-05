"""Paragraph analysis for content extractability.

Research shows that paragraphs ≤4 sentences are more scannable
and extractable by AI systems. This module analyzes paragraph
structure for optimal AI consumption.
"""

import re
from dataclasses import dataclass, field

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


# Optimal paragraph metrics from research
OPTIMAL_MAX_SENTENCES = 4
OPTIMAL_MAX_WORDS = 100
OPTIMAL_MIN_WORDS = 20


@dataclass
class ParagraphInfo:
    """Information about a single paragraph."""

    text: str
    word_count: int
    sentence_count: int
    is_optimal: bool
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text_preview": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "is_optimal": self.is_optimal,
            "issues": self.issues,
        }


@dataclass
class ParagraphAnalysis:
    """Complete paragraph analysis result."""

    # Counts
    total_paragraphs: int = 0
    optimal_paragraphs: int = 0
    long_paragraphs: int = 0  # > 4 sentences
    short_paragraphs: int = 0  # < 2 sentences but > 0

    # Averages
    avg_sentence_count: float = 0.0
    avg_word_count: float = 0.0

    # Quality metrics
    optimal_ratio: float = 0.0  # % of paragraphs that are optimal length

    # Score
    score: float = 100.0
    level: str = "unknown"

    # Issues
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Sample data
    paragraphs: list[ParagraphInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_paragraphs": self.total_paragraphs,
            "optimal_paragraphs": self.optimal_paragraphs,
            "long_paragraphs": self.long_paragraphs,
            "short_paragraphs": self.short_paragraphs,
            "averages": {
                "sentences_per_paragraph": round(self.avg_sentence_count, 1),
                "words_per_paragraph": round(self.avg_word_count, 1),
            },
            "optimal_ratio": round(self.optimal_ratio, 2),
            "score": round(self.score, 1),
            "level": self.level,
            "issues": self.issues[:3],
            "recommendations": self.recommendations[:3],
            # Sample of long paragraphs
            "long_paragraph_samples": [
                p.to_dict() for p in self.paragraphs if p.sentence_count > OPTIMAL_MAX_SENTENCES
            ][:3],
        }


class ParagraphAnalyzer:
    """Analyzes paragraph structure for AI extractability."""

    def __init__(
        self,
        max_sentences: int = OPTIMAL_MAX_SENTENCES,
        max_words: int = OPTIMAL_MAX_WORDS,
        min_words: int = OPTIMAL_MIN_WORDS,
    ):
        self.max_sentences = max_sentences
        self.max_words = max_words
        self.min_words = min_words

    def analyze(self, html: str, _main_content: str = "") -> ParagraphAnalysis:
        """
        Analyze paragraph structure.

        Args:
            html: HTML content
            main_content: Pre-extracted main content (optional)

        Returns:
            ParagraphAnalysis with paragraph metrics
        """
        soup = BeautifulSoup(html, "html.parser")
        result = ParagraphAnalysis()

        # Find paragraphs in main content area
        main = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.body

        if not main:
            result.level = "partial"
            result.issues.append("No content area found")
            return result

        paragraphs = main.find_all("p")

        if not paragraphs:
            result.level = "partial"
            result.issues.append("No paragraphs found in content")
            return result

        total_sentences = 0
        total_words = 0

        for p in paragraphs:
            text = p.get_text(strip=True)
            if not text or len(text) < 10:
                continue

            para_info = self._analyze_paragraph(text)
            result.paragraphs.append(para_info)
            result.total_paragraphs += 1

            total_sentences += para_info.sentence_count
            total_words += para_info.word_count

            if para_info.is_optimal:
                result.optimal_paragraphs += 1
            elif para_info.sentence_count > self.max_sentences:
                result.long_paragraphs += 1
            elif para_info.sentence_count < 2 and para_info.word_count >= self.min_words:
                result.short_paragraphs += 1

        # Calculate averages
        if result.total_paragraphs > 0:
            result.avg_sentence_count = total_sentences / result.total_paragraphs
            result.avg_word_count = total_words / result.total_paragraphs
            result.optimal_ratio = result.optimal_paragraphs / result.total_paragraphs

        # Calculate score
        result.score = self._calculate_score(result)

        # Determine level
        if result.score >= 80:
            result.level = "full"
        elif result.score >= 50:
            result.level = "partial"
        else:
            result.level = "limited"

        # Generate recommendations
        self._generate_recommendations(result)

        logger.debug(
            "paragraph_analysis_complete",
            total=result.total_paragraphs,
            optimal=result.optimal_paragraphs,
            long=result.long_paragraphs,
            avg_sentences=result.avg_sentence_count,
            score=result.score,
        )

        return result

    def _analyze_paragraph(self, text: str) -> ParagraphInfo:
        """Analyze a single paragraph."""
        word_count = len(text.split())
        sentence_count = self._count_sentences(text)

        issues = []
        is_optimal = True

        if sentence_count > self.max_sentences:
            is_optimal = False
            issues.append(f"Too long ({sentence_count} sentences, max {self.max_sentences})")

        if word_count > self.max_words:
            is_optimal = False
            issues.append(f"Too many words ({word_count}, max {self.max_words})")

        return ParagraphInfo(
            text=text,
            word_count=word_count,
            sentence_count=sentence_count,
            is_optimal=is_optimal,
            issues=issues,
        )

    def _count_sentences(self, text: str) -> int:
        """Count sentences in text."""
        # Split on sentence-ending punctuation
        # Handle common abbreviations
        text = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Inc|Ltd|Jr|Sr)\.", r"\1<PERIOD>", text)
        text = re.sub(r"(\d)\.", r"\1<PERIOD>", text)  # Numbers with periods

        # Count sentence terminators
        sentences = re.split(r"[.!?]+", text)
        # Filter empty strings
        sentences = [s.strip() for s in sentences if s.strip()]

        return max(1, len(sentences))

    def _calculate_score(self, result: ParagraphAnalysis) -> float:
        """Calculate paragraph quality score."""
        if result.total_paragraphs == 0:
            return 50.0  # Neutral if no paragraphs

        score = 100.0

        # Penalize for long paragraphs (more than 4 sentences)
        long_ratio = result.long_paragraphs / result.total_paragraphs
        score -= long_ratio * 40

        # Penalize for high average sentence count
        if result.avg_sentence_count > 5:
            score -= min(20, (result.avg_sentence_count - 5) * 5)
        elif result.avg_sentence_count > 4:
            score -= min(10, (result.avg_sentence_count - 4) * 5)

        # Bonus for high optimal ratio
        score += result.optimal_ratio * 10

        return max(0, min(100, score))

    def _generate_recommendations(self, result: ParagraphAnalysis) -> None:
        """Generate issues and recommendations."""
        if result.long_paragraphs > 0:
            pct = result.long_paragraphs / result.total_paragraphs * 100
            result.issues.append(
                f"{result.long_paragraphs} paragraph(s) ({pct:.0f}%) have more than "
                f"{self.max_sentences} sentences. Long paragraphs are harder for AI to extract."
            )
            result.recommendations.append(
                f"Break long paragraphs into shorter ones (max {self.max_sentences} sentences). "
                "Each paragraph should cover one main point."
            )

        if result.avg_sentence_count > 4:
            result.issues.append(
                f"Average paragraph length is {result.avg_sentence_count:.1f} sentences. "
                "Optimal is 2-4 sentences for AI extraction."
            )

        if result.avg_word_count > 100:
            result.recommendations.append(
                f"Average paragraph has {result.avg_word_count:.0f} words. "
                "Consider keeping paragraphs under 100 words for better scannability."
            )


def analyze_paragraphs(html: str, main_content: str = "") -> ParagraphAnalysis:
    """
    Convenience function to analyze paragraphs.

    Args:
        html: HTML content
        main_content: Pre-extracted main content (optional)

    Returns:
        ParagraphAnalysis with paragraph metrics
    """
    analyzer = ParagraphAnalyzer()
    return analyzer.analyze(html, main_content)
