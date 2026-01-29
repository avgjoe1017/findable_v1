"""Questions package for AI sourceability evaluation."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.questions.universal import UNIVERSAL_QUESTIONS, get_universal_questions
# from worker.questions.generator import QuestionGenerator
# from worker.questions.derived import DerivedQuestionGenerator

__all__ = [
    # Universal questions
    "UNIVERSAL_QUESTIONS",
    "UniversalQuestion",
    "QuestionCategory",
    "get_universal_questions",
    "get_questions_by_category",
    # Generator
    "QuestionGenerator",
    "GeneratorConfig",
    "GeneratedQuestion",
    "SiteContext",
    # Derived questions
    "DerivedQuestionGenerator",
    "DerivedConfig",
    "ContentAnalysis",
    "derive_questions",
]
