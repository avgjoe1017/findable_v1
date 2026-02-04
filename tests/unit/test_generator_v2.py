"""Unit tests for Findable Score v2 Fix Generator."""

from uuid import uuid4

from worker.fixes.generator_v2 import (
    ActionCenter,
    ActionItem,
    EffortLevel,
    FixCategory,
    FixGeneratorV2,
    FixPlanV2,
    ImpactLevel,
    UnifiedFix,
    generate_fix_plan_v2,
)

# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Tests for fix-related enums."""

    def test_fix_category_values(self):
        """FixCategory has expected values."""
        assert FixCategory.TECHNICAL.value == "technical"
        assert FixCategory.STRUCTURE.value == "structure"
        assert FixCategory.SCHEMA.value == "schema"
        assert FixCategory.AUTHORITY.value == "authority"
        assert FixCategory.CONTENT.value == "content"

    def test_effort_level_values(self):
        """EffortLevel has expected values."""
        assert EffortLevel.LOW.value == "low"
        assert EffortLevel.MEDIUM.value == "medium"
        assert EffortLevel.HIGH.value == "high"

    def test_impact_level_values(self):
        """ImpactLevel has expected values."""
        assert ImpactLevel.CRITICAL.value == "critical"
        assert ImpactLevel.HIGH.value == "high"
        assert ImpactLevel.MEDIUM.value == "medium"
        assert ImpactLevel.LOW.value == "low"


# ============================================================================
# UnifiedFix Tests
# ============================================================================


class TestUnifiedFix:
    """Tests for UnifiedFix dataclass."""

    def test_unified_fix_creation(self):
        """UnifiedFix stores data correctly."""
        fix = UnifiedFix(
            id="fix-001",
            category=FixCategory.TECHNICAL,
            title="Add GPTBot to robots.txt",
            description="Allow GPTBot access in robots.txt",
            priority=1,
            impact_level=ImpactLevel.CRITICAL,
            effort_level=EffortLevel.LOW,
            estimated_points=2.5,
            impact_points=16.67,
            affected_pillar="technical",
        )

        assert fix.id == "fix-001"
        assert fix.category == FixCategory.TECHNICAL
        assert fix.priority == 1
        assert fix.estimated_points == 2.5
        assert fix.impact_points == 16.67

    def test_unified_fix_to_dict(self):
        """UnifiedFix converts to dictionary correctly."""
        fix = UnifiedFix(
            id="fix-002",
            category=FixCategory.SCHEMA,
            title="Add FAQPage schema",
            description="Implement FAQPage structured data",
            priority=2,
            impact_level=ImpactLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            estimated_points=3.0,
            impact_points=20.0,
            affected_pillar="schema",
            scaffold="<script type='application/ld+json'>...</script>",
        )

        data = fix.to_dict()
        assert data["id"] == "fix-002"
        assert data["category"] == "schema"
        assert data["impact_level"] == "high"
        assert data["effort_level"] == "medium"
        assert data["estimated_points"] == 3.0
        assert data["impact_points"] == 20.0
        assert data["scaffold"] is not None

    def test_unified_fix_optional_fields(self):
        """UnifiedFix handles optional fields correctly."""
        fix = UnifiedFix(
            id="fix-003",
            category=FixCategory.AUTHORITY,
            title="Add author bylines",
            description="Add author attribution",
            priority=2,
            impact_level=ImpactLevel.HIGH,
            effort_level=EffortLevel.MEDIUM,
            estimated_points=2.0,
            impact_points=13.33,
            affected_pillar="authority",
            target_url="https://example.com/blog/post-1",
            metadata={"page_count": 5},
        )

        data = fix.to_dict()
        assert data["target_url"] == "https://example.com/blog/post-1"
        assert data["metadata"]["page_count"] == 5


# ============================================================================
# ActionItem Tests
# ============================================================================


