"""Schema.org structured data extraction and analysis.

Extracts and validates JSON-LD and microdata schema markup,
which is critical for AI answer engines to understand content.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


# Schema types that are particularly valuable for AI citation
VALUABLE_SCHEMA_TYPES = {
    "FAQPage": {"weight": 4, "citation_lift": 0.35},  # 35-40% citation lift
    "Article": {"weight": 3, "citation_lift": 0.15},
    "NewsArticle": {"weight": 3, "citation_lift": 0.15},
    "BlogPosting": {"weight": 2, "citation_lift": 0.10},
    "HowTo": {"weight": 2, "citation_lift": 0.20},
    "Recipe": {"weight": 2, "citation_lift": 0.15},
    "Product": {"weight": 2, "citation_lift": 0.10},
    "Organization": {"weight": 2, "citation_lift": 0.05},
    "LocalBusiness": {"weight": 2, "citation_lift": 0.05},
    "Person": {"weight": 1, "citation_lift": 0.05},
    "WebPage": {"weight": 1, "citation_lift": 0.02},
    "BreadcrumbList": {"weight": 1, "citation_lift": 0.02},
}

# Required fields for key schema types
REQUIRED_FIELDS = {
    "Article": ["headline", "author", "datePublished"],
    "NewsArticle": ["headline", "author", "datePublished", "dateModified"],
    "BlogPosting": ["headline", "author", "datePublished"],
    "FAQPage": ["mainEntity"],
    "HowTo": ["name", "step"],
    "Product": ["name", "description"],
    "Organization": ["name", "url"],
    "Person": ["name"],
}

# Recommended fields for better AI understanding
RECOMMENDED_FIELDS = {
    "Article": ["dateModified", "description", "image", "publisher"],
    "NewsArticle": ["description", "image", "publisher"],
    "BlogPosting": ["dateModified", "description", "image"],
    "FAQPage": [],  # mainEntity covers it
    "HowTo": ["description", "totalTime", "image"],
    "Product": ["image", "offers", "brand", "review"],
    "Organization": ["logo", "description", "contactPoint"],
}


@dataclass
class SchemaValidationError:
    """A single schema validation error."""

    schema_type: str
    error_type: str  # missing_required, invalid_format, empty_value
    field: str
    message: str

    def to_dict(self) -> dict:
        return {
            "schema_type": self.schema_type,
            "error_type": self.error_type,
            "field": self.field,
            "message": self.message,
        }


@dataclass
class FAQItem:
    """A single FAQ question-answer pair from schema."""

    question: str
    answer: str
    is_valid: bool = True

    def to_dict(self) -> dict:
        return {
            "question": self.question[:200],
            "answer": self.answer[:500],
            "is_valid": self.is_valid,
        }


@dataclass
class SchemaInstance:
    """A single schema.org instance found on the page."""

    schema_type: str
    source: str  # json-ld, microdata, rdfa
    data: dict
    is_valid: bool = True
    errors: list[SchemaValidationError] = field(default_factory=list)
    completeness: float = 0.0  # 0-100

    # Key extracted fields
    name: str | None = None
    description: str | None = None
    author: str | None = None
    date_published: str | None = None
    date_modified: str | None = None
    image: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": self.schema_type,
            "source": self.source,
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "completeness": round(self.completeness, 2),
            "name": self.name,
            "description": self.description[:200] if self.description else None,
            "author": self.author,
            "date_published": self.date_published,
            "date_modified": self.date_modified,
        }


@dataclass
class SchemaAnalysis:
    """Complete schema analysis result for a page."""

    url: str

    # Schema detection
    has_json_ld: bool = False
    has_microdata: bool = False
    has_rdfa: bool = False
    total_schemas: int = 0

    # Schema instances found
    schemas: list[SchemaInstance] = field(default_factory=list)

    # Key schema types
    has_faq_page: bool = False
    has_article: bool = False
    has_how_to: bool = False
    has_organization: bool = False
    has_product: bool = False
    has_person: bool = False
    has_breadcrumb: bool = False

    # FAQ analysis
    faq_items: list[FAQItem] = field(default_factory=list)
    faq_count: int = 0

    # Freshness
    has_date_published: bool = False
    has_date_modified: bool = False
    date_modified: str | None = None
    days_since_modified: int | None = None
    freshness_level: str = "unknown"  # fresh, recent, stale, very_stale

    # Author/Authority
    has_author: bool = False
    author_name: str | None = None
    has_author_credentials: bool = False

    # Validation
    validation_errors: list[SchemaValidationError] = field(default_factory=list)
    error_count: int = 0

    # Overall metrics
    schema_types_found: list[str] = field(default_factory=list)
    avg_completeness: float = 0.0
    score: float = 0.0  # 0-100

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "detection": {
                "has_json_ld": self.has_json_ld,
                "has_microdata": self.has_microdata,
                "has_rdfa": self.has_rdfa,
                "total_schemas": self.total_schemas,
            },
            "types": {
                "has_faq_page": self.has_faq_page,
                "has_article": self.has_article,
                "has_how_to": self.has_how_to,
                "has_organization": self.has_organization,
                "has_product": self.has_product,
                "has_person": self.has_person,
                "has_breadcrumb": self.has_breadcrumb,
                "all_types": self.schema_types_found,
            },
            "faq": {
                "count": self.faq_count,
                "items": [f.to_dict() for f in self.faq_items[:5]],
            },
            "freshness": {
                "has_date_published": self.has_date_published,
                "has_date_modified": self.has_date_modified,
                "date_modified": self.date_modified,
                "days_since_modified": self.days_since_modified,
                "level": self.freshness_level,
            },
            "author": {
                "has_author": self.has_author,
                "name": self.author_name,
                "has_credentials": self.has_author_credentials,
            },
            "validation": {
                "error_count": self.error_count,
                "errors": [e.to_dict() for e in self.validation_errors[:10]],
            },
            "metrics": {
                "avg_completeness": round(self.avg_completeness, 2),
                "score": round(self.score, 2),
            },
            "schemas": [s.to_dict() for s in self.schemas[:10]],
        }


class SchemaAnalyzer:
    """Analyzes schema.org structured data for AI extractability."""

    def __init__(
        self,
        freshness_thresholds: dict | None = None,
    ):
        self.freshness_thresholds = freshness_thresholds or {
            "fresh": 30,  # < 30 days
            "recent": 90,  # < 90 days
            "stale": 180,  # < 180 days
            # > 180 days = very_stale
        }

    def analyze(self, html: str, url: str) -> SchemaAnalysis:
        """
        Analyze schema.org markup in HTML.

        Args:
            html: HTML content to analyze
            url: Page URL

        Returns:
            SchemaAnalysis with complete schema evaluation
        """
        soup = BeautifulSoup(html, "html.parser")
        result = SchemaAnalysis(url=url)

        # Extract JSON-LD schemas
        json_ld_schemas = self._extract_json_ld(soup)
        if json_ld_schemas:
            result.has_json_ld = True
            result.schemas.extend(json_ld_schemas)

        # Extract Microdata schemas
        microdata_schemas = self._extract_microdata(soup)
        if microdata_schemas:
            result.has_microdata = True
            result.schemas.extend(microdata_schemas)

        result.total_schemas = len(result.schemas)

        # Analyze schema types
        for schema in result.schemas:
            self._categorize_schema(schema, result)

        # Extract FAQ items
        if result.has_faq_page:
            result.faq_items = self._extract_faq_items(result.schemas)
            result.faq_count = len(result.faq_items)

        # Analyze freshness
        self._analyze_freshness(result)

        # Analyze author
        self._analyze_author(result)

        # Validate schemas
        self._validate_schemas(result)

        # Calculate score
        result.schema_types_found = list({s.schema_type for s in result.schemas})
        if result.schemas:
            result.avg_completeness = sum(s.completeness for s in result.schemas) / len(
                result.schemas
            )
        result.score = self._calculate_score(result)

        logger.debug(
            "schema_analysis_complete",
            url=url,
            total_schemas=result.total_schemas,
            types=result.schema_types_found,
            score=result.score,
        )

        return result

    def _extract_json_ld(self, soup: BeautifulSoup) -> list[SchemaInstance]:
        """Extract JSON-LD schema instances."""
        schemas = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                content = script.string
                if not content:
                    continue

                data = json.loads(content)

                # Handle @graph arrays
                if isinstance(data, dict) and "@graph" in data:
                    for item in data["@graph"]:
                        if isinstance(item, dict) and "@type" in item:
                            schema = self._create_schema_instance(item, "json-ld")
                            if schema:
                                schemas.append(schema)
                elif isinstance(data, dict) and "@type" in data:
                    schema = self._create_schema_instance(data, "json-ld")
                    if schema:
                        schemas.append(schema)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "@type" in item:
                            schema = self._create_schema_instance(item, "json-ld")
                            if schema:
                                schemas.append(schema)

            except (json.JSONDecodeError, TypeError) as e:
                logger.debug("json_ld_parse_error", error=str(e))

        return schemas

    def _extract_microdata(self, soup: BeautifulSoup) -> list[SchemaInstance]:
        """Extract Microdata schema instances."""
        schemas = []

        for element in soup.find_all(attrs={"itemtype": True}):
            itemtype = element.get("itemtype", "")
            if "schema.org" not in itemtype:
                continue

            # Extract type from URL
            type_match = re.search(r"schema\.org/(\w+)", itemtype)
            if not type_match:
                continue

            schema_type = type_match.group(1)

            # Extract properties
            data = {"@type": schema_type}
            for prop in element.find_all(attrs={"itemprop": True}):
                prop_name = prop.get("itemprop")
                prop_value = prop.get("content") or prop.get_text(strip=True)
                if prop_name and prop_value:
                    data[prop_name] = prop_value

            schema = self._create_schema_instance(data, "microdata")
            if schema:
                schemas.append(schema)

        return schemas

    def _create_schema_instance(self, data: dict, source: str) -> SchemaInstance | None:
        """Create a SchemaInstance from raw data."""
        schema_type = data.get("@type")
        if not schema_type:
            return None

        # Handle array types
        if isinstance(schema_type, list):
            schema_type = schema_type[0]

        schema = SchemaInstance(
            schema_type=schema_type,
            source=source,
            data=data,
        )

        # Extract common fields
        schema.name = self._extract_field(data, ["name", "headline", "title"])
        schema.description = self._extract_field(data, ["description", "abstract"])
        schema.date_published = self._extract_field(data, ["datePublished", "dateCreated"])
        schema.date_modified = self._extract_field(data, ["dateModified", "lastModified"])
        schema.image = self._extract_image(data)

        # Extract author
        author_data = data.get("author")
        if author_data:
            if isinstance(author_data, dict):
                schema.author = author_data.get("name")
            elif isinstance(author_data, str):
                schema.author = author_data
            elif isinstance(author_data, list) and author_data:
                first = author_data[0]
                schema.author = first.get("name") if isinstance(first, dict) else str(first)

        # Calculate completeness
        schema.completeness = self._calculate_completeness(schema_type, data)

        return schema

    def _extract_field(self, data: dict, field_names: list[str]) -> str | None:
        """Extract first matching field from data."""
        for name in field_names:
            value = data.get(name)
            if value:
                if isinstance(value, str):
                    return value
                elif isinstance(value, dict):
                    return value.get("@value") or value.get("name")
        return None

    def _extract_image(self, data: dict) -> str | None:
        """Extract image URL from schema data."""
        image = data.get("image")
        if not image:
            return None

        if isinstance(image, str):
            return image
        elif isinstance(image, dict):
            return image.get("url") or image.get("@id")
        elif isinstance(image, list) and image:
            first = image[0]
            if isinstance(first, str):
                return first
            elif isinstance(first, dict):
                return first.get("url")
        return None

    def _calculate_completeness(self, schema_type: str, data: dict) -> float:
        """Calculate schema completeness percentage."""
        required = REQUIRED_FIELDS.get(schema_type, [])
        recommended = RECOMMENDED_FIELDS.get(schema_type, [])

        if not required and not recommended:
            # Unknown type - basic completeness check
            return 50.0 if len(data) > 2 else 25.0

        required_present = sum(1 for f in required if self._has_field(data, f))
        recommended_present = sum(1 for f in recommended if self._has_field(data, f))

        required_weight = 0.7
        recommended_weight = 0.3

        required_score = (required_present / len(required)) if required else 1.0
        recommended_score = (recommended_present / len(recommended)) if recommended else 0.5

        return (required_score * required_weight + recommended_score * recommended_weight) * 100

    def _has_field(self, data: dict, field: str) -> bool:
        """Check if field exists and has value."""
        value = data.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return not (isinstance(value, list) and not value)

    def _categorize_schema(self, schema: SchemaInstance, result: SchemaAnalysis) -> None:
        """Categorize schema by type and update result."""
        t = schema.schema_type

        if t == "FAQPage":
            result.has_faq_page = True
        elif t in ["Article", "NewsArticle", "BlogPosting"]:
            result.has_article = True
        elif t == "HowTo":
            result.has_how_to = True
        elif t in ["Organization", "LocalBusiness"]:
            result.has_organization = True
        elif t == "Product":
            result.has_product = True
        elif t == "Person":
            result.has_person = True
        elif t == "BreadcrumbList":
            result.has_breadcrumb = True

    def _extract_faq_items(self, schemas: list[SchemaInstance]) -> list[FAQItem]:
        """Extract FAQ question-answer pairs from FAQPage schemas."""
        faq_items = []

        for schema in schemas:
            if schema.schema_type != "FAQPage":
                continue

            main_entity = schema.data.get("mainEntity", [])
            if isinstance(main_entity, dict):
                main_entity = [main_entity]

            for qa in main_entity:
                if not isinstance(qa, dict):
                    continue

                question = qa.get("name", "")
                accepted_answer = qa.get("acceptedAnswer", {})

                if isinstance(accepted_answer, dict):
                    answer = accepted_answer.get("text", "")
                else:
                    answer = str(accepted_answer)

                if question:
                    faq_items.append(
                        FAQItem(
                            question=question,
                            answer=answer,
                            is_valid=bool(question and answer),
                        )
                    )

        return faq_items

    def _analyze_freshness(self, result: SchemaAnalysis) -> None:
        """Analyze content freshness from schema dates."""
        for schema in result.schemas:
            if schema.date_published:
                result.has_date_published = True

            if schema.date_modified:
                result.has_date_modified = True
                result.date_modified = schema.date_modified

                # Calculate days since modified
                try:
                    # Try various date formats
                    date_str = schema.date_modified
                    modified_date = None

                    for fmt in [
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d",
                    ]:
                        try:
                            # Remove timezone info for simpler parsing
                            clean_date = date_str.split("+")[0].split("Z")[0]
                            modified_date = datetime.strptime(
                                clean_date[:19], fmt[: min(len(fmt), 19)]
                            )
                            break
                        except ValueError:
                            continue

                    if modified_date:
                        delta = datetime.now() - modified_date
                        result.days_since_modified = delta.days

                        # Determine freshness level
                        if delta.days < self.freshness_thresholds["fresh"]:
                            result.freshness_level = "fresh"
                        elif delta.days < self.freshness_thresholds["recent"]:
                            result.freshness_level = "recent"
                        elif delta.days < self.freshness_thresholds["stale"]:
                            result.freshness_level = "stale"
                        else:
                            result.freshness_level = "very_stale"

                except Exception:
                    pass

    def _analyze_author(self, result: SchemaAnalysis) -> None:
        """Analyze author information from schemas."""
        for schema in result.schemas:
            if schema.author:
                result.has_author = True
                result.author_name = schema.author

                # Check for author credentials in the data
                author_data = schema.data.get("author", {})
                if isinstance(author_data, dict) and (
                    author_data.get("jobTitle") or author_data.get("description")
                ):
                    result.has_author_credentials = True
                break

    def _validate_schemas(self, result: SchemaAnalysis) -> None:
        """Validate schema instances for errors."""
        for schema in result.schemas:
            errors = self._validate_schema_instance(schema)
            schema.errors = errors
            schema.is_valid = len(errors) == 0
            result.validation_errors.extend(errors)

        result.error_count = len(result.validation_errors)

    def _validate_schema_instance(self, schema: SchemaInstance) -> list[SchemaValidationError]:
        """Validate a single schema instance."""
        errors = []
        schema_type = schema.schema_type
        data = schema.data

        # Check required fields
        required = REQUIRED_FIELDS.get(schema_type, [])
        for req_field in required:
            if not self._has_field(data, req_field):
                errors.append(
                    SchemaValidationError(
                        schema_type=schema_type,
                        error_type="missing_required",
                        field=req_field,
                        message=f"{schema_type} missing required field: {req_field}",
                    )
                )

        # Check for empty values in key fields
        for key_field in ["name", "headline", "description"]:
            value = data.get(key_field)
            if value is not None and isinstance(value, str) and not value.strip():
                errors.append(
                    SchemaValidationError(
                        schema_type=schema_type,
                        error_type="empty_value",
                        field=key_field,
                        message=f"{schema_type} has empty {key_field}",
                    )
                )

        return errors

    def _calculate_score(self, result: SchemaAnalysis) -> float:
        """Calculate overall schema richness score."""
        score = 0.0

        # Base score for having any schema
        if result.total_schemas > 0:
            score += 10

        # Score for valuable schema types
        for schema in result.schemas:
            type_info = VALUABLE_SCHEMA_TYPES.get(schema.schema_type)
            if type_info:
                # Weight by type importance and completeness
                type_score = type_info["weight"] * (schema.completeness / 100) * 10
                score += min(15, type_score)

        # Bonus for FAQPage (most valuable)
        if result.has_faq_page:
            score += 15
            # Extra bonus for multiple FAQ items
            if result.faq_count >= 3:
                score += 5
            if result.faq_count >= 5:
                score += 5

        # Bonus for Article with author
        if result.has_article and result.has_author:
            score += 10

        # Bonus for freshness
        if result.has_date_modified:
            score += 5
            if result.freshness_level == "fresh":
                score += 5
            elif result.freshness_level == "recent":
                score += 3

        # Bonus for Organization (entity recognition)
        if result.has_organization:
            score += 5

        # Bonus for HowTo
        if result.has_how_to:
            score += 5

        # Penalty for validation errors
        if result.error_count > 0:
            penalty = min(20, result.error_count * 3)
            score -= penalty

        return max(0, min(100, score))


def analyze_schema(html: str, url: str) -> SchemaAnalysis:
    """
    Convenience function to analyze schema.org markup.

    Args:
        html: HTML content to analyze
        url: Page URL

    Returns:
        SchemaAnalysis with complete schema evaluation
    """
    analyzer = SchemaAnalyzer()
    return analyzer.analyze(html, url)
