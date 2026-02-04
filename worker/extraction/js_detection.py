"""JavaScript dependency detection for AI crawler accessibility.

AI crawlers like GPTBot and ClaudeBot cannot execute JavaScript.
Sites that render content client-side will appear empty to these crawlers.
This module detects whether a page's main content requires JS to render.
"""

import re
from dataclasses import dataclass, field

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


# Common JS framework markers that indicate client-side rendering
JS_FRAMEWORK_MARKERS = {
    # React
    'id="root"': "React",
    'id="__next"': "Next.js",
    "data-reactroot": "React",
    "__NEXT_DATA__": "Next.js",
    # Vue
    'id="app"': "Vue.js",
    "data-v-": "Vue.js",
    "__NUXT__": "Nuxt.js",
    # Angular
    "ng-app": "Angular",
    "ng-version": "Angular",
    "_nghost": "Angular",
    # Svelte
    "svelte-": "SvelteKit",
    # Generic SPA markers
    "window.__INITIAL_STATE__": "SPA",
    "window.__PRELOADED_STATE__": "SPA",
}

# Minimum content length to consider a page as having real content
MIN_CONTENT_LENGTH = 500

# Critical threshold - below this is almost certainly JS-rendered
CRITICAL_CONTENT_LENGTH = 100

# Common empty/loading state indicators
LOADING_INDICATORS = [
    "loading...",
    "please wait",
    "javascript is required",
    "enable javascript",
    "this site requires javascript",
    "noscript",
]


@dataclass
class JSDetectionResult:
    """Result of JavaScript dependency detection."""

    url: str
    likely_js_dependent: bool
    confidence: str  # high, medium, low
    score: float  # 0-100 (100 = fully accessible without JS)

    # Detection details
    framework_detected: str | None = None
    framework_markers_found: list[str] = field(default_factory=list)
    content_length: int = 0
    main_content_length: int = 0
    has_noscript_fallback: bool = False
    has_loading_indicators: bool = False

    # Recommendations
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "likely_js_dependent": self.likely_js_dependent,
            "confidence": self.confidence,
            "score": round(self.score, 2),
            "framework_detected": self.framework_detected,
            "framework_markers_found": self.framework_markers_found,
            "content_length": self.content_length,
            "main_content_length": self.main_content_length,
            "has_noscript_fallback": self.has_noscript_fallback,
            "has_loading_indicators": self.has_loading_indicators,
            "issues": self.issues,
        }

    @property
    def level(self) -> str:
        """Get traffic light level."""
        if self.score >= 80:
            return "good"
        elif self.score >= 50:
            return "warning"
        else:
            return "critical"

    @property
    def is_empty_shell(self) -> bool:
        """
        Check if this page appears to be a JavaScript shell with no content.

        This is the most critical JS dependency signal - the page has HTML
        but essentially zero readable content, meaning AI crawlers see nothing.
        """
        return self.main_content_length < CRITICAL_CONTENT_LENGTH

    @property
    def severity(self) -> str:
        """
        Get severity level for reporting.

        Returns:
            'blocking' - AI crawlers cannot see content at all
            'degraded' - Content is partial or reduced
            'ok' - Content is accessible
        """
        if self.is_empty_shell:
            return "blocking"
        elif self.likely_js_dependent:
            return "degraded"
        else:
            return "ok"