class TestActionItem:
    """Tests for ActionItem dataclass."""

    def test_action_item_creation(self):
        """ActionItem wraps UnifiedFix correctly."""
        fix = UnifiedFix(
            id="fix-001",
            category=FixCategory.TECHNICAL,
            title="Test fix",
            description="Test description",
            priority=1,
            impact_level=ImpactLevel.HIGH,
            effort_level=EffortLevel.LOW,
            estimated_points=2.0,
            impact_points=13.33,
            affected_pillar="technical",
        )

        item = ActionItem(fix=fix, order=1)
        assert item.order == 1
        assert item.status == "pending"
        assert item.fix.id == "fix-001"

    def test_action_item_to_dict(self):
        """ActionItem converts to dictionary correctly."""
        fix = UnifiedFix(
            id="fix-001",
            category=FixCategory.TECHNICAL,
            title="Test fix",
            description="Test description",
            priority=1,
            impact_level=ImpactLevel.HIGH,
            effort_level=EffortLevel.LOW,
            estimated_points=2.0,
            impact_points=13.33,
            affected_pillar="technical",
        )

        item = ActionItem(fix=fix, order=1, status="in_progress")
        data = item.to_dict()

        assert data["order"] == 1
        assert data["status"] == "in_progress"
        assert "fix" in data


# ============================================================================
# ActionCenter Tests
# ============================================================================


class TestActionCenter:
    """Tests for ActionCenter dataclass."""

    def test_action_center_creation(self):
        """ActionCenter stores all fix categories."""
        center = ActionCenter(
            quick_wins=[],
            high_priority=[],
            by_category={},
            all_fixes=[],
            total_fixes=0,
            estimated_total_points=0.0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
        )

        assert center.total_fixes == 0
        assert center.estimated_total_points == 0.0

    def test_action_center_to_dict(self):
        """ActionCenter converts to dictionary correctly."""
        fix = UnifiedFix(
            id="fix-001",
            category=FixCategory.TECHNICAL,
            title="Test fix",
            description="Test description",
            priority=1,
            impact_level=ImpactLevel.CRITICAL,
            effort_level=EffortLevel.LOW,
            estimated_points=2.0,
            impact_points=13.33,
            affected_pillar="technical",
        )
        item = ActionItem(fix=fix, order=1)

        center = ActionCenter(
            quick_wins=[item],
            high_priority=[item],
            by_category={"technical": [item]},
            all_fixes=[item],
            total_fixes=1,
            estimated_total_points=2.0,
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
        )

        data = center.to_dict()
        assert data["summary"]["total_fixes"] == 1
        assert data["summary"]["critical_count"] == 1
        assert len(data["quick_wins"]) == 1
        assert "technical" in data["by_category"]


# ============================================================================
# FixPlanV2 Tests
# ============================================================================


class TestFixPlanV2:
    """Tests for FixPlanV2 dataclass."""

    def test_fix_plan_v2_creation(self):
        """FixPlanV2 stores all data correctly."""
        site_id = uuid4()
        run_id = uuid4()

        center = ActionCenter(
            quick_wins=[],
            high_priority=[],
            by_category={},
            all_fixes=[],
            total_fixes=0,
            estimated_total_points=0.0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
        )

        plan = FixPlanV2(
            id=uuid4(),
            site_id=site_id,
            run_id=run_id,
            company_name="Test Company",
            action_center=center,
            content_fix_plan=None,
        )

        assert plan.company_name == "Test Company"
        assert plan.version == "2.0"

    def test_fix_plan_v2_to_dict(self):
        """FixPlanV2 converts to dictionary correctly."""
        site_id = uuid4()
        run_id = uuid4()

        center = ActionCenter(
            quick_wins=[],
            high_priority=[],
            by_category={},
            all_fixes=[],
            total_fixes=0,
            estimated_total_points=0.0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
        )

        plan = FixPlanV2(
            id=uuid4(),
            site_id=site_id,
            run_id=run_id,
            company_name="Test Company",
            action_center=center,
            content_fix_plan=None,
        )

        data = plan.to_dict()
        assert data["company_name"] == "Test Company"
        assert data["version"] == "2.0"
        assert "action_center" in data
        assert data["content_fixes"] is None


# ============================================================================
# FixGeneratorV2 Helper Method Tests
# ============================================================================


