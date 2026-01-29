"""Tests for reason codes module."""

from worker.fixes.reason_codes import (
    REASON_CODE_INFO,
    ReasonCode,
    ReasonCodeInfo,
    get_codes_by_category,
    get_codes_by_severity,
    get_reason_info,
)


class TestReasonCode:
    """Tests for ReasonCode enum."""

    def test_all_content_codes_exist(self) -> None:
        """All content-related reason codes exist."""
        assert ReasonCode.MISSING_DEFINITION == "missing_definition"
        assert ReasonCode.MISSING_PRICING == "missing_pricing"
        assert ReasonCode.MISSING_CONTACT == "missing_contact"
        assert ReasonCode.MISSING_LOCATION == "missing_location"
        assert ReasonCode.MISSING_FEATURES == "missing_features"
        assert ReasonCode.MISSING_SOCIAL_PROOF == "missing_social_proof"

    def test_all_structure_codes_exist(self) -> None:
        """All structure-related reason codes exist."""
        assert ReasonCode.BURIED_ANSWER == "buried_answer"
        assert ReasonCode.FRAGMENTED_INFO == "fragmented_info"
        assert ReasonCode.NO_DEDICATED_PAGE == "no_dedicated_page"
        assert ReasonCode.POOR_HEADINGS == "poor_headings"

    def test_all_quality_codes_exist(self) -> None:
        """All quality-related reason codes exist."""
        assert ReasonCode.NOT_CITABLE == "not_citable"
        assert ReasonCode.VAGUE_LANGUAGE == "vague_language"
        assert ReasonCode.OUTDATED_INFO == "outdated_info"
        assert ReasonCode.INCONSISTENT == "inconsistent"

    def test_all_trust_codes_exist(self) -> None:
        """All trust-related reason codes exist."""
        assert ReasonCode.TRUST_GAP == "trust_gap"
        assert ReasonCode.NO_AUTHORITY == "no_authority"
        assert ReasonCode.UNVERIFIED_CLAIMS == "unverified_claims"

    def test_all_technical_codes_exist(self) -> None:
        """All technical reason codes exist."""
        assert ReasonCode.RENDER_REQUIRED == "render_required"
        assert ReasonCode.BLOCKED_BY_ROBOTS == "blocked_by_robots"


class TestReasonCodeInfo:
    """Tests for ReasonCodeInfo dataclass."""

    def test_create_info(self) -> None:
        """Can create reason code info."""
        info = ReasonCodeInfo(
            code=ReasonCode.MISSING_DEFINITION,
            name="Missing Definition",
            description="Core concept not defined",
            severity="critical",
            category="content",
            typical_impact=0.3,
        )

        assert info.code == ReasonCode.MISSING_DEFINITION
        assert info.severity == "critical"
        assert info.typical_impact == 0.3

    def test_to_dict(self) -> None:
        """Converts to dict."""
        info = ReasonCodeInfo(
            code=ReasonCode.BURIED_ANSWER,
            name="Buried Answer",
            description="Hard to find",
            severity="medium",
            category="structure",
            typical_impact=0.15,
        )

        d = info.to_dict()
        assert d["code"] == "buried_answer"
        assert d["severity"] == "medium"
        assert d["category"] == "structure"


class TestReasonCodeInfoMapping:
    """Tests for REASON_CODE_INFO mapping."""

    def test_all_codes_have_info(self) -> None:
        """All reason codes have info defined."""
        for code in ReasonCode:
            assert code in REASON_CODE_INFO

    def test_all_severities_valid(self) -> None:
        """All severity levels are valid."""
        valid_severities = {"critical", "high", "medium", "low"}
        for info in REASON_CODE_INFO.values():
            assert info.severity in valid_severities

    def test_all_categories_valid(self) -> None:
        """All categories are valid."""
        valid_categories = {"content", "structure", "quality", "trust", "technical"}
        for info in REASON_CODE_INFO.values():
            assert info.category in valid_categories

    def test_impact_ranges_valid(self) -> None:
        """All impact values are in valid range."""
        for info in REASON_CODE_INFO.values():
            assert 0 <= info.typical_impact <= 1


class TestGetReasonInfo:
    """Tests for get_reason_info function."""

    def test_returns_info(self) -> None:
        """Returns info for valid code."""
        info = get_reason_info(ReasonCode.MISSING_PRICING)

        assert info.code == ReasonCode.MISSING_PRICING
        assert info.name == "Missing Pricing"
        assert info.category == "content"

    def test_returns_critical_severity(self) -> None:
        """Returns correct severity for critical codes."""
        info = get_reason_info(ReasonCode.MISSING_DEFINITION)
        assert info.severity == "critical"

    def test_returns_technical_category(self) -> None:
        """Returns correct category for technical codes."""
        info = get_reason_info(ReasonCode.RENDER_REQUIRED)
        assert info.category == "technical"


class TestGetCodesByCategory:
    """Tests for get_codes_by_category function."""

    def test_content_category(self) -> None:
        """Returns all content category codes."""
        codes = get_codes_by_category("content")

        assert ReasonCode.MISSING_DEFINITION in codes
        assert ReasonCode.MISSING_PRICING in codes
        assert ReasonCode.MISSING_CONTACT in codes
        assert ReasonCode.BURIED_ANSWER not in codes

    def test_structure_category(self) -> None:
        """Returns all structure category codes."""
        codes = get_codes_by_category("structure")

        assert ReasonCode.BURIED_ANSWER in codes
        assert ReasonCode.FRAGMENTED_INFO in codes
        assert ReasonCode.MISSING_DEFINITION not in codes

    def test_technical_category(self) -> None:
        """Returns all technical category codes."""
        codes = get_codes_by_category("technical")

        assert ReasonCode.RENDER_REQUIRED in codes
        assert ReasonCode.BLOCKED_BY_ROBOTS in codes
        assert len(codes) == 2

    def test_empty_for_invalid(self) -> None:
        """Returns empty list for invalid category."""
        codes = get_codes_by_category("invalid")
        assert codes == []


class TestGetCodesBySeverity:
    """Tests for get_codes_by_severity function."""

    def test_critical_severity(self) -> None:
        """Returns all critical severity codes."""
        codes = get_codes_by_severity("critical")

        assert ReasonCode.MISSING_DEFINITION in codes
        assert ReasonCode.INCONSISTENT in codes
        assert ReasonCode.BLOCKED_BY_ROBOTS in codes

    def test_high_severity(self) -> None:
        """Returns all high severity codes."""
        codes = get_codes_by_severity("high")

        assert ReasonCode.MISSING_PRICING in codes
        assert ReasonCode.OUTDATED_INFO in codes

    def test_medium_severity(self) -> None:
        """Returns all medium severity codes."""
        codes = get_codes_by_severity("medium")

        assert ReasonCode.BURIED_ANSWER in codes
        assert ReasonCode.TRUST_GAP in codes

    def test_empty_for_invalid(self) -> None:
        """Returns empty list for invalid severity."""
        codes = get_codes_by_severity("extreme")
        assert codes == []
