"""Tests for fix templates module."""

from worker.fixes.reason_codes import ReasonCode
from worker.fixes.templates import (
    FIX_TEMPLATES,
    FixTemplate,
    get_template,
    get_templates_by_category,
    get_templates_by_question_category,
)
from worker.questions.universal import QuestionCategory


class TestFixTemplate:
    """Tests for FixTemplate dataclass."""

    def test_create_template(self) -> None:
        """Can create a fix template."""
        template = FixTemplate(
            reason_code=ReasonCode.MISSING_PRICING,
            title="Add Pricing",
            description="Create pricing page",
            action_verb="Create",
            target_location="/pricing",
            scaffold_template="## Pricing\n[CONTENT]",
            examples=["Example 1"],
            related_categories=[QuestionCategory.OFFERINGS],
            priority=1,
        )

        assert template.reason_code == ReasonCode.MISSING_PRICING
        assert template.title == "Add Pricing"
        assert template.priority == 1

    def test_to_dict(self) -> None:
        """Converts to dict."""
        template = FixTemplate(
            reason_code=ReasonCode.MISSING_CONTACT,
            title="Add Contact Info",
            description="Add contact details",
            action_verb="Add",
            target_location="/contact",
            scaffold_template="## Contact\n[EMAIL]",
            related_categories=[QuestionCategory.CONTACT],
        )

        d = template.to_dict()
        assert d["reason_code"] == "missing_contact"
        assert d["title"] == "Add Contact Info"
        assert d["related_categories"] == ["contact"]

    def test_default_examples_empty(self) -> None:
        """Examples default to empty list."""
        template = FixTemplate(
            reason_code=ReasonCode.BURIED_ANSWER,
            title="Surface Info",
            description="Move info",
            action_verb="Move",
            target_location="Homepage",
            scaffold_template="[CONTENT]",
        )

        assert template.examples == []
        assert template.related_categories == []

    def test_default_priority(self) -> None:
        """Priority defaults to 1."""
        template = FixTemplate(
            reason_code=ReasonCode.VAGUE_LANGUAGE,
            title="Use Specifics",
            description="Be specific",
            action_verb="Replace",
            target_location="Copy",
            scaffold_template="[CONTENT]",
        )

        assert template.priority == 1


class TestFixTemplatesMapping:
    """Tests for FIX_TEMPLATES mapping."""

    def test_all_codes_have_templates(self) -> None:
        """All reason codes have templates defined."""
        for code in ReasonCode:
            assert code in FIX_TEMPLATES, f"Missing template for {code}"

    def test_all_templates_have_scaffold(self) -> None:
        """All templates have non-empty scaffolds."""
        for template in FIX_TEMPLATES.values():
            assert len(template.scaffold_template) > 0

    def test_all_templates_have_title(self) -> None:
        """All templates have titles."""
        for template in FIX_TEMPLATES.values():
            assert len(template.title) > 0

    def test_all_templates_have_action_verb(self) -> None:
        """All templates have action verbs."""
        valid_verbs = {"Add", "Create", "Update", "Move", "Replace", "Fix", "Implement"}
        for template in FIX_TEMPLATES.values():
            assert template.action_verb in valid_verbs

    def test_all_priorities_valid(self) -> None:
        """All priorities are in valid range."""
        for template in FIX_TEMPLATES.values():
            assert 1 <= template.priority <= 5


class TestGetTemplate:
    """Tests for get_template function."""

    def test_returns_template(self) -> None:
        """Returns template for valid code."""
        template = get_template(ReasonCode.MISSING_PRICING)

        assert template.reason_code == ReasonCode.MISSING_PRICING
        assert "Pricing" in template.title

    def test_template_has_scaffold(self) -> None:
        """Returned template has scaffold."""
        template = get_template(ReasonCode.MISSING_DEFINITION)

        assert "[COMPANY_NAME]" in template.scaffold_template
        assert len(template.scaffold_template) > 50

    def test_template_has_examples(self) -> None:
        """Most templates have examples."""
        template = get_template(ReasonCode.MISSING_PRICING)

        assert len(template.examples) > 0


