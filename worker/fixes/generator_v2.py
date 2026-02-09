"""Findable Score v2 Fix Generator.

Consolidates fixes from all scoring pillars into a unified,
prioritized action plan with impact estimates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

import structlog

from worker.fixes.generator import FixPlan
from worker.scoring.authority import AuthoritySignalsScore
from worker.scoring.schema import SchemaRichnessScore
from worker.scoring.structure import StructureQualityScore
from worker.scoring.technical import TechnicalReadinessScore
from worker.tasks.authority_check import generate_authority_fixes
from worker.tasks.schema_check import generate_schema_fixes
from worker.tasks.structure_check import generate_structure_fixes
from worker.tasks.technical_check import generate_technical_fixes

logger = structlog.get_logger(__name__)


class FixCategory(StrEnum):
    """Categories for v2 fixes."""

    TECHNICAL = "technical"
    STRUCTURE = "structure"
    SCHEMA = "schema"
    AUTHORITY = "authority"
    CONTENT = "content"


class EffortLevel(StrEnum):
    """Effort levels for implementing fixes."""

    LOW = "low"  # < 1 hour, no technical skills
    MEDIUM = "medium"  # 1-4 hours, some technical skills
    HIGH = "high"  # > 4 hours or requires developer


class ImpactLevel(StrEnum):
    """Impact levels for fixes."""

    CRITICAL = "critical"  # Must fix immediately
    HIGH = "high"  # Significant improvement
    MEDIUM = "medium"  # Moderate improvement
    LOW = "low"  # Nice to have


@dataclass
class UnifiedFix:
    """A unified fix recommendation in the v2 system."""

    id: str
    category: FixCategory
    title: str
    description: str
    priority: int  # 1 = highest
    impact_level: ImpactLevel
    effort_level: EffortLevel
    estimated_points: float  # Estimated point improvement to total score
    impact_points: float  # Points improvement within affected pillar (0-100 scale)
    affected_pillar: str
    scaffold: str | None = None  # Template/example code if applicable
    target_url: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "impact_level": self.impact_level.value,
            "effort_level": self.effort_level.value,
            "estimated_points": round(self.estimated_points, 2),
            "impact_points": round(self.impact_points, 2),
            "affected_pillar": self.affected_pillar,
            "scaffold": self.scaffold,
            "target_url": self.target_url,
            "metadata": self.metadata,
        }


@dataclass
class ActionItem:
    """A single item in the Action Center."""

    fix: UnifiedFix
    order: int
    status: str = "pending"  # pending, in_progress, completed, skipped

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "status": self.status,
            "fix": self.fix.to_dict(),
        }


@dataclass
class ActionCenter:
    """Prioritized action center with all fixes organized by impact."""

    # Quick wins (low effort, high impact)
    quick_wins: list[ActionItem]

    # High priority (critical issues)
    high_priority: list[ActionItem]

    # Standard fixes (organized by category)
    by_category: dict[str, list[ActionItem]]

    # All fixes in priority order
    all_fixes: list[ActionItem]

    # Summary stats
    total_fixes: int
    estimated_total_points: float
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

    def to_dict(self) -> dict:
        return {
            "quick_wins": [a.to_dict() for a in self.quick_wins],
            "high_priority": [a.to_dict() for a in self.high_priority],
            "by_category": {
                cat: [a.to_dict() for a in items] for cat, items in self.by_category.items()
            },
            "all_fixes": [a.to_dict() for a in self.all_fixes],
            "summary": {
                "total_fixes": self.total_fixes,
                "estimated_total_points": round(self.estimated_total_points, 2),
                "critical_count": self.critical_count,
                "high_count": self.high_count,
                "medium_count": self.medium_count,
                "low_count": self.low_count,
            },
        }


@dataclass
class FixPlanV2:
    """Complete v2 fix plan with action center."""

    id: UUID
    site_id: UUID
    run_id: UUID
    company_name: str

    # Action center
    action_center: ActionCenter

    # Original v1 fix plan (content fixes)
    content_fix_plan: FixPlan | None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "2.0"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "site_id": str(self.site_id),
            "run_id": str(self.run_id),
            "company_name": self.company_name,
            "action_center": self.action_center.to_dict(),
            "content_fixes": self.content_fix_plan.to_dict() if self.content_fix_plan else None,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
        }


class FixGeneratorV2:
    """Generates unified fix plans from all v2 pillar scores."""

    # Impact multipliers by pillar (how much 1% improvement in pillar affects total)
    PILLAR_IMPACT = {
        "technical": 0.15,
        "structure": 0.20,
        "schema": 0.15,
        "authority": 0.15,
        "retrieval": 0.25,
        "coverage": 0.10,
    }

    def generate(
        self,
        site_id: UUID,
        run_id: UUID,
        company_name: str,
        technical_score: TechnicalReadinessScore | None = None,
        structure_score: StructureQualityScore | None = None,
        schema_score: SchemaRichnessScore | None = None,
        authority_score: AuthoritySignalsScore | None = None,
        content_fix_plan: FixPlan | None = None,
    ) -> FixPlanV2:
        """
        Generate unified fix plan from all pillar scores.

        Args:
            site_id: Site identifier
            run_id: Run identifier
            company_name: Company name
            technical_score: Technical Readiness score
            structure_score: Structure Quality score
            schema_score: Schema Richness score
            authority_score: Authority Signals score
            content_fix_plan: Original v1 content fix plan

        Returns:
            FixPlanV2 with action center
        """
        all_fixes: list[UnifiedFix] = []

        # Generate fixes from each pillar
        if technical_score:
            tech_fixes = self._convert_technical_fixes(technical_score)
            all_fixes.extend(tech_fixes)

        if structure_score:
            struct_fixes = self._convert_structure_fixes(structure_score)
            all_fixes.extend(struct_fixes)

        if schema_score:
            schema_fixes = self._convert_schema_fixes(schema_score)
            all_fixes.extend(schema_fixes)

        if authority_score:
            auth_fixes = self._convert_authority_fixes(authority_score)
            all_fixes.extend(auth_fixes)

        # Convert content fixes from v1 plan
        if content_fix_plan:
            content_fixes = self._convert_content_fixes(content_fix_plan)
            all_fixes.extend(content_fixes)

        # Build action center
        action_center = self._build_action_center(all_fixes)

        return FixPlanV2(
            id=uuid4(),
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            action_center=action_center,
            content_fix_plan=content_fix_plan,
        )

    def _convert_technical_fixes(self, score: TechnicalReadinessScore) -> list[UnifiedFix]:
        """Convert technical fixes to unified format."""
        fixes = []
        raw_fixes = generate_technical_fixes(score)

        for i, fix in enumerate(raw_fixes):
            # Technical fixes use different format - normalize
            priority = self._normalize_priority(fix.get("priority", "medium"))
            impact_level = self._get_impact_level(priority)
            effort = self._normalize_effort(fix.get("effort", "medium"))

            # impact_points is the pillar-level improvement (0-100 scale)
            # estimated_impact or impact_points from raw fix
            impact_points = fix.get("impact_points") or fix.get("estimated_impact", 10.0)

            # estimated_points is the total score improvement
            estimated_points = impact_points * self.PILLAR_IMPACT["technical"]

            # Generate ID if not present
            fix_id = fix.get("id") or f"technical_fix_{i + 1}"

            fixes.append(
                UnifiedFix(
                    id=fix_id,
                    category=FixCategory.TECHNICAL,
                    title=fix["title"],
                    description=fix["description"],
                    priority=priority,
                    impact_level=impact_level,
                    effort_level=effort,
                    estimated_points=estimated_points,
                    impact_points=impact_points,
                    affected_pillar="technical",
                    scaffold=fix.get("scaffold"),
                )
            )

        return fixes

    def _convert_structure_fixes(self, score: StructureQualityScore) -> list[UnifiedFix]:
        """Convert structure fixes to unified format."""
        fixes = []
        raw_fixes = generate_structure_fixes(score)

        for fix in raw_fixes:
            impact_level = self._get_impact_level(fix.get("priority", 3))
            effort = EffortLevel(fix.get("effort", "medium"))

            # impact_points is the pillar-level improvement (0-100 scale)
            impact_points = fix.get("impact_points") or fix.get("estimated_impact", 10.0)
            estimated_points = impact_points * self.PILLAR_IMPACT["structure"]

            fixes.append(
                UnifiedFix(
                    id=fix["id"],
                    category=FixCategory.STRUCTURE,
                    title=fix["title"],
                    description=fix["description"],
                    priority=fix.get("priority", 2),
                    impact_level=impact_level,
                    effort_level=effort,
                    estimated_points=estimated_points,
                    impact_points=impact_points,
                    affected_pillar="structure",
                )
            )

        return fixes

    def _convert_schema_fixes(self, score: SchemaRichnessScore) -> list[UnifiedFix]:
        """Convert schema fixes to unified format."""
        fixes = []
        raw_fixes = generate_schema_fixes(score)

        for fix in raw_fixes:
            impact_level = self._get_impact_level(fix.get("priority", 3))
            effort = EffortLevel(fix.get("effort", "medium"))

            # impact_points is the pillar-level improvement (0-100 scale)
            impact_points = fix.get("impact_points") or fix.get("estimated_impact", 10.0)
            estimated_points = impact_points * self.PILLAR_IMPACT["schema"]

            fixes.append(
                UnifiedFix(
                    id=fix["id"],
                    category=FixCategory.SCHEMA,
                    title=fix["title"],
                    description=fix["description"],
                    priority=fix.get("priority", 2),
                    impact_level=impact_level,
                    effort_level=effort,
                    estimated_points=estimated_points,
                    impact_points=impact_points,
                    affected_pillar="schema",
                    scaffold=fix.get("scaffold"),
                )
            )

        return fixes

    def _convert_authority_fixes(self, score: AuthoritySignalsScore) -> list[UnifiedFix]:
        """Convert authority fixes to unified format."""
        fixes = []
        raw_fixes = generate_authority_fixes(score)

        for fix in raw_fixes:
            impact_level = self._get_impact_level(fix.get("priority", 3))
            effort = EffortLevel(fix.get("effort", "medium"))

            # impact_points is the pillar-level improvement (0-100 scale)
            impact_points = fix.get("impact_points") or fix.get("estimated_impact", 10.0)
            estimated_points = impact_points * self.PILLAR_IMPACT["authority"]

            fixes.append(
                UnifiedFix(
                    id=fix["id"],
                    category=FixCategory.AUTHORITY,
                    title=fix["title"],
                    description=fix["description"],
                    priority=fix.get("priority", 2),
                    impact_level=impact_level,
                    effort_level=effort,
                    estimated_points=estimated_points,
                    impact_points=impact_points,
                    affected_pillar="authority",
                )
            )

        return fixes

    def _convert_content_fixes(self, plan: FixPlan) -> list[UnifiedFix]:
        """Convert v1 content fixes to unified format."""
        fixes = []

        for fix in plan.fixes:
            # Map priority to impact level
            if fix.priority == 1:
                impact_level = ImpactLevel.CRITICAL
            elif fix.priority == 2:
                impact_level = ImpactLevel.HIGH
            elif fix.priority == 3:
                impact_level = ImpactLevel.MEDIUM
            else:
                impact_level = ImpactLevel.LOW

            # Map effort
            effort = EffortLevel(fix.effort_level)

            # impact_points is from v1 estimated_impact (0-1 scale, convert to 0-100)
            # v1 estimated_impact is already normalized
            impact_points = fix.estimated_impact * 100

            # Estimate total score points (content affects retrieval and coverage)
            estimated_points = (
                fix.estimated_impact
                * (self.PILLAR_IMPACT["retrieval"] + self.PILLAR_IMPACT["coverage"])
                * 100
            )

            fixes.append(
                UnifiedFix(
                    id=str(fix.id),
                    category=FixCategory.CONTENT,
                    title=fix.template.title,
                    description=fix.template.description,
                    priority=fix.priority,
                    impact_level=impact_level,
                    effort_level=effort,
                    estimated_points=estimated_points,
                    impact_points=impact_points,
                    affected_pillar="content",
                    scaffold=fix.scaffold,
                    target_url=fix.target_url,
                    metadata={
                        "reason_code": fix.reason_code.value,
                        "affected_questions": fix.affected_question_ids,
                    },
                )
            )

        return fixes

    def _normalize_priority(self, priority: str | int) -> int:
        """Normalize priority to int (1-4 scale)."""
        if isinstance(priority, int):
            return priority

        # Handle string priorities from technical fixes
        priority_map = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
        }
        return priority_map.get(str(priority).lower(), 3)

    def _normalize_effort(self, effort: str) -> EffortLevel:
        """Normalize effort string to EffortLevel enum."""
        effort_lower = str(effort).lower()

        # Direct enum values
        if effort_lower in ("low", "medium", "high"):
            return EffortLevel(effort_lower)

        # Map descriptive efforts to levels
        if "minute" in effort_lower:
            # "5 minutes", "30 minutes" -> low
            return EffortLevel.LOW
        elif "hour" in effort_lower:
            # Parse hours
            try:
                # Extract first number
                import re

                nums = re.findall(r"\d+", effort_lower)
                if nums:
                    hours = int(nums[0])
                    if hours <= 1:
                        return EffortLevel.LOW
                    elif hours <= 4:
                        return EffortLevel.MEDIUM
                    else:
                        return EffortLevel.HIGH
            except (ValueError, IndexError):
                pass
            return EffortLevel.MEDIUM
        elif "day" in effort_lower or "week" in effort_lower:
            return EffortLevel.HIGH

        return EffortLevel.MEDIUM

    def _get_impact_level(self, priority: int) -> ImpactLevel:
        """Convert priority to impact level."""
        return {
            1: ImpactLevel.CRITICAL,
            2: ImpactLevel.HIGH,
            3: ImpactLevel.MEDIUM,
        }.get(priority, ImpactLevel.LOW)

    def _build_action_center(self, fixes: list[UnifiedFix]) -> ActionCenter:
        """Build action center from all fixes."""
        # Sort by priority, then by estimated points (descending)
        sorted_fixes = sorted(
            fixes,
            key=lambda f: (f.priority, -f.estimated_points),
        )

        # Convert to action items
        all_items = [ActionItem(fix=fix, order=i + 1) for i, fix in enumerate(sorted_fixes)]

        # Identify quick wins (low effort, high/critical impact)
        quick_wins = [
            item
            for item in all_items
            if item.fix.effort_level == EffortLevel.LOW
            and item.fix.impact_level in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]
        ]

        # Identify high priority (critical impact)
        high_priority = [
            item for item in all_items if item.fix.impact_level == ImpactLevel.CRITICAL
        ]

        # Group by category
        by_category: dict[str, list[ActionItem]] = {}
        for item in all_items:
            cat = item.fix.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)

        # Calculate stats
        total_points = sum(f.estimated_points for f in fixes)
        critical_count = sum(1 for f in fixes if f.impact_level == ImpactLevel.CRITICAL)
        high_count = sum(1 for f in fixes if f.impact_level == ImpactLevel.HIGH)
        medium_count = sum(1 for f in fixes if f.impact_level == ImpactLevel.MEDIUM)
        low_count = sum(1 for f in fixes if f.impact_level == ImpactLevel.LOW)

        return ActionCenter(
            quick_wins=quick_wins[:5],  # Top 5 quick wins
            high_priority=high_priority[:5],  # Top 5 critical
            by_category=by_category,
            all_fixes=all_items,
            total_fixes=len(fixes),
            estimated_total_points=total_points,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
        )


def generate_fix_plan_v2(
    site_id: UUID,
    run_id: UUID,
    company_name: str,
    technical_score: TechnicalReadinessScore | None = None,
    structure_score: StructureQualityScore | None = None,
    schema_score: SchemaRichnessScore | None = None,
    authority_score: AuthoritySignalsScore | None = None,
    content_fix_plan: FixPlan | None = None,
) -> FixPlanV2:
    """
    Convenience function to generate v2 fix plan.

    Args:
        site_id: Site identifier
        run_id: Run identifier
        company_name: Company name
        technical_score: Technical Readiness score
        structure_score: Structure Quality score
        schema_score: Schema Richness score
        authority_score: Authority Signals score
        content_fix_plan: Original v1 content fix plan

    Returns:
        FixPlanV2 with action center
    """
    generator = FixGeneratorV2()
    return generator.generate(
        site_id=site_id,
        run_id=run_id,
        company_name=company_name,
        technical_score=technical_score,
        structure_score=structure_score,
        schema_score=schema_score,
        authority_score=authority_score,
        content_fix_plan=content_fix_plan,
    )
