"""Public audit endpoints — no authentication required.

Provides a free audit tool that accepts a URL, runs the Findable Score
pipeline, and returns score + pillar breakdown + top fixes.

Rate limited to 3 audits per hour per IP address via Redis.
"""

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import async_session_maker
from api.models import Report, Run, Site

logger = structlog.get_logger(__name__)

# Template configuration
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/public", tags=["public"])


# ============================================================================
# Rate Limiting
# ============================================================================

MAX_AUDITS_PER_HOUR = 3


def _get_client_ip(request: Request) -> str:
    """Extract client IP, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_rate_limit(request: Request) -> None:
    """Check per-IP rate limit using Redis."""
    settings = get_settings()
    if not settings.redis_url:
        return  # No Redis = no rate limiting

    try:
        import redis.asyncio as aioredis

        client_ip = _get_client_ip(request)
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
        key = f"findable:public_audit:rate:{ip_hash}"

        r = aioredis.from_url(str(settings.redis_url))
        try:
            current = await r.get(key)
            if current and int(current) >= MAX_AUDITS_PER_HOUR:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {MAX_AUDITS_PER_HOUR} audits per hour.",
                )
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 3600)  # 1 hour TTL
            await pipe.execute()
        finally:
            await r.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("rate_limit_check_failed", error=str(e))
        # Fail open — allow the request if Redis is down


# ============================================================================
# Schemas
# ============================================================================


class PublicAuditRequest(BaseModel):
    """Request to start a public audit."""

    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = f"https://{v}"
        parsed = urlparse(v)
        if not parsed.netloc or "." not in parsed.netloc:
            raise ValueError("Invalid URL")
        # Reject localhost, private IPs
        hostname = parsed.netloc.split(":")[0].lower()
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0") or hostname.startswith("192.168."):
            raise ValueError("Cannot audit local addresses")
        return v


class PublicAuditResponse(BaseModel):
    """Response from starting a public audit."""

    audit_id: str
    domain: str
    status_url: str
    result_url: str


# ============================================================================
# Public User Management
# ============================================================================

PUBLIC_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
PUBLIC_USER_EMAIL = "public@findable.score"


async def _ensure_public_user(db: AsyncSession) -> None:
    """Create the public audit user if it doesn't exist."""
    from api.models.user import User

    result = await db.execute(select(User).where(User.id == PUBLIC_USER_ID))
    if not result.scalar_one_or_none():
        user = User(
            id=PUBLIC_USER_ID,
            email=PUBLIC_USER_EMAIL,
            hashed_password="public_user_no_login",
            name="Public Audit",
        )
        db.add(user)
        await db.flush()


# ============================================================================
# Helper: Generate shareable ID
# ============================================================================


def _make_shareable_id(run_id: uuid.UUID) -> str:
    """Generate a short, URL-safe shareable ID from a run UUID."""
    return run_id.hex[:12]


async def _find_run_by_shareable_id(db: AsyncSession, shareable_id: str) -> Run | None:
    """Find a run by its shareable ID prefix."""
    # shareable_id is first 12 hex chars of run_id
    result = await db.execute(select(Run))
    runs = result.scalars().all()
    for run in runs:
        if run.id.hex[:12] == shareable_id:
            return run
    return None


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/audit", response_model=PublicAuditResponse)
async def start_public_audit(
    request: Request,
    audit_request: PublicAuditRequest,
) -> PublicAuditResponse:
    """Start a free public audit. Rate limited to 3/hour per IP."""
    await _check_rate_limit(request)

    parsed = urlparse(audit_request.url)
    domain = parsed.netloc.replace("www.", "")

    # Create deterministic site_id from domain
    site_id = uuid.uuid5(uuid.NAMESPACE_DNS, domain)
    run_id = uuid.uuid4()
    shareable_id = _make_shareable_id(run_id)

    async with async_session_maker() as db:
        await _ensure_public_user(db)

        # Get or create site
        result = await db.execute(select(Site).where(Site.id == site_id))
        site = result.scalar_one_or_none()

        if not site:
            site = Site(
                id=site_id,
                user_id=PUBLIC_USER_ID,
                domain=domain,
                name=domain.split(".")[0].title(),
                business_model="unknown",
            )
            db.add(site)

        # Create run
        run = Run(
            id=run_id,
            site_id=site_id,
            run_type="starter_audit",
            status="queued",
            config={
                "include_observation": True,
                "include_benchmark": False,
                "bands": ["typical"],
                "provider": {"preferred": "router", "model": "auto"},
                "public_audit": True,
            },
        )
        db.add(run)
        await db.commit()

        # Enqueue the audit job
        from api.services.job_service import job_service

        try:
            job_id = job_service.enqueue_audit(run, site)
            logger.info(
                "public_audit_enqueued",
                run_id=str(run_id),
                domain=domain,
                job_id=job_id,
                client_ip=_get_client_ip(request),
            )
        except Exception as e:
            logger.error("public_audit_enqueue_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Audit service temporarily unavailable",
            )

    return PublicAuditResponse(
        audit_id=shareable_id,
        domain=domain,
        status_url=f"/public/audit/{shareable_id}/status",
        result_url=f"/score/{shareable_id}",
    )