class TestFixGeneratorHelpers:
    """Tests for FixGeneratorV2 helper methods."""

    def test_normalize_priority_int(self):
        """Int priorities pass through."""
        generator = FixGeneratorV2()
        assert generator._normalize_priority(1) == 1
        assert generator._normalize_priority(2) == 2
        assert generator._normalize_priority(3) == 3

    def test_normalize_priority_string(self):
        """String priorities are converted."""
        generator = FixGeneratorV2()
        assert generator._normalize_priority("critical") == 1
        assert generator._normalize_priority("high") == 2
        assert generator._normalize_priority("medium") == 3
        assert generator._normalize_priority("low") == 4

    def test_normalize_priority_case_insensitive(self):
        """String priorities are case insensitive."""
        generator = FixGeneratorV2()
        assert generator._normalize_priority("CRITICAL") == 1
        assert generator._normalize_priority("High") == 2

    def test_normalize_effort_enum_values(self):
        """Enum values pass through."""
        generator = FixGeneratorV2()
        assert generator._normalize_effort("low") == EffortLevel.LOW
        assert generator._normalize_effort("medium") == EffortLevel.MEDIUM
        assert generator._normalize_effort("high") == EffortLevel.HIGH

    def test_normalize_effort_minutes(self):
        """Minute-based effort is LOW."""
        generator = FixGeneratorV2()
        assert generator._normalize_effort("5 minutes") == EffortLevel.LOW
        assert generator._normalize_effort("30 minutes") == EffortLevel.LOW

    def test_normalize_effort_hours(self):
        """Hour-based effort is scaled."""
        generator = FixGeneratorV2()
        assert generator._normalize_effort("1 hour") == EffortLevel.LOW
        assert generator._normalize_effort("2-4 hours") == EffortLevel.MEDIUM
        assert generator._normalize_effort("8 hours") == EffortLevel.HIGH

    def test_normalize_effort_days(self):
        """Day/week-based effort is HIGH."""
        generator = FixGeneratorV2()
        assert generator._normalize_effort("2 days") == EffortLevel.HIGH
        assert generator._normalize_effort("1 week") == EffortLevel.HIGH

    def test_get_impact_level(self):
        """Priority maps to impact level."""
        generator = FixGeneratorV2()
        assert generator._get_impact_level(1) == ImpactLevel.CRITICAL
        assert generator._get_impact_level(2) == ImpactLevel.HIGH
        assert generator._get_impact_level(3) == ImpactLevel.MEDIUM
        assert generator._get_impact_level(4) == ImpactLevel.LOW


# ============================================================================
# FixGeneratorV2 Generation Tests
# ============================================================================


