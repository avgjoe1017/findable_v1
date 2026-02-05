"""Content structure analysis for AI extractability.

Analyzes page structure including headings, links, answer positioning,
FAQ sections, and extractable formats (tables, lists).
"""

import re
from dataclasses import dataclass, field

import structlog
from bs4 import BeautifulSoup, Tag

from worker.extraction.headings import HeadingAnalysis, analyze_headings
from worker.extraction.links import LinkAnalysis, analyze_links

logger = structlog.get_logger(__name__)


@dataclass
class AIAnswerBlockAnalysis:
    """Analysis of AI-extractable answer block (GEO/AEO spec: 40-80 word direct answer).

    Per Perplexity GEO/AEO template: Pages should have a concise 40-80 word
    direct answer that AI can extract and present standalone.
    """

    # Detection
    has_answer_block: bool = False
    answer_block_text: str = ""
    answer_block_word_count: int = 0

    # Quality indicators
    is_standalone: bool = False  # Can be understood without context
    is_in_optimal_range: bool = False  # 40-80 words
    starts_with_topic: bool = False  # First sentence names the subject
    contains_definition: bool = False  # Has "is", "are", "refers to"

    # Position
    position_score: float = 0.0  # Higher if answer is early in content

    # Score (0-100)
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "has_answer_block": self.has_answer_block,
            "answer_block_preview": self.answer_block_text[:200] if self.answer_block_text else "",
            "word_count": self.answer_block_word_count,
            "is_standalone": self.is_standalone,
            "is_in_optimal_range": self.is_in_optimal_range,
            "starts_with_topic": self.starts_with_topic,
            "contains_definition": self.contains_definition,
            "position_score": round(self.position_score, 2),
            "score": round(self.score, 2),
        }


@dataclass
class ReadabilityAnalysis:
    """Analysis of content readability for AI consumption.

    Per GEO/AEO spec: 2-3 sentences per paragraph, ~18-20 word average
    sentence length, frequent headings and bullets, no walls of text.
    """

    # Paragraph metrics
    total_paragraphs: int = 0
    avg_paragraph_sentences: float = 0.0
    avg_paragraph_words: float = 0.0
    short_paragraphs_ratio: float = 0.0  # % under 4 sentences

    # Sentence metrics
    avg_sentence_length: float = 0.0
    long_sentences_ratio: float = 0.0  # % over 25 words

    # Wall of text detection
    has_wall_of_text: bool = False  # Paragraph > 150 words
    longest_paragraph_words: int = 0

    # Format density
    headings_per_500_words: float = 0.0
    lists_per_500_words: float = 0.0

    # Score (0-100)
    score: float = 50.0

    def to_dict(self) -> dict:
        return {
            "paragraphs": {
                "total": self.total_paragraphs,
                "avg_sentences": round(self.avg_paragraph_sentences, 1),
                "avg_words": round(self.avg_paragraph_words, 1),
                "short_ratio": round(self.short_paragraphs_ratio, 2),
            },
            "sentences": {
                "avg_length": round(self.avg_sentence_length, 1),
                "long_ratio": round(self.long_sentences_ratio, 2),
            },
            "walls_of_text": {
                "detected": self.has_wall_of_text,
                "longest_paragraph": self.longest_paragraph_words,
            },
            "density": {
                "headings_per_500_words": round(self.headings_per_500_words, 2),
                "lists_per_500_words": round(self.lists_per_500_words, 2),
            },
            "score": round(self.score, 2),
        }


@dataclass
class AnswerFirstAnalysis:
    """Analysis of whether content leads with the answer."""

    # Position metrics
    first_paragraph_length: int = 0
    answer_in_first_paragraph: bool = False
    answer_position: int = 0  # Character position where answer-like content starts
    words_before_answer: int = 0

    # Quality indicators
    has_direct_answer: bool = False  # Starts with definitive statement
    has_definition: bool = False  # Contains "is a", "refers to", etc.
    has_number: bool = False  # Contains specific numbers/data
    has_list_early: bool = False  # Has list in first 500 chars

    # Score
    score: float = 100.0

    def to_dict(self) -> dict:
        return {
            "first_paragraph_length": self.first_paragraph_length,
            "answer_in_first_paragraph": self.answer_in_first_paragraph,
            "answer_position": self.answer_position,
            "words_before_answer": self.words_before_answer,
            "has_direct_answer": self.has_direct_answer,
            "has_definition": self.has_definition,
            "has_number": self.has_number,
            "has_list_early": self.has_list_early,
            "score": round(self.score, 2),
        }


