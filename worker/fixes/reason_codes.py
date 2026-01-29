"""Reason codes for why questions fail AI sourceability evaluation.

Defines the standard reason codes that explain why a question
cannot be answered or is only partially answerable.
"""

from dataclasses import dataclass
from enum import Enum


class ReasonCode(str, Enum):
    """Reason codes for question failures."""

    # Content gaps
    MISSING_DEFINITION = "missing_definition"  # Core concept not defined
    MISSING_PRICING = "missing_pricing"  # No pricing information
    MISSING_CONTACT = "missing_contact"  # No contact details
    MISSING_LOCATION = "missing_location"  # No location/service area
    MISSING_FEATURES = "missing_features"  # Product features not listed
    MISSING_SOCIAL_PROOF = "missing_social_proof"  # No testimonials/case studies

    # Structure issues
    BURIED_ANSWER = "buried_answer"  # Info exists but hard to find
    FRAGMENTED_INFO = "fragmented_info"  # Info spread across pages
    NO_DEDICATED_PAGE = "no_dedicated_page"  # Topic lacks dedicated page
    POOR_HEADINGS = "poor_headings"  # Headings don't match queries

    # Quality issues
    NOT_CITABLE = "not_citable"  # Info not clearly attributable
    VAGUE_LANGUAGE = "vague_language"  # Too generic/buzzwordy
    OUTDATED_INFO = "outdated_info"  # Stale information
    INCONSISTENT = "inconsistent"  # Conflicting information

    # Trust gaps
    TRUST_GAP = "trust_gap"  # Lacks credibility signals
    NO_AUTHORITY = "no_authority"  # No expertise indicators
    UNVERIFIED_CLAIMS = "unverified_claims"  # Claims lack evidence

    # Technical
    RENDER_REQUIRED = "render_required"  # Content requires JS to load
    BLOCKED_BY_ROBOTS = "blocked_by_robots"  # Blocked by robots.txt


@dataclass
class ReasonCodeInfo:
    """Information about a reason code."""

    code: ReasonCode
    name: str
    description: str
    severity: str  # critical, high, medium, low
    category: str  # content, structure, quality, trust, technical
    typical_impact: float  # Expected score impact (0-1)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "code": self.code.value,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "typical_impact": self.typical_impact,
        }


