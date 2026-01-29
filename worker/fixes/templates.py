"""Fix templates for each reason code.

Provides template-based fix suggestions with placeholders
that can be filled with site-specific content.
"""

from dataclasses import dataclass, field

from worker.fixes.reason_codes import ReasonCode
from worker.questions.universal import QuestionCategory


@dataclass
class FixTemplate:
    """Template for generating a fix."""

    reason_code: ReasonCode
    title: str
    description: str
    action_verb: str  # e.g., "Add", "Create", "Update"
    target_location: str  # Where the fix should be applied
    scaffold_template: str  # Template with [PLACEHOLDERS]
    examples: list[str] = field(default_factory=list)
    related_categories: list[QuestionCategory] = field(default_factory=list)
    priority: int = 1  # 1 = highest priority

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "reason_code": self.reason_code.value,
            "title": self.title,
            "description": self.description,
            "action_verb": self.action_verb,
            "target_location": self.target_location,
            "scaffold_template": self.scaffold_template,
            "examples": self.examples,
            "related_categories": [c.value for c in self.related_categories],
            "priority": self.priority,
        }


# Fix templates for each reason code
FIX_TEMPLATES: dict[ReasonCode, FixTemplate] = {
    ReasonCode.MISSING_DEFINITION: FixTemplate(
        reason_code=ReasonCode.MISSING_DEFINITION,
        title="Add Clear Business Definition",
        description="Add a clear, concise definition of what your business does",
        action_verb="Add",
        target_location="About page or homepage hero section",
        scaffold_template="""[COMPANY_NAME] is a [BUSINESS_TYPE] that [CORE_VALUE_PROPOSITION].

We help [TARGET_AUDIENCE] to [PRIMARY_BENEFIT] by [HOW_YOU_DO_IT].

Founded in [YEAR], we [BRIEF_HISTORY_OR_MISSION].""",
        examples=[
            "Acme Corp is a B2B SaaS company that streamlines inventory management.",
            "We help retail businesses reduce stockouts by 40% through AI-powered forecasting.",
        ],
        related_categories=[QuestionCategory.IDENTITY],
        priority=1,
    ),
    ReasonCode.MISSING_PRICING: FixTemplate(
        reason_code=ReasonCode.MISSING_PRICING,
        title="Add Pricing Information",
        description="Create a dedicated pricing page or section with clear pricing tiers",
        action_verb="Create",
        target_location="Dedicated /pricing page",
        scaffold_template="""## Pricing Plans

### [PLAN_NAME_1] - $[PRICE_1]/[PERIOD]
[PLAN_DESCRIPTION_1]
- [FEATURE_1]
- [FEATURE_2]
- [FEATURE_3]

### [PLAN_NAME_2] - $[PRICE_2]/[PERIOD]
[PLAN_DESCRIPTION_2]
- [FEATURE_1]
- [FEATURE_2]
- [FEATURE_3]
- [FEATURE_4]

[CALL_TO_ACTION] or [CONTACT_FOR_CUSTOM_PRICING]""",
        examples=[
            "Starter - $29/month: Perfect for small teams",
            "Professional - $99/month: For growing businesses",
            "Enterprise - Contact us for custom pricing",
        ],
        related_categories=[QuestionCategory.OFFERINGS],
        priority=1,
    ),
    ReasonCode.MISSING_CONTACT: FixTemplate(
        reason_code=ReasonCode.MISSING_CONTACT,
        title="Add Contact Information",
        description="Make contact information prominent and accessible",
        action_verb="Add",
        target_location="Footer, header, and dedicated /contact page",
        scaffold_template="""## Contact Us

**Email:** [EMAIL_ADDRESS]
**Phone:** [PHONE_NUMBER]
**Address:** [PHYSICAL_ADDRESS]

### Business Hours
[BUSINESS_HOURS]

### Get in Touch
[CONTACT_FORM_OR_BOOKING_LINK]""",
        examples=[
            "Email: hello@company.com",
            "Phone: (555) 123-4567",
            "Hours: Monday-Friday, 9am-5pm EST",
        ],
        related_categories=[QuestionCategory.CONTACT],
        priority=1,
    ),
    ReasonCode.MISSING_LOCATION: FixTemplate(
        reason_code=ReasonCode.MISSING_LOCATION,
        title="Add Location/Service Area",
        description="Clearly state where your business operates or serves customers",
        action_verb="Add",
        target_location="About page, footer, or dedicated locations page",
        scaffold_template="""## Our Location

**Headquarters:** [HQ_ADDRESS]

### Service Areas
We serve customers in:
- [REGION_1]
- [REGION_2]
- [REGION_3]

[REMOTE_OR_GLOBAL_NOTE]""",
        examples=[
            "Headquartered in Austin, TX",
            "Serving customers across North America",
            "Available globally via remote delivery",
        ],
        related_categories=[QuestionCategory.CONTACT, QuestionCategory.IDENTITY],
        priority=2,
    ),
    ReasonCode.MISSING_FEATURES: FixTemplate(
        reason_code=ReasonCode.MISSING_FEATURES,
        title="Add Product/Service Features",
        description="Create a detailed features page or section listing capabilities",
        action_verb="Create",
        target_location="Product page or dedicated /features page",
        scaffold_template="""## Features

### [FEATURE_CATEGORY_1]
**[FEATURE_NAME_1]:** [FEATURE_DESCRIPTION_1]
**[FEATURE_NAME_2]:** [FEATURE_DESCRIPTION_2]

### [FEATURE_CATEGORY_2]
**[FEATURE_NAME_3]:** [FEATURE_DESCRIPTION_3]
**[FEATURE_NAME_4]:** [FEATURE_DESCRIPTION_4]

### Why These Features Matter
[BENEFIT_SUMMARY]""",
        examples=[
            "Real-time Analytics: Track performance metrics as they happen",
            "Automated Reports: Generate insights without manual work",
        ],
        related_categories=[QuestionCategory.OFFERINGS],
        priority=1,
    ),
    ReasonCode.MISSING_SOCIAL_PROOF: FixTemplate(
        reason_code=ReasonCode.MISSING_SOCIAL_PROOF,
        title="Add Social Proof",
        description="Add testimonials, case studies, or customer reviews",
        action_verb="Add",
        target_location="Homepage, dedicated /testimonials or /case-studies page",
        scaffold_template="""## What Our Customers Say

### [CUSTOMER_NAME], [CUSTOMER_TITLE] at [COMPANY]
"[TESTIMONIAL_QUOTE]"

**Results:** [SPECIFIC_OUTCOME]

---

### Case Study: [CLIENT_NAME]
**Challenge:** [PROBLEM_DESCRIPTION]
**Solution:** [HOW_YOU_HELPED]
**Results:** [QUANTIFIED_OUTCOMES]""",
        examples=[
            '"Acme helped us reduce costs by 30%" - Jane Smith, CEO at TechCorp',
            "Case Study: How Company X increased revenue by 50%",
        ],
        related_categories=[QuestionCategory.TRUST],
        priority=2,
    ),
    ReasonCode.BURIED_ANSWER: FixTemplate(
        reason_code=ReasonCode.BURIED_ANSWER,
        title="Surface Key Information",
        description="Move important information to more prominent locations",
        action_verb="Move",
        target_location="Above the fold, in page headers, or navigation",
        scaffold_template="""## [TOPIC_HEADING]

[KEY_INFORMATION_SUMMARY]

[LINK_TO_DETAILS]""",
        examples=[
            "Add key stats to homepage hero section",
            "Include pricing in main navigation",
            "Add FAQ section with common questions",
        ],
        related_categories=[],
        priority=2,
    ),
    ReasonCode.FRAGMENTED_INFO: FixTemplate(
        reason_code=ReasonCode.FRAGMENTED_INFO,
        title="Consolidate Information",
        description="Create a comprehensive page that brings related information together",
        action_verb="Create",
        target_location="New dedicated page or comprehensive section",
        scaffold_template="""## Complete Guide to [TOPIC]

### Overview
[TOPIC_INTRODUCTION]

### [SUBTOPIC_1]
[CONSOLIDATED_INFO_1]

### [SUBTOPIC_2]
[CONSOLIDATED_INFO_2]

### Related Resources
- [LINK_1]
- [LINK_2]""",
        examples=[
            "Create a comprehensive 'How It Works' page",
            "Build an FAQ page covering common questions",
        ],
        related_categories=[],
        priority=3,
    ),
    ReasonCode.NO_DEDICATED_PAGE: FixTemplate(
        reason_code=ReasonCode.NO_DEDICATED_PAGE,
        title="Create Dedicated Page",
        description="Create a new page focused on this important topic",
        action_verb="Create",
        target_location="New page at /[topic-slug]",
        scaffold_template="""# [PAGE_TITLE]

## Overview
[TOPIC_INTRODUCTION]

## [SECTION_1_HEADING]
[SECTION_1_CONTENT]

## [SECTION_2_HEADING]
[SECTION_2_CONTENT]

## [CALL_TO_ACTION_HEADING]
[CTA_CONTENT]""",
        examples=[
            "Create dedicated /pricing page",
            "Create /about-us page with company story",
            "Create /services page listing all offerings",
        ],
        related_categories=[],
        priority=2,
    ),
    ReasonCode.POOR_HEADINGS: FixTemplate(
        reason_code=ReasonCode.POOR_HEADINGS,
        title="Improve Page Headings",
        description="Update headings to match common search queries",
        action_verb="Update",
        target_location="Page H1, H2, and H3 tags",
        scaffold_template="""# [QUERY_MATCHING_H1]

## [QUESTION_BASED_H2_1]
[CONTENT]

## [QUESTION_BASED_H2_2]
[CONTENT]""",
        examples=[
            'Change "Solutions" to "Enterprise Software Solutions"',
            'Use "How Much Does [Product] Cost?" instead of "Pricing"',
        ],
        related_categories=[],
        priority=3,
    ),
    ReasonCode.NOT_CITABLE: FixTemplate(
        reason_code=ReasonCode.NOT_CITABLE,
        title="Make Content Citable",
        description="Add clear attribution and quotable statements",
        action_verb="Add",
        target_location="Key content sections",
        scaffold_template="""## [TOPIC]

According to [SOURCE_OR_AUTHORITY], "[QUOTABLE_STATEMENT]."

[SUPPORTING_DETAILS]

**Key Takeaway:** [CITABLE_SUMMARY]""",
        examples=[
            "Add specific statistics with sources",
            "Include quotable mission statement",
            "Add named spokesperson quotes",
        ],
        related_categories=[QuestionCategory.TRUST],
        priority=3,
    ),
    ReasonCode.VAGUE_LANGUAGE: FixTemplate(
        reason_code=ReasonCode.VAGUE_LANGUAGE,
        title="Use Specific Language",
        description="Replace vague buzzwords with specific, concrete statements",
        action_verb="Replace",
        target_location="Throughout site copy",
        scaffold_template="""Before: "[VAGUE_STATEMENT]"
After: "[SPECIFIC_STATEMENT_WITH_DETAILS]"

Include:
- Specific numbers and metrics
- Concrete examples
- Named products or services
- Defined target audiences""",
        examples=[
            'Replace "innovative solutions" with "AI-powered inventory forecasting"',
            'Replace "industry-leading" with "rated #1 by G2 in 2024"',
        ],
        related_categories=[],
        priority=3,
    ),
    ReasonCode.OUTDATED_INFO: FixTemplate(
        reason_code=ReasonCode.OUTDATED_INFO,
        title="Update Outdated Information",
        description="Review and update stale content with current information",
        action_verb="Update",
        target_location="Identified outdated pages/sections",
        scaffold_template="""## [TOPIC] (Updated [CURRENT_DATE])

[UPDATED_CONTENT]

Last reviewed: [DATE]""",
        examples=[
            "Update copyright year in footer",
            "Refresh team page with current employees",
            "Update product features to reflect latest version",
        ],
        related_categories=[],
        priority=2,
    ),
    ReasonCode.INCONSISTENT: FixTemplate(
        reason_code=ReasonCode.INCONSISTENT,
        title="Resolve Inconsistencies",
        description="Identify and fix conflicting information across pages",
        action_verb="Fix",
        target_location="Multiple pages with conflicting info",
        scaffold_template="""## Content Audit

**Issue:** [DESCRIPTION_OF_INCONSISTENCY]

**Pages affected:**
- [PAGE_1_URL]
- [PAGE_2_URL]

**Correct information:** [ACCURATE_CONTENT]

**Action:** Update all pages to reflect accurate information.""",
        examples=[
            "Ensure pricing is consistent across all pages",
            "Align company founding date across About and Press pages",
        ],
        related_categories=[],
        priority=1,
    ),
    ReasonCode.TRUST_GAP: FixTemplate(
        reason_code=ReasonCode.TRUST_GAP,
        title="Add Trust Signals",
        description="Add credibility indicators throughout the site",
        action_verb="Add",
        target_location="Homepage, about page, and footer",
        scaffold_template="""## Trust Indicators

### Certifications & Awards
- [CERTIFICATION_1]
- [AWARD_1]

### Client Logos
[NOTABLE_CLIENT_LOGOS]

### Security & Compliance
- [SECURITY_CERTIFICATION]
- [COMPLIANCE_BADGE]

### Media Mentions
As featured in: [MEDIA_OUTLETS]""",
        examples=[
            "Add 'As seen in Forbes, TechCrunch' section",
            "Display security badges (SOC 2, GDPR compliant)",
            "Show client logos with permission",
        ],
        related_categories=[QuestionCategory.TRUST],
        priority=2,
    ),
    ReasonCode.NO_AUTHORITY: FixTemplate(
        reason_code=ReasonCode.NO_AUTHORITY,
        title="Establish Authority",
        description="Add content that demonstrates expertise in your field",
        action_verb="Add",
        target_location="About page, team page, or blog",
        scaffold_template="""## Our Expertise

### Leadership Team
**[NAME], [TITLE]**
[CREDENTIALS_AND_EXPERIENCE]

### Industry Recognition
- [SPEAKING_ENGAGEMENT]
- [PUBLICATION]
- [AWARD]

### Thought Leadership
[LINK_TO_BLOG_OR_RESOURCES]""",
        examples=[
            "Add team credentials and experience",
            "Include speaking engagements and publications",
            "Create thought leadership content",
        ],
        related_categories=[QuestionCategory.TRUST, QuestionCategory.IDENTITY],
        priority=3,
    ),
    ReasonCode.UNVERIFIED_CLAIMS: FixTemplate(
        reason_code=ReasonCode.UNVERIFIED_CLAIMS,
        title="Add Evidence for Claims",
        description="Back up marketing claims with data, case studies, or third-party verification",
        action_verb="Add",
        target_location="Marketing pages with bold claims",
        scaffold_template="""## [CLAIM]

**Evidence:**
- [DATA_POINT_1] (Source: [SOURCE])
- [CASE_STUDY_REFERENCE]
- [THIRD_PARTY_VERIFICATION]

[LINK_TO_FULL_CASE_STUDY]""",
        examples=[
            'Add source for "95% customer satisfaction"',
            "Link claims to case studies with real results",
            "Include third-party reviews or audits",
        ],
        related_categories=[QuestionCategory.TRUST],
        priority=2,
    ),
    ReasonCode.RENDER_REQUIRED: FixTemplate(
        reason_code=ReasonCode.RENDER_REQUIRED,
        title="Enable Static Content",
        description="Ensure critical content is available without JavaScript",
        action_verb="Implement",
        target_location="Server-side rendering or static HTML",
        scaffold_template="""## Technical Fix

**Issue:** Content requires JavaScript to render

**Solutions:**
1. Implement server-side rendering (SSR)
2. Use static site generation (SSG) for key pages
3. Add meaningful content to initial HTML
4. Use progressive enhancement

**Priority pages:**
- Homepage
- About page
- Product/service pages
- Contact page""",
        examples=[
            "Add SSR for Next.js pages",
            "Pre-render critical content paths",
            "Include initial content in HTML before JS hydration",
        ],
        related_categories=[],
        priority=1,
    ),
    ReasonCode.BLOCKED_BY_ROBOTS: FixTemplate(
        reason_code=ReasonCode.BLOCKED_BY_ROBOTS,
        title="Update Robots.txt",
        description="Allow crawlers to access important pages",
        action_verb="Update",
        target_location="/robots.txt file",
        scaffold_template="""## robots.txt Update

**Current (blocking):**
```
User-agent: *
Disallow: /[BLOCKED_PATH]
```

**Recommended:**
```
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /[IMPORTANT_PATH]/
```

Ensure important pages are NOT blocked.""",
        examples=[
            "Allow /pricing/ to be crawled",
            "Ensure /about/ is accessible",
            "Only block truly private pages",
        ],
        related_categories=[],
        priority=1,
    ),
}


def get_template(reason_code: ReasonCode) -> FixTemplate:
    """Get the fix template for a reason code."""
    return FIX_TEMPLATES[reason_code]


def get_templates_by_category(category: str) -> list[FixTemplate]:
    """Get all templates for a reason code category."""
    from worker.fixes.reason_codes import get_codes_by_category

    codes = get_codes_by_category(category)
    return [FIX_TEMPLATES[code] for code in codes]


def get_templates_by_question_category(
    question_category: QuestionCategory,
) -> list[FixTemplate]:
    """Get templates related to a question category."""
    return [
        template
        for template in FIX_TEMPLATES.values()
        if question_category in template.related_categories
    ]