@dataclass
class FAQAnalysis:
    """Analysis of FAQ sections in content."""

    # Detection
    has_faq_section: bool = False
    faq_count: int = 0  # Number of Q&A pairs found

    # Quality
    questions_found: list[str] = field(default_factory=list)
    avg_answer_length: float = 0.0

    # Schema
    has_faq_schema: bool = False

    # Score
    score: float = 0.0  # 0 if no FAQ, higher if good FAQ

    def to_dict(self) -> dict:
        return {
            "has_faq_section": self.has_faq_section,
            "faq_count": self.faq_count,
            "questions_sample": self.questions_found[:5],  # First 5
            "avg_answer_length": round(self.avg_answer_length, 1),
            "has_faq_schema": self.has_faq_schema,
            "score": round(self.score, 2),
        }


@dataclass
class ExtractableFormats:
    """Analysis of extractable content formats."""

    # Tables
    table_count: int = 0
    tables_with_headers: int = 0
    total_table_rows: int = 0

    # Lists
    ordered_list_count: int = 0
    unordered_list_count: int = 0
    definition_list_count: int = 0
    total_list_items: int = 0

    # Code blocks
    code_block_count: int = 0

    # Score
    score: float = 50.0  # Base score, bonus for good formats

    def to_dict(self) -> dict:
        return {
            "tables": {
                "count": self.table_count,
                "with_headers": self.tables_with_headers,
                "total_rows": self.total_table_rows,
            },
            "lists": {
                "ordered": self.ordered_list_count,
                "unordered": self.unordered_list_count,
                "definition": self.definition_list_count,
                "total_items": self.total_list_items,
            },
            "code_blocks": self.code_block_count,
            "score": round(self.score, 2),
        }


@dataclass
class StructureAnalysis:
    """Complete structure analysis result."""

    url: str

    # Component analyses
    headings: HeadingAnalysis = field(default_factory=HeadingAnalysis)
    links: LinkAnalysis = field(default_factory=LinkAnalysis)
    answer_first: AnswerFirstAnalysis = field(default_factory=AnswerFirstAnalysis)
    faq: FAQAnalysis = field(default_factory=FAQAnalysis)
    formats: ExtractableFormats = field(default_factory=ExtractableFormats)
    # GEO/AEO additions
    ai_answer_block: AIAnswerBlockAnalysis = field(default_factory=AIAnswerBlockAnalysis)
    readability: ReadabilityAnalysis = field(default_factory=ReadabilityAnalysis)

    # Overall metrics
    total_score: float = 0.0
    level: str = "unknown"  # good, warning, critical
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "headings": self.headings.to_dict(),
            "links": self.links.to_dict(),
            "answer_first": self.answer_first.to_dict(),
            "faq": self.faq.to_dict(),
            "formats": self.formats.to_dict(),
            "ai_answer_block": self.ai_answer_block.to_dict(),
            "readability": self.readability.to_dict(),
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


# Patterns for answer-first detection
DEFINITION_PATTERNS = [
    r"\bis\s+a\b",
    r"\bare\s+a\b",
    r"\brefers\s+to\b",
    r"\bmeans\b",
    r"\bdefine[ds]?\s+as\b",
    r"\bknown\s+as\b",
]

# FAQ patterns
FAQ_SECTION_PATTERNS = [
    r"frequently\s+asked\s+questions?",
    r"\bfaq\b",
    r"common\s+questions?",
    r"questions?\s+(&|and)\s+answers?",
    r"q\s*&\s*a",
]


