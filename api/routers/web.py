"""Web routes for HTML pages using Jinja2 templates.

Provides server-rendered UI for the Findable Score Analyzer MVP.
"""

import uuid
from datetime import UTC
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from api.auth import get_current_user_optional
from api.config import get_settings
from api.database import async_session_maker, get_db
from api.models.user import User
from api.services import run_service, site_service

logger = structlog.get_logger()

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["web"])


# Session cookie name for simple auth
SESSION_COOKIE = "findable_session"

# Dev user ID (consistent UUID for development)
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_or_create_dev_user() -> User:
    """Get or create the dev user in the database."""
    import structlog
    from sqlalchemy import select, text

    log = structlog.get_logger()

    # Pre-computed bcrypt hash for "devpassword123"
    DEV_PASSWORD_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.DQwOZwTTaZiGGi"

    try:
        async with async_session_maker() as db:
            result = await db.execute(select(User).where(User.id == DEV_USER_ID))
            user = result.scalar_one_or_none()

            if not user:
                log.info("Creating dev user via raw SQL", user_id=str(DEV_USER_ID))
                # Use raw SQL to bypass any ORM/passlib issues
                await db.execute(
                    text(
                        """
                        INSERT INTO users (id, email, hashed_password, is_active, is_superuser, is_verified, plan)
                        VALUES (:id, :email, :hashed_password, :is_active, :is_superuser, :is_verified, :plan)
                    """
                    ),
                    {
                        "id": DEV_USER_ID,
                        "email": "dev@findable.local",
                        "hashed_password": DEV_PASSWORD_HASH,
                        "is_active": True,
                        "is_superuser": True,
                        "is_verified": True,
                        "plan": "agency",
                    },
                )
                await db.commit()
                log.info("Dev user created successfully")

                # Now fetch the user
                result = await db.execute(select(User).where(User.id == DEV_USER_ID))
                user = result.scalar_one()

            result_user: User = user
            return result_user
    except Exception as e:
        log.error("Error in get_or_create_dev_user", error=str(e))
        raise


async def get_optional_user(request: Request) -> User:
    """Get current user if authenticated, or dev user in development mode."""
    settings = get_settings()

    # In development mode, always return dev user (bypass auth)
    if settings.env == "development":
        return await get_or_create_dev_user()

    try:
        user = await get_current_user_optional(request)
        if user:
            return user
        # If no user, return dev user as fallback
        return await get_or_create_dev_user()
    except Exception:
        # On error, return dev user as fallback
        return await get_or_create_dev_user()


def get_grade_class(grade: str) -> str:
    """Return CSS class for grade letter."""
    if not grade:
        return "grade-c"
    letter = grade[0].upper()
    grade_map = {"A": "a", "B": "b", "C": "c", "D": "d", "F": "f"}
    return f"grade-{grade_map.get(letter, 'c')}"


def get_score_class(score: float | None) -> str:
    """Return CSS class for score level."""
    if score is None:
        return "score-fair"
    if score >= 80:
        return "score-excellent"
    if score >= 60:
        return "score-good"
    if score >= 40:
        return "score-fair"
    return "score-poor"


def format_trend(current: float | None, previous: float | None) -> str:
    """Format score trend as +/- string."""
    if current is None or previous is None:
        return "—"
    diff = current - previous
    if diff > 0:
        return f"+{int(diff)}"
    if diff < 0:
        return str(int(diff))
    return "0"


# Register template filters
templates.env.filters["grade_class"] = get_grade_class
templates.env.filters["score_class"] = get_score_class
templates.env.filters["format_trend"] = format_trend