class JSDetector:
    """Detects JavaScript rendering dependencies in HTML."""

    def detect(self, html: str, url: str = "") -> JSDetectionResult:
        """
        Analyze HTML to determine if content requires JavaScript.

        This works by checking:
        1. Presence of JS framework markers
        2. Main content area length
        3. Noscript fallbacks
        4. Loading state indicators

        Args:
            html: The HTML content to analyze
            url: Optional URL for logging

        Returns:
            JSDetectionResult with dependency analysis
        """
        result = JSDetectionResult(
            url=url,
            likely_js_dependent=False,
            confidence="low",
            score=100.0,
        )

        if not html:
            result.likely_js_dependent = True
            result.confidence = "high"
            result.score = 0.0
            result.issues.append("No HTML content received")
            return result

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Get content lengths
            result.content_length = len(html)
            result.main_content_length = self._get_main_content_length(soup)

            # Check for framework markers
            self._detect_frameworks(result, html)

            # Check for noscript fallback
            result.has_noscript_fallback = self._has_noscript_content(soup)

            # Check for loading indicators
            result.has_loading_indicators = self._has_loading_state(soup)

            # Calculate likelihood and score
            self._calculate_js_dependency(result)

            logger.info(
                "js_dependency_detected",
                url=url,
                likely_js_dependent=result.likely_js_dependent,
                confidence=result.confidence,
                framework=result.framework_detected,
                main_content_length=result.main_content_length,
            )

        except Exception as e:
            logger.warning("js_detection_error", url=url, error=str(e))
            result.issues.append(f"Detection error: {e}")

        return result

    def _get_main_content_length(self, soup: BeautifulSoup) -> int:
        """Get the text length of the main content area."""
        # Try common main content containers
        main_selectors = [
            soup.find("main"),
            soup.find("article"),
            soup.find(id="content"),
            soup.find(id="main-content"),
            soup.find(class_="content"),
            soup.find(role="main"),
        ]

        for element in main_selectors:
            if element:
                text = element.get_text(separator=" ", strip=True)
                return len(text)

        # Fallback to body
        body = soup.find("body")
        if body:
            # Remove script/style/nav/footer
            for tag in body.find_all(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = body.get_text(separator=" ", strip=True)
            return len(text)

        return 0

    def _detect_frameworks(self, result: JSDetectionResult, html: str) -> None:
        """Detect JS frameworks from HTML markers."""
        html_lower = html.lower()

        for marker, framework in JS_FRAMEWORK_MARKERS.items():
            if marker.lower() in html_lower:
                result.framework_markers_found.append(marker)
                if not result.framework_detected:
                    result.framework_detected = framework

    def _has_noscript_content(self, soup: BeautifulSoup) -> bool:
        """Check if there's meaningful noscript fallback content."""
        noscript_tags = soup.find_all("noscript")
        for tag in noscript_tags:
            text = tag.get_text(strip=True)
            # Ignore simple "JavaScript required" messages
            if len(text) > 100:
                return True
        return False

    def _has_loading_state(self, soup: BeautifulSoup) -> bool:
        """Check for loading/placeholder indicators."""
        body_text = soup.get_text(separator=" ", strip=True).lower()

        for indicator in LOADING_INDICATORS:
            if indicator in body_text:
                return True

        # Check for spinner/loading classes
        loading_classes = soup.find_all(class_=re.compile(r"loading|spinner|skeleton"))
        return len(loading_classes) > 5  # Multiple loading indicators

    def _calculate_js_dependency(self, result: JSDetectionResult) -> None:
        """Calculate the likelihood of JS dependency and score."""
        # Start with full score
        score = 100.0
        issues = []
        confidence_factors = 0

        # CRITICAL: Near-zero content is a very strong JS indicator
        # This catches pages that are pure JS shells with no server-rendered content
        if result.main_content_length < CRITICAL_CONTENT_LENGTH:
            score -= 60
            confidence_factors += 3  # High confidence signal
            if result.main_content_length == 0:
                issues.append(
                    "No main content detected - page appears to be a JavaScript shell "
                    "(AI crawlers will see an empty page)"
                )
            else:
                issues.append(
                    f"Almost no content visible without JavaScript ({result.main_content_length} chars) - "
                    "AI crawlers cannot access your content"
                )
        elif result.main_content_length < MIN_CONTENT_LENGTH:
            score -= 40
            confidence_factors += 2
            issues.append(
                f"Main content very short ({result.main_content_length} chars, "
                f"minimum {MIN_CONTENT_LENGTH}) - may require JavaScript to render"
            )
        elif result.main_content_length < MIN_CONTENT_LENGTH * 2:
            score -= 20
            confidence_factors += 1

        # Framework detected
        if result.framework_detected:
            score -= 30
            confidence_factors += 1
            issues.append(
                f"{result.framework_detected} framework detected - ensure SSR/prerendering is enabled"
            )

        # Loading indicators
        if result.has_loading_indicators:
            score -= 15
            confidence_factors += 1
            issues.append("Loading state indicators found")

        # Noscript fallback is a good sign
        if result.has_noscript_fallback:
            score += 10
            issues.append("Has noscript fallback content (good)")

        # Multiple framework markers
        if len(result.framework_markers_found) > 2:
            score -= 10
            confidence_factors += 1

        # Set confidence based on number of factors
        if confidence_factors >= 3:
            result.confidence = "high"
        elif confidence_factors >= 2:
            result.confidence = "medium"
        else:
            result.confidence = "low"

        # Determine if likely JS dependent
        result.likely_js_dependent = score < 50
        result.score = max(0, min(100, score))
        result.issues = issues


def detect_js_dependency(html: str, url: str = "") -> JSDetectionResult:
    """
    Convenience function to detect JavaScript dependency.

    Args:
        html: The HTML content to analyze
        url: Optional URL for logging

    Returns:
        JSDetectionResult with dependency analysis
    """
    detector = JSDetector()
    return detector.detect(html, url)


def needs_rendering(html: str, threshold: float = 50.0) -> bool:
    """
    Quick check if a page likely needs headless rendering.

    Args:
        html: The HTML content
        threshold: Score below which rendering is needed

    Returns:
        True if headless rendering is recommended
    """
    result = detect_js_dependency(html)
    return result.score < threshold