class TestGetTemplatesByCategory:
    """Tests for get_templates_by_category function."""

    def test_content_category(self) -> None:
        """Returns templates for content category."""
        templates = get_templates_by_category("content")

        # Should have templates for content-related issues
        reason_codes = [t.reason_code for t in templates]
        assert ReasonCode.MISSING_DEFINITION in reason_codes
        assert ReasonCode.MISSING_PRICING in reason_codes

    def test_technical_category(self) -> None:
        """Returns templates for technical category."""
        templates = get_templates_by_category("technical")

        reason_codes = [t.reason_code for t in templates]
        assert ReasonCode.RENDER_REQUIRED in reason_codes
        assert ReasonCode.BLOCKED_BY_ROBOTS in reason_codes
        assert len(templates) == 2

    def test_empty_for_invalid(self) -> None:
        """Returns empty for invalid category."""
        templates = get_templates_by_category("invalid")
        assert templates == []


class TestGetTemplatesByQuestionCategory:
    """Tests for get_templates_by_question_category function."""

    def test_identity_category(self) -> None:
        """Returns templates related to identity questions."""
        templates = get_templates_by_question_category(QuestionCategory.IDENTITY)

        # MISSING_DEFINITION should be related to identity
        reason_codes = [t.reason_code for t in templates]
        assert ReasonCode.MISSING_DEFINITION in reason_codes

    def test_offerings_category(self) -> None:
        """Returns templates related to offerings questions."""
        templates = get_templates_by_question_category(QuestionCategory.OFFERINGS)

        reason_codes = [t.reason_code for t in templates]
        assert ReasonCode.MISSING_PRICING in reason_codes
        assert ReasonCode.MISSING_FEATURES in reason_codes

    def test_contact_category(self) -> None:
        """Returns templates related to contact questions."""
        templates = get_templates_by_question_category(QuestionCategory.CONTACT)

        reason_codes = [t.reason_code for t in templates]
        assert ReasonCode.MISSING_CONTACT in reason_codes

    def test_trust_category(self) -> None:
        """Returns templates related to trust questions."""
        templates = get_templates_by_question_category(QuestionCategory.TRUST)

        reason_codes = [t.reason_code for t in templates]
        assert ReasonCode.MISSING_SOCIAL_PROOF in reason_codes
        assert ReasonCode.TRUST_GAP in reason_codes


class TestTemplateScaffolds:
    """Tests for specific template scaffolds."""

    def test_pricing_scaffold_has_placeholders(self) -> None:
        """Pricing scaffold has expected placeholders."""
        template = get_template(ReasonCode.MISSING_PRICING)

        assert "[PLAN_NAME" in template.scaffold_template
        assert "[PRICE" in template.scaffold_template
        assert "[FEATURE" in template.scaffold_template

    def test_contact_scaffold_has_placeholders(self) -> None:
        """Contact scaffold has expected placeholders."""
        template = get_template(ReasonCode.MISSING_CONTACT)

        assert "[EMAIL" in template.scaffold_template
        assert "[PHONE" in template.scaffold_template

    def test_definition_scaffold_has_company_name(self) -> None:
        """Definition scaffold uses company name."""
        template = get_template(ReasonCode.MISSING_DEFINITION)

        assert "[COMPANY_NAME]" in template.scaffold_template

    def test_social_proof_scaffold_has_testimonial(self) -> None:
        """Social proof scaffold has testimonial structure."""
        template = get_template(ReasonCode.MISSING_SOCIAL_PROOF)

        assert "[CUSTOMER_NAME]" in template.scaffold_template or "[TESTIMONIAL" in template.scaffold_template

    def test_robots_scaffold_has_code_example(self) -> None:
        """Robots.txt scaffold has code example."""
        template = get_template(ReasonCode.BLOCKED_BY_ROBOTS)

        assert "User-agent" in template.scaffold_template
        assert "Disallow" in template.scaffold_template