@router.get("/", response_class=HTMLResponse, name="dashboard")
async def dashboard(
    request: Request,
    db: Any = Depends(get_db),
) -> HTMLResponse:
    """Render the main dashboard showing all sites."""
    user = await get_optional_user(request)

    # Default demo data for unauthenticated users
    sites = []
    total_sites = 0
    avg_score = 0
    open_fixes = 0

    if user:
        # Get real data for authenticated users
        site_list, total = await site_service.list_sites(db, user.id, skip=0, limit=50)
        total_sites = total

        # Build sites data with latest scores
        scores = []
        for site in site_list:
            latest_report = await site_service.get_latest_report(db, site.id)
            previous_report = await site_service.get_previous_report(db, site.id)
            score = latest_report.score_typical if latest_report else None
            prev_score = previous_report.score_typical if previous_report else None
            grade = _score_to_grade(score) if score else None

            # Calculate trend from previous run
            trend = format_trend(score, prev_score) if score else "—"

            # Count open fixes from report data
            if latest_report and latest_report.data:
                fix_section = latest_report.data.get("fixes", {})
                fix_list = fix_section.get("fixes", [])
                open_fixes += len([f for f in fix_list if f.get("status") != "resolved"])

            if score:
                scores.append(score)

            sites.append(
                {
                    "id": str(site.id),
                    "name": site.name,
                    "domain": site.domain,
                    "score": score or 0,
                    "grade": grade or "—",
                    "trend": trend,
                    "last_run": _format_last_run(latest_report),
                    "status": "completed" if latest_report else "pending",
                }
            )

        avg_score = int(sum(scores) / len(scores)) if scores else 0

    return templates.TemplateResponse(
        request=request,
        name="sites/dashboard.html",
        context={
            "sites": sites,
            "total_sites": total_sites,
            "avg_score": avg_score,
            "monthly_change": 0,
            "open_fixes": open_fixes,
        },
    )


@router.get("/sites/new", response_class=HTMLResponse, name="new_site")
async def new_site(request: Request) -> HTMLResponse:
    """Render the site creation form."""
    return templates.TemplateResponse(
        request=request,
        name="sites/new.html",
        context={
            "business_models": [
                ("b2b_saas", "B2B SaaS"),
                ("b2c_saas", "B2C SaaS"),
                ("ecommerce", "E-Commerce"),
                ("marketplace", "Marketplace"),
                ("agency", "Agency / Services"),
                ("media", "Media / Content"),
                ("other", "Other"),
            ],
        },
    )


