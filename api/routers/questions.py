"""Question generation endpoints."""

from fastapi import APIRouter, Query

from api.auth import CurrentUser
from api.services.question_service import QuestionService, get_question_service
from worker.questions.universal import QuestionCategory, QuestionDifficulty

router = APIRouter(prefix="/questions", tags=["questions"])


def get_service() -> QuestionService:
    """Get question service dependency."""
    return get_question_service()


@router.get("/universal")
async def list_universal_questions(
    _user: CurrentUser,
    category: QuestionCategory | None = Query(None, description="Filter by category"),
    difficulty: QuestionDifficulty | None = Query(None, description="Filter by difficulty"),
) -> dict:
    """
    Get all 15 universal evaluation questions.

    These questions apply to any website and form the core of the
    AI sourceability evaluation.
    """
    service = get_service()

    if category:
        questions = service.get_questions_by_category(category)
    elif difficulty:
        questions = service.get_questions_by_difficulty(difficulty)
    else:
        questions = service.get_universal_questions()

    return {
        "questions": [q.to_dict() for q in questions],
        "count": len(questions),
        "filters": {
            "category": category.value if category else None,
            "difficulty": difficulty.value if difficulty else None,
        },
    }


@router.get("/universal/{question_id}")
async def get_universal_question(
    question_id: str,
    _user: CurrentUser,
) -> dict:
    """Get a specific universal question by ID."""
    service = get_service()
    question = service.get_question_by_id(question_id)

    if not question:
        return {"error": "Question not found", "question_id": question_id}

    return {"question": question.to_dict()}


@router.get("/stats")
async def get_question_stats(
    _user: CurrentUser,
) -> dict:
    """Get question statistics."""
    service = get_service()
    return {"stats": service.get_stats()}


@router.post("/generate")
async def generate_questions(
    _user: CurrentUser,
    company_name: str = Query(..., description="Company name for questions"),
    domain: str = Query(..., description="Site domain"),
    title: str | None = Query(None, description="Site title"),
    description: str | None = Query(None, description="Site description"),
    schema_types: list[str] | None = Query(None, description="Schema.org types found"),
    include_derived: bool = Query(True, description="Include site-derived questions"),
) -> dict:
    """
    Generate a complete question set for a site.

    Returns 15 universal questions plus up to 5 site-derived questions
    based on the provided metadata.
    """
    service = get_service()

    # Generate questions
    question_set = service.generate_for_site(
        company_name=company_name,
        domain=domain,
        title=title,
        description=description,
        schema_types=schema_types,
    )

    if not include_derived:
        return {
            "questions": [q.to_dict() for q in question_set.universal],
            "count": len(question_set.universal),
            "total_weight": sum(q.weight for q in question_set.universal),
        }

    return question_set.to_dict()


@router.get("/categories")
async def list_categories(
    _user: CurrentUser,
) -> dict:
    """List all question categories with descriptions."""
    return {
        "categories": [
            {
                "id": cat.value,
                "name": cat.name,
                "description": _get_category_description(cat),
            }
            for cat in QuestionCategory
        ]
    }


@router.get("/difficulties")
async def list_difficulties(
    _user: CurrentUser,
) -> dict:
    """List all question difficulty levels."""
    return {
        "difficulties": [
            {
                "id": diff.value,
                "name": diff.name,
                "description": _get_difficulty_description(diff),
            }
            for diff in QuestionDifficulty
        ]
    }


def _get_category_description(category: QuestionCategory) -> str:
    """Get description for a category."""
    descriptions = {
        QuestionCategory.IDENTITY: "Who/what is this organization",
        QuestionCategory.OFFERINGS: "Products, services, and capabilities",
        QuestionCategory.CONTACT: "How to reach and engage with them",
        QuestionCategory.TRUST: "Credibility and trust signals",
        QuestionCategory.DIFFERENTIATION: "What makes them unique",
    }
    return descriptions.get(category, "")


def _get_difficulty_description(difficulty: QuestionDifficulty) -> str:
    """Get description for a difficulty level."""
    descriptions = {
        QuestionDifficulty.EASY: "Information should be clearly stated on the site",
        QuestionDifficulty.MEDIUM: "May require some inference from available content",
        QuestionDifficulty.HARD: "Complex or multi-part, may not be fully available",
    }
    return descriptions.get(difficulty, "")