class StructureAnalyzer:
    """Analyzes page structure for AI extractability."""

    def __init__(
        self,
        answer_first_chars: int = 500,  # Check first N chars for answer
        min_faq_items: int = 3,  # Minimum Q&A pairs for good FAQ
    ):
        self.answer_first_chars = answer_first_chars
        self.min_faq_items = min_faq_items

    def analyze(
        self,
        html: str,
        url: str,
        main_content: str = "",
        word_count: int = 0,
    ) -> StructureAnalysis:
        """
        Analyze complete page structure.

        Args:
            html: Full HTML content
            url: Page URL
            main_content: Extracted main content text
            word_count: Word count of content

        Returns:
            StructureAnalysis with all component analyses
        """
        result = StructureAnalysis(url=url)
        soup = BeautifulSoup(html, "html.parser")

        # Analyze headings
        result.headings = analyze_headings(html)

        # Analyze links
        result.links = analyze_links(html, url, word_count)

        # Analyze answer-first
        result.answer_first = self._analyze_answer_first(soup, main_content)

        # Analyze FAQ sections
        result.faq = self._analyze_faq(soup, html)

        # Analyze extractable formats
        result.formats = self._analyze_formats(soup)

        # GEO/AEO additions
        result.ai_answer_block = self._analyze_ai_answer_block(soup, main_content)
        result.readability = self._analyze_readability(soup, main_content, word_count)

        # Calculate overall score
        result.total_score = self._calculate_total_score(result)

        # Determine level
        if result.total_score >= 80:
            result.level = "full"
        elif result.total_score >= 50:
            result.level = "partial"
        else:
            result.level = "limited"

        # Compile issues and recommendations
        result.issues, result.recommendations = self._compile_issues(result)

        logger.info(
            "structure_analysis_complete",
            url=url,
            total_score=result.total_score,
            level=result.level,
            heading_score=result.headings.score,
            link_score=result.links.score,
        )

        return result

    def _analyze_answer_first(
        self,
        soup: BeautifulSoup,
        main_content: str,
    ) -> AnswerFirstAnalysis:
        """Analyze whether content leads with the answer."""
        result = AnswerFirstAnalysis()

        # Use main content or extract from soup
        if not main_content:
            main_el = soup.find("main") or soup.find("article") or soup.body
            if main_el:
                main_content = main_el.get_text(separator=" ", strip=True)

        if not main_content:
            result.score = 0
            return result

        # Get first paragraph
        first_p = soup.find("p")
        if first_p:
            result.first_paragraph_length = len(first_p.get_text(strip=True))

        # Analyze first N characters
        first_chars = main_content[: self.answer_first_chars]

        # Check for definition patterns
        for pattern in DEFINITION_PATTERNS:
            if re.search(pattern, first_chars, re.IGNORECASE):
                result.has_definition = True
                break

        # Check for numbers/data
        if re.search(r"\b\d+(?:\.\d+)?%?\b", first_chars):
            result.has_number = True

        # Check for direct answer indicators
        direct_starters = [
            "the answer is",
            "in short",
            "simply put",
            "to summarize",
            "the main",
            "yes,",
            "no,",
        ]
        first_lower = first_chars.lower()
        result.has_direct_answer = any(s in first_lower for s in direct_starters)

        # Check for early list
        early_list = soup.find(["ul", "ol"])
        result.has_list_early = bool(early_list and early_list.find_parent("main"))

        # Count words before substantive content
        words = main_content.split()
        result.words_before_answer = min(50, len(words[:50]))

        # Check if answer is in first paragraph
        if result.first_paragraph_length >= 50:
            result.answer_in_first_paragraph = (
                result.has_definition or result.has_number or result.has_direct_answer
            )

        # Calculate score
        score = 50.0  # Base
        if result.answer_in_first_paragraph:
            score += 30
        if result.has_definition:
            score += 10
        if result.has_number:
            score += 5
        if result.has_list_early:
            score += 5

        result.score = min(100, score)
        return result

    def _analyze_faq(self, soup: BeautifulSoup, html: str) -> FAQAnalysis:
        """Analyze FAQ sections in content."""
        result = FAQAnalysis()

        # Check for FAQ schema
        if "FAQPage" in html or "faqpage" in html.lower():
            result.has_faq_schema = True

        # Find FAQ sections by heading
        faq_headings = []
        for h in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = h.get_text(strip=True).lower()
            for pattern in FAQ_SECTION_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    faq_headings.append(h)
                    break

        # Find question headings (headings ending with ?)
        question_headings = []
        for h in soup.find_all(["h2", "h3", "h4", "h5"]):
            text = h.get_text(strip=True)
            if text.endswith("?"):
                question_headings.append(h)
                result.questions_found.append(text[:200])

        # Find question elements (details/summary, dt/dd patterns)
        details_questions = soup.find_all("details")
        dt_questions = soup.find_all("dt")

        # Count FAQ items
        result.faq_count = len(question_headings) + len(details_questions) + len(dt_questions)

        # Determine if has FAQ section
        result.has_faq_section = len(faq_headings) > 0 or result.faq_count >= self.min_faq_items

        # Calculate average answer length (from question headings)
        answer_lengths = []
        for h in question_headings:
            # Get content until next heading
            next_el = h.find_next_sibling()
            answer_text = ""
            while next_el and next_el.name not in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                if isinstance(next_el, Tag):
                    answer_text += next_el.get_text(strip=True) + " "
                next_el = next_el.find_next_sibling()
            if answer_text:
                answer_lengths.append(len(answer_text))

        if answer_lengths:
            result.avg_answer_length = sum(answer_lengths) / len(answer_lengths)

        # Calculate score
        if result.has_faq_section:
            score = 50.0
            score += min(30, result.faq_count * 5)  # Up to 30 for more Q&As
            if result.has_faq_schema:
                score += 20
            result.score = min(100, score)
        else:
            result.score = 0

        return result

    def _analyze_formats(self, soup: BeautifulSoup) -> ExtractableFormats:
        """Analyze extractable content formats."""
        result = ExtractableFormats()

        # Analyze tables
        tables = soup.find_all("table")
        result.table_count = len(tables)
        for table in tables:
            if table.find("th") or table.find("thead"):
                result.tables_with_headers += 1
            result.total_table_rows += len(table.find_all("tr"))

        # Analyze lists
        result.ordered_list_count = len(soup.find_all("ol"))
        result.unordered_list_count = len(soup.find_all("ul"))
        result.definition_list_count = len(soup.find_all("dl"))
        result.total_list_items = len(soup.find_all(["li", "dd"]))

        # Analyze code blocks
        result.code_block_count = len(soup.find_all(["pre", "code"]))

        # Calculate score
        score = 50.0  # Base

        # Bonus for tables with headers
        if result.tables_with_headers > 0:
            score += min(15, result.tables_with_headers * 5)

        # Bonus for lists
        if result.total_list_items > 0:
            score += min(20, result.total_list_items * 0.5)

        # Bonus for definition lists (very AI-friendly)
        if result.definition_list_count > 0:
            score += min(10, result.definition_list_count * 5)

        # Bonus for code blocks (technical content)
        if result.code_block_count > 0:
            score += min(5, result.code_block_count * 2)

        result.score = min(100, score)
        return result

    def _analyze_ai_answer_block(
        self,
        soup: BeautifulSoup,
        main_content: str,
    ) -> AIAnswerBlockAnalysis:
        """Analyze for AI-extractable answer block (40-80 words).

        Per GEO/AEO spec: Pages should have a concise direct answer
        that AI can extract and present standalone.
        """
        result = AIAnswerBlockAnalysis()

        # Find first substantive paragraph after H1
        h1 = soup.find("h1")
        first_para = None

        if h1:
            # Look for paragraph after H1
            next_el = h1.find_next_sibling()
            while next_el:
                if hasattr(next_el, "name") and next_el.name == "p":
                    text = next_el.get_text(strip=True)
                    if len(text) > 30:  # Skip very short paragraphs
                        first_para = text
                        break
                next_el = next_el.find_next_sibling()

        # Fall back to first paragraph in main/article
        if not first_para:
            main_el = soup.find("main") or soup.find("article") or soup.body
            if main_el:
                for p in main_el.find_all("p", recursive=True)[:3]:
                    text = p.get_text(strip=True)
                    if len(text) > 30:
                        first_para = text
                        break

        if not first_para:
            return result

        # Count words
        words = first_para.split()
        word_count = len(words)

        result.answer_block_text = first_para
        result.answer_block_word_count = word_count

        # Check if in optimal range (40-80 words per GEO/AEO spec)
        result.is_in_optimal_range = 40 <= word_count <= 80

        # Check if standalone (contains subject + definition)
        # Look for patterns like "X is...", "X are...", "X refers to..."
        standalone_patterns = [
            r"^[A-Z][^.]+\s+(?:is|are|refers?\s+to|means?|provides?|enables?)\s",
            r"^[A-Z][^.]+\s+(?:helps?|allows?|lets?|offers?)\s",
        ]
        for pattern in standalone_patterns:
            if re.search(pattern, first_para):
                result.is_standalone = True
                result.contains_definition = True
                break

        # Check if starts with the topic (capitalized noun phrase)
        if first_para and first_para[0].isupper():
            # First word should be a topic word, not "The", "A", "In", etc.
            skip_starters = ["the", "a", "an", "in", "on", "at", "for", "when", "if", "as"]
            first_word = words[0].lower().rstrip(",.")
            if first_word not in skip_starters:
                result.starts_with_topic = True

        # Determine if we have an answer block
        result.has_answer_block = word_count >= 30 and (
            result.is_standalone or result.contains_definition or result.starts_with_topic
        )

        # Position score (higher if answer is very early)
        # Check position in main_content
        if first_para in main_content:
            pos = main_content.find(first_para)
            # Score based on position (0-100, higher is better)
            result.position_score = max(0, 100 - (pos / 10))

        # Calculate overall score
        score = 0.0
        if result.has_answer_block:
            score += 40

        if result.is_in_optimal_range:
            score += 25
        elif 30 <= word_count <= 100:
            score += 15  # Acceptable range

        if result.is_standalone:
            score += 15
        if result.starts_with_topic:
            score += 10
        if result.position_score > 80:
            score += 10

        result.score = min(100, score)
        return result

    def _analyze_readability(
        self,
        soup: BeautifulSoup,
        main_content: str,
        word_count: int,
    ) -> ReadabilityAnalysis:
        """Analyze content readability for AI consumption.

        Per GEO/AEO spec: 2-3 sentences per paragraph, ~18-20 word
        sentence length, no walls of text.
        """
        result = ReadabilityAnalysis()

        if not main_content or word_count == 0:
            return result

        # Get all paragraphs
        main_el = soup.find("main") or soup.find("article") or soup.body
        paragraphs = []
        if main_el:
            for p in main_el.find_all("p", recursive=True):
                text = p.get_text(strip=True)
                if len(text) > 20:  # Skip very short
                    paragraphs.append(text)

        if not paragraphs:
            # Fall back to splitting main content
            paragraphs = [p.strip() for p in main_content.split("\n\n") if len(p.strip()) > 20]

        result.total_paragraphs = len(paragraphs)

        if not paragraphs:
            result.score = 50.0
            return result

        # Analyze paragraphs
        paragraph_word_counts = []
        paragraph_sentence_counts = []
        all_sentences = []

        for para in paragraphs:
            words = para.split()
            paragraph_word_counts.append(len(words))

            # Simple sentence splitting (not perfect but sufficient)
            sentences = re.split(r"[.!?]+\s+", para)
            sentences = [s for s in sentences if len(s) > 5]
            paragraph_sentence_counts.append(len(sentences))
            all_sentences.extend(sentences)

        # Calculate metrics
        result.avg_paragraph_words = sum(paragraph_word_counts) / len(paragraph_word_counts)
        result.avg_paragraph_sentences = (
            sum(paragraph_sentence_counts) / len(paragraph_sentence_counts)
            if paragraph_sentence_counts
            else 0
        )

        # Short paragraphs ratio (target: 2-4 sentences = under 80 words)
        short_paras = sum(1 for wc in paragraph_word_counts if wc <= 80)
        result.short_paragraphs_ratio = short_paras / len(paragraphs)

        # Sentence length analysis
        sentence_lengths = [len(s.split()) for s in all_sentences]
        if sentence_lengths:
            result.avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)
            long_sentences = sum(1 for sl in sentence_lengths if sl > 25)
            result.long_sentences_ratio = long_sentences / len(sentence_lengths)

        # Wall of text detection
        result.longest_paragraph_words = max(paragraph_word_counts) if paragraph_word_counts else 0
        result.has_wall_of_text = result.longest_paragraph_words > 150

        # Heading and list density
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        lists = soup.find_all(["ul", "ol"])
        words_per_500 = word_count / 500 if word_count > 0 else 1

        result.headings_per_500_words = len(headings) / words_per_500
        result.lists_per_500_words = len(lists) / words_per_500

        # Calculate score
        score = 50.0  # Base

        # Good paragraph length (target: 2-3 sentences, 40-80 words)
        if 1.5 <= result.avg_paragraph_sentences <= 4:
            score += 15
        elif result.avg_paragraph_sentences < 1.5:
            score -= 5  # Too choppy

        # Good sentence length (target: 18-20 words)
        if 15 <= result.avg_sentence_length <= 22:
            score += 15
        elif result.avg_sentence_length > 25:
            score -= 10  # Too long

        # Short paragraphs ratio
        if result.short_paragraphs_ratio >= 0.7:
            score += 10
        elif result.short_paragraphs_ratio >= 0.5:
            score += 5

        # Penalize walls of text
        if result.has_wall_of_text:
            score -= 15

        # Penalize too many long sentences
        if result.long_sentences_ratio > 0.3:
            score -= 10

        # Bonus for good heading density (at least 2 per 500 words)
        if result.headings_per_500_words >= 2:
            score += 5

        # Bonus for lists
        if result.lists_per_500_words >= 0.5:
            score += 5

        result.score = max(0, min(100, score))
        return result

    def _calculate_total_score(self, analysis: StructureAnalysis) -> float:
        """Calculate weighted total score."""
        # Weights for each component (must sum to 1.0)
        # Updated with GEO/AEO components
        weights = {
            "headings": 0.20,  # Heading hierarchy
            "answer_first": 0.15,  # Legacy answer-first check
            "ai_answer_block": 0.15,  # NEW: GEO/AEO answer block
            "readability": 0.15,  # NEW: Paragraph/sentence quality
            "faq": 0.15,  # FAQ sections
            "links": 0.10,  # Internal linking
            "formats": 0.10,  # Tables, lists, etc.
        }

        weighted_sum = (
            analysis.headings.score * weights["headings"]
            + analysis.answer_first.score * weights["answer_first"]
            + analysis.ai_answer_block.score * weights["ai_answer_block"]
            + analysis.readability.score * weights["readability"]
            + analysis.faq.score * weights["faq"]
            + analysis.links.score * weights["links"]
            + analysis.formats.score * weights["formats"]
        )

        return weighted_sum

    def _compile_issues(self, analysis: StructureAnalysis) -> tuple[list[str], list[str]]:
        """Compile issues and recommendations."""
        issues = []
        recommendations = []

        # Heading issues
        if not analysis.headings.hierarchy_valid:
            issues.extend([i.details for i in analysis.headings.issues[:3]])
        if analysis.headings.h1_count == 0:
            recommendations.append("Add an H1 heading to the page")
        elif analysis.headings.h1_count > 1:
            recommendations.append("Use only one H1 heading per page")

        # Link issues
        issues.extend(analysis.links.issues[:2])
        if analysis.links.density_level == "low":
            recommendations.append(
                f"Add more internal links. Current: {analysis.links.internal_links}, "
                f"target: 5-15 per page"
            )

        # Answer-first issues
        if not analysis.answer_first.answer_in_first_paragraph:
            recommendations.append("Move the main answer/definition to the first paragraph")

        # FAQ recommendations
        if not analysis.faq.has_faq_section:
            recommendations.append("Add an FAQ section with 3-5 common questions about your topic")
        elif not analysis.faq.has_faq_schema:
            recommendations.append(
                "Add FAQPage schema to your FAQ section for 35-40% citation lift"
            )

        # Format recommendations
        if analysis.formats.table_count > 0 and analysis.formats.tables_with_headers == 0:
            recommendations.append("Add header rows to tables for better AI extraction")

        # AI Answer Block recommendations (GEO/AEO)
        if not analysis.ai_answer_block.has_answer_block:
            recommendations.append(
                "Add a concise 40-80 word answer block after your H1 that AI can extract standalone"
            )
        elif not analysis.ai_answer_block.is_in_optimal_range:
            if analysis.ai_answer_block.answer_block_word_count < 40:
                recommendations.append(
                    f"Expand your opening paragraph to 40-80 words (currently {analysis.ai_answer_block.answer_block_word_count})"
                )
            else:
                recommendations.append(
                    f"Tighten your opening paragraph to 40-80 words (currently {analysis.ai_answer_block.answer_block_word_count})"
                )
        elif not analysis.ai_answer_block.starts_with_topic:
            recommendations.append(
                "Start your first paragraph with the topic name, not 'The' or 'A'"
            )

        # Readability recommendations (GEO/AEO)
        if analysis.readability.has_wall_of_text:
            issues.append(
                f"Wall of text detected: paragraph with {analysis.readability.longest_paragraph_words} words"
            )
            recommendations.append(
                "Break up long paragraphs into 2-3 sentences each (40-80 words max)"
            )

        if analysis.readability.avg_sentence_length > 25:
            recommendations.append(
                f"Shorten sentences to ~18-20 words (currently averaging {analysis.readability.avg_sentence_length:.0f})"
            )

        if analysis.readability.headings_per_500_words < 1.5:
            recommendations.append("Add more section headings (target: 2-3 per 500 words)")

        return issues, recommendations


def analyze_structure(
    html: str,
    url: str,
    main_content: str = "",
    word_count: int = 0,
) -> StructureAnalysis:
    """
    Convenience function to analyze page structure.

    Args:
        html: Full HTML content
        url: Page URL
        main_content: Extracted main content text
        word_count: Word count of content

    Returns:
        StructureAnalysis with all component analyses
    """
    analyzer = StructureAnalyzer()
    return analyzer.analyze(html, url, main_content, word_count)