@router.post("/sites/new", response_model=None, name="create_site")
async def create_site_form(
    request: Request,
    db: Any = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Handle site creation form submission."""
    user = await get_optional_user(request)
    if not user:
        # Redirect to login for unauthenticated users
        return RedirectResponse(url="/login?next=/sites/new", status_code=303)

    form = await request.form()
    domain = str(form.get("domain", "")).strip()
    name = str(form.get("name", "")).strip()
    business_model = str(form.get("business_model", "other")).strip()
    competitors_raw = str(form.get("competitors", "")).strip()

    # Parse competitors (one per line)
    competitors_list: list[dict[str, str]] = []
    for line in competitors_raw.split("\n"):
        comp = line.strip()
        if comp:
            competitors_list.append({"domain": comp})

    errors = []
    if not domain:
        errors.append("Domain is required")
    if not name:
        errors.append("Company name is required")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="sites/new.html",
            context={
                "errors": errors,
                "domain": domain,
                "name": name,
                "business_model": business_model,
                "competitors": competitors_raw,
                "business_models": [
                    ("b2b_saas", "B2B SaaS"),
                    ("b2c_saas", "B2C SaaS"),
                    ("ecommerce", "E-Commerce"),
                    ("marketplace", "Marketplace"),
                    ("agency", "Agency / Services"),
                    ("media", "Media / Content"),
                    ("other", "Other"),
                ],
            },
            status_code=400,
        )

    try:
        from api.schemas.site import CompetitorCreate, SiteCreate

        # Convert dict competitors to CompetitorCreate objects
        competitors = [CompetitorCreate(domain=c["domain"], name=None) for c in competitors_list]

        site_in = SiteCreate(
            domain=domain,
            name=name,
            business_model=business_model,
            competitors=competitors,
        )
        site = await site_service.create_site(db, user, site_in)
        return RedirectResponse(url=f"/sites/{site.id}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="sites/new.html",
            context={
                "errors": [str(e)],
                "domain": domain,
                "name": name,
                "business_model": business_model,
                "competitors": competitors_raw,
                "business_models": [
                    ("b2b_saas", "B2B SaaS"),
                    ("b2c_saas", "B2C SaaS"),
                    ("ecommerce", "E-Commerce"),
                    ("marketplace", "Marketplace"),
                    ("agency", "Agency / Services"),
                    ("media", "Media / Content"),
                    ("other", "Other"),
                ],
            },
            status_code=400,
        )


@router.get("/sites/{site_id}", response_model=None, name="site_detail")
async def site_detail(
    request: Request,
    site_id: uuid.UUID,
    db: Any = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Render the site detail page with run progress."""
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next=/sites/{site_id}", status_code=303)

    try:
        site = await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Site not found")

    # Get runs for this site
    runs, total_runs = await run_service.list_runs(db, site_id, skip=0, limit=10)

    # Get latest report
    latest_report = await site_service.get_latest_report(db, site_id)

    # Check for active run
    active_run = await run_service.get_active_run(db, site_id)

    # Format runs for template
    run_list = []
    for run in runs:
        # Extract config values safely
        config = run.config or {}
        include_observation = config.get("include_observation", True)
        include_benchmark = config.get("include_benchmark", True)

        run_list.append(
            {
                "id": str(run.id),
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "include_observation": include_observation,
                "include_benchmark": include_benchmark,
                "error_message": run.error_message,
                "has_report": run.report_id is not None,
                "report_id": str(run.report_id) if run.report_id else None,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="sites/detail.html",
        context={
            "site": {
                "id": str(site.id),
                "name": site.name,
                "domain": site.domain,
                "business_model": site.business_model,
                "monitoring_enabled": site.monitoring_enabled,
                "competitors": [{"name": c.name, "domain": c.domain} for c in site.competitors],
            },
            "runs": run_list,
            "total_runs": total_runs,
            "active_run": (
                {
                    "id": str(active_run.id),
                    "status": active_run.status,
                    "progress": active_run.progress or 0,
                }
                if active_run
                else None
            ),
            "latest_score": latest_report.score_typical if latest_report else None,
            "latest_grade": _score_to_grade(latest_report.score_typical) if latest_report else None,
            "latest_report_id": str(latest_report.id) if latest_report else None,
        },
    )


@router.post("/sites/{site_id}/runs", response_model=None, name="start_run")
async def start_run(
    request: Request,
    site_id: uuid.UUID,
    db: Any = Depends(get_db),
) -> RedirectResponse:
    """Start a new audit run for a site."""
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next=/sites/{site_id}", status_code=303)

    try:
        site = await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Site not found")

    # Check for existing active run
    active_run = await run_service.get_active_run(db, site_id)
    if active_run:
        # Return to detail page with error
        return RedirectResponse(
            url=f"/sites/{site_id}?error=run_active",
            status_code=303,
        )

    # Get form data
    form = await request.form()
    include_observation = form.get("include_observation") == "on"
    include_benchmark = form.get("include_benchmark") == "on"

    try:
        from api.schemas.run import RunConfig, RunCreate
        from api.services import job_service

        run_in = RunCreate(
            config=RunConfig(
                include_observation=include_observation,
                include_benchmark=include_benchmark,
            )
        )
        run = await run_service.create_run(db, site, run_in)
        logger.info("run_created", run_id=str(run.id), site_id=str(site_id))

        # Enqueue background job
        try:
            job_id = job_service.enqueue_audit(run, site)
            logger.info("job_enqueued", job_id=job_id, run_id=str(run.id))
            run.job_id = job_id
            await db.flush()
        except Exception as enqueue_error:
            logger.error("job_enqueue_failed", error=str(enqueue_error), run_id=str(run.id))
            # Mark run as failed
            run.status = "failed"
            run.error_message = f"Failed to enqueue job: {str(enqueue_error)}"
            await db.flush()
            raise

        return RedirectResponse(url=f"/sites/{site_id}", status_code=303)
    except Exception as e:
        logger.error("start_run_failed", error=str(e), site_id=str(site_id))
        return RedirectResponse(
            url=f"/sites/{site_id}?error={str(e)}",
            status_code=303,
        )


@router.get("/reports/{report_id}", response_model=None, name="view_report")
async def view_report(
    request: Request,
    report_id: uuid.UUID,
    db: Any = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Render the full score report."""
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next=/reports/{report_id}", status_code=303)

    try:
        report = await run_service.get_report(db, report_id, user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="Report not found")

    # Extract data from report JSON
    # The report structure from FullReport.to_dict():
    # {
    #   "metadata": {"company_name": "...", "domain": "...", "created_at": "..."},
    #   "score": {"total_score": N, "questions_answered": N, "criterion_scores": [...], ...},
    #   "fixes": {"fixes": [...], "total_fixes": N, ...},
    #   "observation": {...} (optional),
    #   "benchmark": {...} (optional),
    #   "divergence": {...} (optional),
    # }
    data = report.data
    metadata = data.get("metadata", {})
    score_data = data.get("score", {})
    score_v2_data = data.get("score_v2", {})  # v2 pillar scores
    fixes_data = data.get("fixes", {})
    _ = data.get("action_center", {})  # v2 action center (reserved for future use)
    observation = data.get("observation")
    benchmark = data.get("benchmark")
    divergence = data.get("divergence")
    citation_context = data.get("citation_context")
    source_primacy = data.get("source_primacy")

    # Get scores - use report denormalized fields if available, otherwise calculate
    typical_score = report.score_typical or int(score_data.get("total_score", 0))
    conservative_score = report.score_conservative or int(typical_score * 0.9)
    generous_score = report.score_generous or int(min(100, typical_score * 1.1))

    # Determine grade based on typical score
    def score_to_grade(s: int) -> tuple[str, str]:
        if s >= 90:
            return "A+", "Excellent AI sourceability"
        elif s >= 80:
            return "A", "Very good AI sourceability"
        elif s >= 70:
            return "B", "Good AI sourceability"
        elif s >= 60:
            return "C", "Fair AI sourceability"
        elif s >= 50:
            return "D", "Poor AI sourceability"
        else:
            return "F", "Very poor AI sourceability"

    grade, grade_description = score_to_grade(typical_score)

    # Build v2 pillar data for template
    pillars = []
    v2_pillars = score_v2_data.get("pillars", [])
    if v2_pillars:
        for pillar in v2_pillars:
            pillars.append(
                {
                    "name": pillar.get("name", ""),
                    "display_name": pillar.get("display_name", ""),
                    "raw_score": pillar.get("raw_score", 0),
                    "max_points": pillar.get("max_points", 0),
                    "points_earned": round(pillar.get("points_earned", 0), 1),
                    "level": pillar.get("level", "critical"),
                }
            )

    # Use v2 grade if available
    if score_v2_data:
        grade = score_v2_data.get("grade", grade)
        grade_description = score_v2_data.get("grade_description", grade_description)
        typical_score = int(score_v2_data.get("total_score", typical_score))

    # v2 partial analysis tracking
    is_partial = score_v2_data.get("is_partial", False) if score_v2_data else False
    pillars_evaluated = score_v2_data.get("pillars_evaluated", 6) if score_v2_data else 6
    max_evaluated_points = score_v2_data.get("max_evaluated_points", 100) if score_v2_data else 100
    evaluated_score_pct = (
        score_v2_data.get("evaluated_score_pct", typical_score) if score_v2_data else typical_score
    )

    # v2 pillar summary counts
    pillars_good = score_v2_data.get("pillars_good", 0) if score_v2_data else 0
    pillars_warning = score_v2_data.get("pillars_warning", 0) if score_v2_data else 0
    pillars_critical = score_v2_data.get("pillars_critical", 0) if score_v2_data else 0

    # Build category data for template (legacy v1 fallback)
    categories = []
    category_scores = score_data.get("category_scores", {})
    if category_scores:
        for cat_name, cat_score in category_scores.items():
            weight = _get_category_weight(cat_name)
            categories.append(
                {
                    "name": cat_name,
                    "score": int(cat_score),
                    "weight": int(weight * 100),
                }
            )
    elif not pillars:
        # Provide default categories if none exist and no v2 pillars
        default_categories = [
            ("Identity", 25),
            ("Offerings", 30),
            ("Contact", 15),
            ("Trust", 15),
            ("Differentiation", 15),
        ]
        for cat_name, weight in default_categories:
            categories.append(
                {
                    "name": cat_name,
                    "score": typical_score,  # Use overall score as placeholder
                    "weight": weight,
                }
            )

    # Build fixes data for template
    fix_list = []
    fixes_items = fixes_data.get("fixes", []) if isinstance(fixes_data, dict) else fixes_data
    for fix in fixes_items:
        # FixItem.to_dict() stores impact as separate fields, not nested
        fix_list.append(
            {
                "severity": _priority_to_severity(fix.get("priority", 3)),
                "title": fix.get("title", ""),
                "reason_code": fix.get("reason_code", ""),
                "impact_min": fix.get("estimated_impact_min", 0),
                "impact_max": fix.get("estimated_impact_max", 0),
                "impact_expected": fix.get("estimated_impact_expected", 0),
                "effort": fix.get("effort_level", "medium"),
                "target_url": fix.get("target_url", ""),
                "scaffold": fix.get("scaffold", ""),
            }
        )

    # Get question counts from score section (not from questions list)
    # The ScoreSection stores: total_questions, questions_answered, questions_partial, questions_unanswered
    questions_answered = score_data.get("questions_answered", 0)
    questions_partial = score_data.get("questions_partial", 0)
    questions_unanswered = score_data.get("questions_unanswered", 0)
    total_questions = score_data.get("total_questions", 0) or 20  # Default to 20 if not set

    # Get coverage from score section, or calculate if not available
    coverage_pct = score_data.get("coverage_percentage", 0)
    if not coverage_pct and total_questions > 0:
        coverage_pct = int((questions_answered / total_questions) * 100)

    # Format report date
    created_at = metadata.get("created_at", "")
    report_date = _format_date(created_at) if created_at else "Unknown"

    # Get domain and company name from metadata
    domain = metadata.get("domain", "")
    company_name = metadata.get(
        "company_name", domain.split(".")[0].title() if domain else "Unknown"
    )

    # Extract criterion scores for the "show the math" section
    # criterion_scores is a list of dicts with 'name', 'raw_score', 'weighted_score', etc.
    criterion_scores = score_data.get("criterion_scores", [])
    content_relevance = 0.0
    signal_coverage = 0.0
    answer_confidence = 0.0
    source_quality = 0.0

    for cs in criterion_scores:
        name = cs.get("name", "").lower().replace(" ", "_")
        # raw_score is already normalized to 0-1
        score = cs.get("raw_score", 0.0)
        if "content" in name or "relevance" in name:
            content_relevance = score
        elif "signal" in name or "coverage" in name:
            signal_coverage = score
        elif "confidence" in name or "answer" in name:
            answer_confidence = score
        elif "source" in name or "quality" in name:
            source_quality = score

    return templates.TemplateResponse(
        request=request,
        name="reports/score_report.html",
        context={
            "company_name": company_name,
            "domain": domain,
            "report_date": report_date,
            "run_id": str(report_id),
            "overall_score": typical_score,
            "score_conservative": conservative_score,
            "score_typical": typical_score,
            "score_generous": generous_score,
            "grade": grade,
            "grade_description": grade_description,
            "categories": categories,
            # v2 pillar data
            "pillars": pillars,
            "has_v2_pillars": len(pillars) > 0,
            "is_partial": is_partial,
            "pillars_evaluated": pillars_evaluated,
            "max_evaluated_points": max_evaluated_points,
            "evaluated_score_pct": round(evaluated_score_pct, 1),
            "pillars_good": pillars_good,
            "pillars_warning": pillars_warning,
            "pillars_critical": pillars_critical,
            "calculation_summary": (
                score_v2_data.get("calculation_summary", []) if score_v2_data else []
            ),
            "critical_issues": score_v2_data.get("critical_issues", []) if score_v2_data else [],
            "top_recommendations": (
                score_v2_data.get("top_recommendations", []) if score_v2_data else []
            ),
            # Question stats
            "questions_answered": questions_answered,
            "questions_partial": questions_partial,
            "questions_unanswered": questions_unanswered,
            "total_questions": total_questions,
            "coverage_score": coverage_pct,
            "content_relevance": content_relevance,
            "signal_coverage": signal_coverage,
            "answer_confidence": answer_confidence,
            "source_quality": source_quality,
            "fixes": fix_list,
            "total_fixes": len(fix_list),
            "critical_fixes": sum(1 for f in fix_list if f.get("severity") == "critical"),
            "observation": observation,
            "benchmark": benchmark,
            "divergence": divergence,
            "citation_context": citation_context,
            "source_primacy": source_primacy,
            "show_the_math": score_data.get("show_the_math", ""),
        },
    )


@router.get("/runs/{run_id}/status", response_class=HTMLResponse, name="run_status")
async def run_status_fragment(
    request: Request,
    run_id: uuid.UUID,
    db: Any = Depends(get_db),
) -> HTMLResponse:
    """Return HTML fragment for run status (used by HTMX polling)."""
    user = await get_optional_user(request)
    if not user:
        return HTMLResponse(content="<div>Unauthorized</div>", status_code=401)

    try:
        run = await run_service.get_run(db, run_id, user.id)
    except Exception:
        return HTMLResponse(content="<div>Run not found</div>", status_code=404)

    # Get job status if available
    from api.services import job_service

    job_status = None
    if run.job_id:
        job_info = job_service.get_job_status(run.job_id)
        if job_info:
            job_status = job_info.status.value

    return templates.TemplateResponse(
        request=request,
        name="partials/run_status.html",
        context={
            "run": {
                "id": str(run.id),
                "status": run.status,
                "progress": run.progress or 0,
                "job_status": job_status,
                "completed": run.status in ("complete", "failed"),
                "error_message": run.error_message,
                "report_id": str(run.report_id) if run.report_id else None,
            },
        },
    )


# Helper functions


def _score_to_grade(score: float | None) -> str:
    """Convert numeric score to letter grade."""
    if score is None:
        return "—"
    if score >= 90:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 65:
        return "B-"
    if score >= 60:
        return "C+"
    if score >= 55:
        return "C"
    if score >= 50:
        return "C-"
    if score >= 45:
        return "D+"
    if score >= 40:
        return "D"
    return "F"


def _format_last_run(report: Any | None) -> str:
    """Format the last run time as a human-readable string."""
    if not report or not report.created_at:
        return "Never"

    from datetime import datetime

    now = datetime.now(UTC)
    created = report.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)

    diff = now - created
    seconds = diff.total_seconds()

    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins} minute{'s' if mins != 1 else ''} ago"
    if seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds / 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def _get_category_weight(category: str) -> float:
    """Get weight for a category."""
    weights = {
        "identity": 0.25,
        "offerings": 0.30,
        "contact": 0.15,
        "trust": 0.15,
        "differentiation": 0.15,
    }
    return weights.get(category.lower(), 0.20)


def _priority_to_severity(priority: int) -> str:
    """Convert numeric priority to severity string."""
    if priority == 1:
        return "critical"
    if priority == 2:
        return "high"
    if priority == 3:
        return "medium"
    return "low"


def _format_date(date_str: str | None) -> str:
    """Format ISO date string as readable date."""
    if not date_str:
        return "Unknown"

    from datetime import datetime

    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return date_str


# Authentication routes


@router.get("/login", response_class=HTMLResponse, name="login")
async def login_page(
    request: Request,
    next: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Render the login page."""
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "next": next,
            "error": error,
        },
    )


@router.post("/login", response_model=None, name="login_submit")
async def login_submit(
    request: Request,
    db: Any = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Handle login form submission."""
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    next_url = str(form.get("next", "/"))

    if not email or not password:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Email and password are required",
                "email": email,
                "next": next_url,
            },
            status_code=400,
        )

    # Try to authenticate
    from sqlalchemy import select

    from api.models import User

    result = await db.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    user = result.scalar_one_or_none()

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Invalid email or password",
                "email": email,
                "next": next_url,
            },
            status_code=401,
        )

    # Verify password
    from api.auth import verify_password

    if not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Invalid email or password",
                "email": email,
                "next": next_url,
            },
            status_code=401,
        )

    # Create session token
    from api.auth import create_access_token

    token = create_access_token(str(user.id))

    # Redirect with session cookie
    response = RedirectResponse(url=next_url or "/", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax",
    )
    return response


@router.get("/register", response_class=HTMLResponse, name="register")
async def register_page(
    request: Request,
    next: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    """Render the registration page."""
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={
            "next": next,
            "error": error,
        },
    )


@router.post("/register", response_model=None, name="register_submit")
async def register_submit(
    request: Request,
    db: Any = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Handle registration form submission."""
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    password_confirm = str(form.get("password_confirm", ""))
    next_url = str(form.get("next", "/"))

    errors = []
    if not email:
        errors.append("Email is required")
    if not password:
        errors.append("Password is required")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if password != password_confirm:
        errors.append("Passwords do not match")

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": "; ".join(errors),
                "email": email,
                "next": next_url,
            },
            status_code=400,
        )

    # Check if user exists
    from sqlalchemy import select

    from api.models import User

    result = await db.execute(select(User).where(User.email == email))  # type: ignore[arg-type]
    existing = result.scalar_one_or_none()

    if existing:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": "An account with this email already exists",
                "email": email,
                "next": next_url,
            },
            status_code=409,
        )

    # Create user
    from api.auth import get_password_hash

    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        is_active=True,
        is_verified=True,  # Auto-verify for demo
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create session token
    from api.auth import create_access_token

    token = create_access_token(str(user.id))

    # Redirect with session cookie
    response = RedirectResponse(url=next_url or "/", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax",
    )
    return response


