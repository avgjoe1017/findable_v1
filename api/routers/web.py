"""Web routes for HTML pages using Jinja2 templates.

Provides server-rendered UI for the Findable Score Analyzer MVP.
"""

import uuid
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from api.auth import get_current_user_optional
from api.config import get_settings
from api.database import async_session_maker, get_db
from api.models.user import User
from api.services import run_service, site_service

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
            score = latest_report.score_typical if latest_report else None
            grade = _score_to_grade(score) if score else None

            if score:
                scores.append(score)

            sites.append(
                {
                    "id": str(site.id),
                    "name": site.name,
                    "domain": site.domain,
                    "score": score or 0,
                    "grade": grade or "—",
                    "trend": "+0",  # TODO: Calculate from previous run
                    "last_run": _format_last_run(latest_report),
                    "status": "completed" if latest_report else "pending",
                }
            )

        avg_score = int(sum(scores) / len(scores)) if scores else 0
        # TODO: Calculate open fixes from reports

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
        run_list.append(
            {
                "id": str(run.id),
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "include_observation": run.include_observation,
                "include_benchmark": run.include_benchmark,
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

        # Enqueue background job
        job_id = job_service.enqueue_audit(run, site)
        run.job_id = job_id
        await db.flush()

        return RedirectResponse(url=f"/sites/{site_id}", status_code=303)
    except Exception as e:
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
    data = report.data
    metadata = data.get("metadata", {})
    score = data.get("score", {})
    fixes = data.get("fixes", {})
    observation = data.get("observation")
    benchmark = data.get("benchmark")
    divergence = data.get("divergence")

    # Build category data for template
    categories = []
    for cat_name, cat_score in score.get("category_scores", {}).items():
        weight = _get_category_weight(cat_name)
        categories.append(
            {
                "name": cat_name,
                "score": int(cat_score),
                "weight": int(weight * 100),
            }
        )

    # Build fixes data for template
    fix_list = []
    for fix in fixes.get("fixes", []):
        impact = fix.get("estimated_impact", {})
        fix_list.append(
            {
                "severity": _priority_to_severity(fix.get("priority", 3)),
                "title": fix.get("title", ""),
                "reason_code": fix.get("reason_code", ""),
                "impact_min": impact.get("min", 0),
                "impact_max": impact.get("max", 0),
                "impact_expected": impact.get("expected", 0),
                "effort": fix.get("effort_level", "medium"),
                "target_url": fix.get("target_url", ""),
                "scaffold": fix.get("scaffold", ""),
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="reports/score_report.html",
        context={
            "company_name": metadata.get("company_name", "Unknown"),
            "domain": metadata.get("domain", ""),
            "report_date": _format_date(metadata.get("created_at")),
            "run_id": metadata.get("run_id", ""),
            "overall_score": int(score.get("total_score", 0)),
            "grade": score.get("grade", "C"),
            "grade_description": score.get("grade_description", ""),
            "categories": categories,
            "questions_answered": score.get("questions_answered", 0),
            "questions_partial": score.get("questions_partial", 0),
            "questions_unanswered": score.get("questions_unanswered", 0),
            "coverage_score": int(score.get("coverage_percentage", 0)),
            "fixes": fix_list,
            "total_fixes": fixes.get("total_fixes", 0),
            "critical_fixes": fixes.get("critical_fixes", 0),
            "observation": observation,
            "benchmark": benchmark,
            "divergence": divergence,
            "show_the_math": score.get("show_the_math", ""),
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

    result = await db.execute(select(User).where(User.email == email))
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

    result = await db.execute(select(User).where(User.email == email))
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