# Reason code metadata
REASON_CODE_INFO: dict[ReasonCode, ReasonCodeInfo] = {
    ReasonCode.MISSING_DEFINITION: ReasonCodeInfo(
        code=ReasonCode.MISSING_DEFINITION,
        name="Missing Definition",
        description="Core business concept or term is not clearly defined",
        severity="critical",
        category="content",
        typical_impact=0.3,
    ),
    ReasonCode.MISSING_PRICING: ReasonCodeInfo(
        code=ReasonCode.MISSING_PRICING,
        name="Missing Pricing",
        description="Pricing information is not available on the site",
        severity="high",
        category="content",
        typical_impact=0.25,
    ),
    ReasonCode.MISSING_CONTACT: ReasonCodeInfo(
        code=ReasonCode.MISSING_CONTACT,
        name="Missing Contact Info",
        description="Contact information is not easily accessible",
        severity="high",
        category="content",
        typical_impact=0.2,
    ),
    ReasonCode.MISSING_LOCATION: ReasonCodeInfo(
        code=ReasonCode.MISSING_LOCATION,
        name="Missing Location",
        description="Service area or location information is not specified",
        severity="medium",
        category="content",
        typical_impact=0.15,
    ),
    ReasonCode.MISSING_FEATURES: ReasonCodeInfo(
        code=ReasonCode.MISSING_FEATURES,
        name="Missing Features",
        description="Product or service features are not clearly listed",
        severity="high",
        category="content",
        typical_impact=0.2,
    ),
    ReasonCode.MISSING_SOCIAL_PROOF: ReasonCodeInfo(
        code=ReasonCode.MISSING_SOCIAL_PROOF,
        name="Missing Social Proof",
        description="No testimonials, case studies, or reviews present",
        severity="medium",
        category="content",
        typical_impact=0.15,
    ),
    ReasonCode.BURIED_ANSWER: ReasonCodeInfo(
        code=ReasonCode.BURIED_ANSWER,
        name="Buried Answer",
        description="Information exists but is difficult to find or extract",
        severity="medium",
        category="structure",
        typical_impact=0.15,
    ),
    ReasonCode.FRAGMENTED_INFO: ReasonCodeInfo(
        code=ReasonCode.FRAGMENTED_INFO,
        name="Fragmented Information",
        description="Related information is scattered across multiple pages",
        severity="medium",
        category="structure",
        typical_impact=0.1,
    ),
    ReasonCode.NO_DEDICATED_PAGE: ReasonCodeInfo(
        code=ReasonCode.NO_DEDICATED_PAGE,
        name="No Dedicated Page",
        description="Important topic lacks its own dedicated page",
        severity="medium",
        category="structure",
        typical_impact=0.15,
    ),
    ReasonCode.POOR_HEADINGS: ReasonCodeInfo(
        code=ReasonCode.POOR_HEADINGS,
        name="Poor Headings",
        description="Page headings don't match common search queries",
        severity="low",
        category="structure",
        typical_impact=0.1,
    ),
    ReasonCode.NOT_CITABLE: ReasonCodeInfo(
        code=ReasonCode.NOT_CITABLE,
        name="Not Citable",
        description="Information cannot be clearly attributed to a source",
        severity="medium",
        category="quality",
        typical_impact=0.1,
    ),
    ReasonCode.VAGUE_LANGUAGE: ReasonCodeInfo(
        code=ReasonCode.VAGUE_LANGUAGE,
        name="Vague Language",
        description="Content uses generic or buzzword-heavy language",
        severity="medium",
        category="quality",
        typical_impact=0.1,
    ),
    ReasonCode.OUTDATED_INFO: ReasonCodeInfo(
        code=ReasonCode.OUTDATED_INFO,
        name="Outdated Information",
        description="Content appears to be outdated or stale",
        severity="high",
        category="quality",
        typical_impact=0.2,
    ),
    ReasonCode.INCONSISTENT: ReasonCodeInfo(
        code=ReasonCode.INCONSISTENT,
        name="Inconsistent Information",
        description="Conflicting information found across pages",
        severity="critical",
        category="quality",
        typical_impact=0.25,
    ),
    ReasonCode.TRUST_GAP: ReasonCodeInfo(
        code=ReasonCode.TRUST_GAP,
        name="Trust Gap",
        description="Lacks credibility signals like reviews or certifications",
        severity="medium",
        category="trust",
        typical_impact=0.15,
    ),
    ReasonCode.NO_AUTHORITY: ReasonCodeInfo(
        code=ReasonCode.NO_AUTHORITY,
        name="No Authority Signals",
        description="No indicators of expertise or authority in the field",
        severity="medium",
        category="trust",
        typical_impact=0.1,
    ),
    ReasonCode.UNVERIFIED_CLAIMS: ReasonCodeInfo(
        code=ReasonCode.UNVERIFIED_CLAIMS,
        name="Unverified Claims",
        description="Claims are made without supporting evidence",
        severity="medium",
        category="trust",
        typical_impact=0.1,
    ),
    ReasonCode.RENDER_REQUIRED: ReasonCodeInfo(
        code=ReasonCode.RENDER_REQUIRED,
        name="JavaScript Required",
        description="Content requires JavaScript rendering to be visible",
        severity="high",
        category="technical",
        typical_impact=0.2,
    ),
    ReasonCode.BLOCKED_BY_ROBOTS: ReasonCodeInfo(
        code=ReasonCode.BLOCKED_BY_ROBOTS,
        name="Blocked by Robots",
        description="Content is blocked by robots.txt",
        severity="critical",
        category="technical",
        typical_impact=0.3,
    ),
}


def get_reason_info(code: ReasonCode) -> ReasonCodeInfo:
    """Get information about a reason code."""
    return REASON_CODE_INFO[code]


def get_codes_by_category(category: str) -> list[ReasonCode]:
    """Get all reason codes in a category."""
    return [
        info.code
        for info in REASON_CODE_INFO.values()
        if info.category == category
    ]


def get_codes_by_severity(severity: str) -> list[ReasonCode]:
    """Get all reason codes with a severity level."""
    return [
        info.code
        for info in REASON_CODE_INFO.values()
        if info.severity == severity
    ]