@router.post("/audit/form", response_class=HTMLResponse)
async def start_public_audit_form(
    request: Request,
    url: Annotated[str, Form()],
) -> RedirectResponse:
    """Start audit from HTML form submission, redirect to results page."""
    audit_request = PublicAuditRequest(url=url)

    await _check_rate_limit(request)

    parsed = urlparse(audit_request.url)
    domain = parsed.netloc.replace("www.", "")

    site_id = uuid.uuid5(uuid.NAMESPACE_DNS, domain)
    run_id = uuid.uuid4()
    shareable_id = _make_shareable_id(run_id)

    async with async_session_maker() as db:
        await _ensure_public_user(db)

        result = await db.execute(select(Site).where(Site.id == site_id))
        site = result.scalar_one_or_none()

        if not site:
            site = Site(
                id=site_id,
                user_id=PUBLIC_USER_ID,
                domain=domain,
                name=domain.split(".")[0].title(),
                business_model="unknown",
            )
            db.add(site)

        run = Run(
            id=run_id,
            site_id=site_id,
            run_type="starter_audit",
            status="queued",
            config={
                "include_observation": True,
                "include_benchmark": False,
                "bands": ["typical"],
                "provider": {"preferred": "router", "model": "auto"},
                "public_audit": True,
            },
        )
        db.add(run)
        await db.commit()

        from api.services.job_service import job_service

        try:
            job_service.enqueue_audit(run, site)
        except Exception as e:
            logger.error("public_audit_form_enqueue_failed", error=str(e))

    # Redirect to the score page (which will show progress)
    return RedirectResponse(url=f"/score/{shareable_id}", status_code=303)


@router.get("/audit/{audit_id}/status")
async def get_audit_status(audit_id: str) -> StreamingResponse:
    """Stream audit progress via Server-Sent Events."""

    async def event_generator() -> AsyncGenerator[str, None]:
        last_status = None
        last_progress = None
        timeout_counter = 0
        max_timeout = 600  # 10 minutes

        while timeout_counter < max_timeout:
            async with async_session_maker() as db:
                run = await _find_run_by_shareable_id(db, audit_id)

                if not run:
                    yield f"event: error\ndata: {json.dumps({'error': 'Audit not found'})}\n\n"
                    break

                current_status = run.status
                current_progress = run.progress

                if current_status != last_status or current_progress != last_progress:
                    event_data = {
                        "status": current_status,
                        "progress": current_progress,
                    }

                    if current_status == "complete":
                        event_data["report_id"] = str(run.report_id) if run.report_id else None
                        event_data["result_url"] = f"/score/{audit_id}"
                        yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                        break

                    if current_status == "failed":
                        event_data["error"] = run.error_message or "Audit failed"
                        yield f"event: error\ndata: {json.dumps(event_data)}\n\n"
                        break

                    yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"
                    last_status = current_status
                    last_progress = current_progress

            await asyncio.sleep(2)
            timeout_counter += 2

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/audit/{audit_id}/result")
async def get_audit_result(audit_id: str) -> dict:
    """Get audit result as JSON (score + pillar breakdown + top 3 fixes)."""
    async with async_session_maker() as db:
        run = await _find_run_by_shareable_id(db, audit_id)

        if not run:
            raise HTTPException(status_code=404, detail="Audit not found")

        if run.status != "complete":
            return {
                "status": run.status,
                "progress": run.progress,
                "complete": False,
            }

        # Load report
        report_result = await db.execute(select(Report).where(Report.id == run.report_id))
        report = report_result.scalar_one_or_none()

        if not report or not report.data:
            raise HTTPException(status_code=404, detail="Report not found")

        report_data = report.data

        # Extract score section
        score_section = report_data.get("score", {})
        v2_score = score_section.get("v2", {})

        # Extract top 3 fixes
        fixes_section = report_data.get("fixes", {})
        all_fixes = fixes_section.get("items", [])
        top_fixes = all_fixes[:3]

        # Get site info
        site_result = await db.execute(select(Site).where(Site.id == run.site_id))
        site = site_result.scalar_one_or_none()

        return {
            "status": "complete",
            "complete": True,
            "domain": site.domain if site else "unknown",
            "score": v2_score.get("total_score", 0),
            "level": v2_score.get("level_label", "Unknown"),
            "pillars": v2_score.get("pillars", []),
            "top_fixes": top_fixes,
            "shareable_url": f"/score/{audit_id}",
        }