class TestFixGeneratorV2:
    """Tests for FixGeneratorV2 class."""

    def test_generate_empty(self):
        """Generate fix plan with no scores."""
        generator = FixGeneratorV2()
        site_id = uuid4()
        run_id = uuid4()

        result = generator.generate(
            site_id=site_id,
            run_id=run_id,
            company_name="Test Corp",
        )

        assert isinstance(result, FixPlanV2)
        assert result.action_center.total_fixes == 0

    def test_build_action_center_empty(self):
        """Empty fix list produces empty action center."""
        generator = FixGeneratorV2()
        center = generator._build_action_center([])

        assert center.total_fixes == 0
        assert len(center.quick_wins) == 0
        assert len(center.high_priority) == 0
        assert len(center.all_fixes) == 0

    def test_build_action_center_categorizes(self):
        """Fixes are categorized by type."""
        generator = FixGeneratorV2()

        fixes = [
            UnifiedFix(
                id="tech-1",
                category=FixCategory.TECHNICAL,
                title="Tech fix",
                description="Desc",
                priority=2,
                impact_level=ImpactLevel.HIGH,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="schema-1",
                category=FixCategory.SCHEMA,
                title="Schema fix",
                description="Desc",
                priority=2,
                impact_level=ImpactLevel.HIGH,
                effort_level=EffortLevel.MEDIUM,
                estimated_points=2.0,
                impact_points=13.33,
                affected_pillar="schema",
            ),
        ]

        center = generator._build_action_center(fixes)

        assert center.total_fixes == 2
        assert "technical" in center.by_category
        assert "schema" in center.by_category
        assert len(center.by_category["technical"]) == 1
        assert len(center.by_category["schema"]) == 1

    def test_build_action_center_quick_wins(self):
        """Quick wins are low effort + high impact."""
        generator = FixGeneratorV2()

        fixes = [
            UnifiedFix(
                id="quick-1",
                category=FixCategory.TECHNICAL,
                title="Quick win",
                description="Desc",
                priority=1,
                impact_level=ImpactLevel.CRITICAL,
                effort_level=EffortLevel.LOW,  # Low effort
                estimated_points=5.0,
                impact_points=33.33,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="not-quick",
                category=FixCategory.TECHNICAL,
                title="Not quick win",
                description="Desc",
                priority=1,
                impact_level=ImpactLevel.CRITICAL,
                effort_level=EffortLevel.HIGH,  # High effort - not a quick win
                estimated_points=5.0,
                impact_points=33.33,
                affected_pillar="technical",
            ),
        ]

        center = generator._build_action_center(fixes)

        # Only the low-effort one should be a quick win
        assert len(center.quick_wins) == 1
        assert center.quick_wins[0].fix.id == "quick-1"

    def test_build_action_center_high_priority(self):
        """High priority are critical impact."""
        generator = FixGeneratorV2()

        fixes = [
            UnifiedFix(
                id="critical-1",
                category=FixCategory.TECHNICAL,
                title="Critical",
                description="Desc",
                priority=1,
                impact_level=ImpactLevel.CRITICAL,
                effort_level=EffortLevel.HIGH,
                estimated_points=5.0,
                impact_points=33.33,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="medium-1",
                category=FixCategory.TECHNICAL,
                title="Medium",
                description="Desc",
                priority=3,
                impact_level=ImpactLevel.MEDIUM,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
        ]

        center = generator._build_action_center(fixes)

        # Only critical should be high priority
        assert len(center.high_priority) == 1
        assert center.high_priority[0].fix.id == "critical-1"

    def test_build_action_center_sorted_by_priority(self):
        """All fixes are sorted by priority then points."""
        generator = FixGeneratorV2()

        fixes = [
            UnifiedFix(
                id="low-priority",
                category=FixCategory.TECHNICAL,
                title="Low priority",
                description="Desc",
                priority=3,
                impact_level=ImpactLevel.MEDIUM,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="high-priority",
                category=FixCategory.SCHEMA,
                title="High priority",
                description="Desc",
                priority=1,
                impact_level=ImpactLevel.CRITICAL,
                effort_level=EffortLevel.LOW,
                estimated_points=5.0,
                impact_points=33.33,
                affected_pillar="schema",
            ),
        ]

        center = generator._build_action_center(fixes)

        # High priority should come first
        assert center.all_fixes[0].fix.id == "high-priority"
        assert center.all_fixes[1].fix.id == "low-priority"

    def test_build_action_center_counts_impact_levels(self):
        """Impact level counts are accurate."""
        generator = FixGeneratorV2()

        fixes = [
            UnifiedFix(
                id="1",
                category=FixCategory.TECHNICAL,
                title="T",
                description="D",
                priority=1,
                impact_level=ImpactLevel.CRITICAL,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="2",
                category=FixCategory.TECHNICAL,
                title="T",
                description="D",
                priority=2,
                impact_level=ImpactLevel.HIGH,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="3",
                category=FixCategory.TECHNICAL,
                title="T",
                description="D",
                priority=3,
                impact_level=ImpactLevel.MEDIUM,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
            UnifiedFix(
                id="4",
                category=FixCategory.TECHNICAL,
                title="T",
                description="D",
                priority=4,
                impact_level=ImpactLevel.LOW,
                effort_level=EffortLevel.LOW,
                estimated_points=1.0,
                impact_points=6.67,
                affected_pillar="technical",
            ),
        ]

        center = generator._build_action_center(fixes)

        assert center.critical_count == 1
        assert center.high_count == 1
        assert center.medium_count == 1
        assert center.low_count == 1


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestGenerateFixPlanV2:
    """Tests for generate_fix_plan_v2 convenience function."""

    def test_convenience_function_works(self):
        """Convenience function produces valid result."""
        site_id = uuid4()
        run_id = uuid4()

        result = generate_fix_plan_v2(
            site_id=site_id,
            run_id=run_id,
            company_name="Test Corp",
        )

        assert isinstance(result, FixPlanV2)
        assert result.company_name == "Test Corp"