@router.get("/logout", response_model=None, name="logout")
async def logout() -> RedirectResponse:
    """Log out the current user."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE)
    return response


@router.get("/validation", response_class=HTMLResponse, name="validation")
async def validation_page(
    request: Request,
    db: Any = Depends(get_db),
) -> HTMLResponse:
    """Render the validation page showing predicted vs observed data."""
    from collections import Counter

    from sqlalchemy import select

    from api.models.calibration import CalibrationSample, OutcomeMatch

    # Query calibration samples
    samples = []
    mismatch_drivers_counter: Counter = Counter()

    try:
        result = await db.execute(
            select(CalibrationSample)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .order_by(CalibrationSample.created_at.desc())
            .limit(100)
        )
        db_samples = result.scalars().all()

        for s in db_samples:
            # Determine mismatch driver for non-correct predictions
            driver = ""
            if s.outcome_match == OutcomeMatch.OPTIMISTIC.value:
                if (
                    s.sim_signals_found
                    and s.sim_signals_total
                    and s.sim_signals_found < s.sim_signals_total * 0.5
                ):
                    driver = "low_signal_coverage"
                elif s.sim_score and s.sim_score < 50:
                    driver = "borderline_score"
                else:
                    driver = "unknown_optimism"
            elif s.outcome_match == OutcomeMatch.PESSIMISTIC.value:
                if s.obs_cited:
                    driver = "brand_authority_override"
                elif s.question_text and (
                    "what is" in s.question_text.lower() or "who is" in s.question_text.lower()
                ):
                    driver = "identity_query_override"
                else:
                    driver = "unknown_pessimism"

            if driver:
                mismatch_drivers_counter[driver] += 1

            samples.append(
                {
                    "question_text": s.question_text or "",
                    "question_category": s.question_category or "unknown",
                    "sim_answerability": s.sim_answerability or "unknown",
                    "sim_score": s.sim_score or 0,
                    "obs_mentioned": s.obs_mentioned or False,
                    "obs_cited": s.obs_cited or False,
                    "obs_provider": s.obs_provider or "",
                    "obs_model": s.obs_model or "",
                    "outcome": s.outcome_match or "unknown",
                    "mismatch_driver": driver,
                }
            )
    except Exception as e:
        logger.warning("validation_samples_query_failed", error=str(e))

    # Calculate metrics
    correct_count = sum(1 for s in samples if s["outcome"] == OutcomeMatch.CORRECT.value)
    optimistic_count = sum(1 for s in samples if s["outcome"] == OutcomeMatch.OPTIMISTIC.value)
    pessimistic_count = sum(1 for s in samples if s["outcome"] == OutcomeMatch.PESSIMISTIC.value)
    total_known = correct_count + optimistic_count + pessimistic_count
    accuracy = correct_count / total_known if total_known > 0 else 0

    return templates.TemplateResponse(
        request=request,
        name="validation/index.html",
        context={
            "samples": samples,
            "accuracy": accuracy,
            "correct_count": correct_count,
            "optimistic_count": optimistic_count,
            "pessimistic_count": pessimistic_count,
            "total_known": total_known,
            "mismatch_drivers": mismatch_drivers_counter.most_common(10),
        },
    )