# ============================================================================
# Public Score Page (HTML)
# ============================================================================


# Register the /score route separately (outside /public prefix)
score_router = APIRouter(tags=["public"])


@score_router.get("/score/{shareable_id}", response_class=HTMLResponse)
async def score_page(request: Request, shareable_id: str) -> HTMLResponse:
    """Public shareable score results page."""
    async with async_session_maker() as db:
        run = await _find_run_by_shareable_id(db, shareable_id)

        if not run:
            raise HTTPException(status_code=404, detail="Score not found")

        # Get site info
        site_result = await db.execute(select(Site).where(Site.id == run.site_id))
        site = site_result.scalar_one_or_none()
        domain = site.domain if site else "unknown"

        # If still running, show progress page
        if run.status not in ("complete", "failed"):
            return templates.TemplateResponse(
                "public/progress.html",
                {
                    "request": request,
                    "domain": domain,
                    "shareable_id": shareable_id,
                    "status": run.status,
                    "progress": run.progress or {},
                },
            )

        if run.status == "failed":
            return templates.TemplateResponse(
                "public/error.html",
                {
                    "request": request,
                    "domain": domain,
                    "error": run.error_message or "Audit failed",
                },
            )

        # Load report for completed run
        report_result = await db.execute(select(Report).where(Report.id == run.report_id))
        report = report_result.scalar_one_or_none()

        if not report or not report.data:
            raise HTTPException(status_code=404, detail="Report not ready")

        report_data = report.data
        score_section = report_data.get("score", {})
        v2_score = score_section.get("v2", {})

        # Extract top 3 fixes
        fixes_section = report_data.get("fixes", {})
        all_fixes = fixes_section.get("items", [])
        top_fixes = all_fixes[:3]

        # Build OG meta tags
        total_score = v2_score.get("total_score", 0)
        level_label = v2_score.get("level_label", "Unknown")

        return templates.TemplateResponse(
            "public/score.html",
            {
                "request": request,
                "domain": domain,
                "score": round(total_score),
                "level_label": level_label,
                "pillars": v2_score.get("pillars", []),
                "top_fixes": top_fixes,
                "shareable_id": shareable_id,
                "shareable_url": f"{request.base_url}score/{shareable_id}",
                "og_title": f"Findable Score: {round(total_score)}/100 - {domain}",
                "og_description": f"{domain} scored {round(total_score)}/100 on the Findable Score. Level: {level_label}.",
            },
        )


@score_router.get("/score/{shareable_id}/og.png")
async def score_og_image(shareable_id: str) -> Response:
    """Generate and return an OG image (1200x630 PNG) for a completed score page."""
    async with async_session_maker() as db:
        run = await _find_run_by_shareable_id(db, shareable_id)

        if not run or run.status != "complete":
            raise HTTPException(status_code=404, detail="Score not found")

        # Load report
        report_result = await db.execute(select(Report).where(Report.id == run.report_id))
        report = report_result.scalar_one_or_none()

        if not report or not report.data:
            raise HTTPException(status_code=404, detail="Report not found")

        v2_score = report.data.get("score", {}).get("v2", {})
        score = round(v2_score.get("total_score", 0))
        level_label = v2_score.get("level_label", "Unknown")

        # Get domain from site
        site_result = await db.execute(select(Site).where(Site.id == run.site_id))
        site = site_result.scalar_one_or_none()
        domain = site.domain if site else "unknown"

    # Lazy import to avoid heavy PIL import on startup
    from worker.reports.og_image import generate_og_image

    png_bytes = generate_og_image(score, domain, level_label)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@score_router.get("/audit", response_class=HTMLResponse)
async def audit_landing_page(request: Request) -> HTMLResponse:
    """Public audit landing page with URL input."""
    return templates.TemplateResponse(
        "public/audit.html",
        {"request": request},
    )
