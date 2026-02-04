"""Integration test for the full audit pipeline."""

import asyncio
import os

import pytest

# Set environment before imports
os.environ["ENV"] = "development"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://findable:findable@localhost:5432/findable"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET"] = "dev-secret-key-for-local-testing"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_audit_pipeline_mini():
    """
    Test the audit pipeline with a minimal site.

    This test crawls a small, fast-loading site to verify
    the entire pipeline works end-to-end.
    """
    from sqlalchemy import select

    from api.database import async_session_maker
    from api.models import Run, Site, User
    from worker.tasks.audit import run_audit

    # Create test data
    async with async_session_maker() as db:
        # Create a test user if not exists
        result = await db.execute(select(User).where(User.email == "test-pipeline@example.com"))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email="test-pipeline@example.com",
                hashed_password="not-a-real-hash",
            )
            db.add(user)
            await db.flush()

        # Create a test site - use example.com as it's small and fast
        site = Site(
            user_id=user.id,
            domain="example.com",
            name="Example Domain",
        )
        db.add(site)
        await db.flush()

        # Create a run
        run = Run(
            site_id=site.id,
            status="pending",
            run_type="full",
        )
        db.add(run)
        await db.commit()

        site_id = site.id
        run_id = run.id

    try:
        # Execute the audit
        result = await run_audit(run_id, site_id)

        # Verify the result
        assert result["status"] == "complete"
        assert "report_id" in result
        assert "score" in result
        assert 0 <= result["score"] <= 100

        # Verify run was updated in database
        async with async_session_maker() as db:
            run_result = await db.execute(select(Run).where(Run.id == run_id))
            run = run_result.scalar_one()

            assert run.status == "complete"
            assert run.report_id is not None
            assert run.completed_at is not None

        print("\n[PASS] Pipeline test passed!")
        print(f"  Score: {result['score']}")
        print(f"  Grade: {result.get('grade', 'N/A')}")
        print(f"  Report ID: {result['report_id']}")

    finally:
        # Cleanup test data
        async with async_session_maker() as db:
            # Delete run and site
            run_result = await db.execute(select(Run).where(Run.id == run_id))
            run = run_result.scalar_one_or_none()
            if run:
                await db.delete(run)

            site_result = await db.execute(select(Site).where(Site.id == site_id))
            site = site_result.scalar_one_or_none()
            if site:
                await db.delete(site)

            await db.commit()


if __name__ == "__main__":
    # Run directly for quick testing
    asyncio.run(test_audit_pipeline_mini())
