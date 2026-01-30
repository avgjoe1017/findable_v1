"""Tests for deployment scripts and configuration."""

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestStartScript:
    """Tests for the production start script."""

    def test_script_exists(self):
        """Verify start script exists."""
        script_path = Path("scripts/start.py")
        assert script_path.exists()

    def test_script_importable(self):
        """Verify start script can be imported."""
        from scripts.start import main, run_migrations, start_api

        assert callable(main)
        assert callable(run_migrations)
        assert callable(start_api)

    @patch("scripts.start.subprocess.run")
    def test_run_migrations_success(self, mock_run):
        """Test successful migration run."""
        from scripts.start import run_migrations

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Migrations applied",
            stderr="",
        )

        result = run_migrations()
        assert result is True
        mock_run.assert_called_once()

    @patch("scripts.start.subprocess.run")
    def test_run_migrations_failure(self, mock_run):
        """Test migration failure handling."""
        import subprocess

        from scripts.start import run_migrations

        mock_run.side_effect = subprocess.CalledProcessError(
            1, "alembic", stderr="Migration failed"
        )

        result = run_migrations()
        assert result is False


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_env_example_exists(self):
        """Verify .env.example exists."""
        env_example = Path(".env.example")
        assert env_example.exists()

    def test_env_example_contains_required_vars(self):
        """Verify .env.example contains all required variables."""
        env_example = Path(".env.example")
        content = env_example.read_text()

        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "JWT_SECRET",
            "ENV",
            "LOG_LEVEL",
        ]

        for var in required_vars:
            assert var in content, f"Missing required variable: {var}"

    def test_env_example_contains_optional_vars(self):
        """Verify .env.example documents optional variables."""
        env_example = Path(".env.example")
        content = env_example.read_text()

        optional_vars = [
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "SENTRY_DSN",
            "STRIPE_SECRET_KEY",
        ]

        for var in optional_vars:
            assert var in content, f"Missing optional variable: {var}"


class TestDockerConfiguration:
    """Tests for Docker configuration files."""

    def test_dockerfile_exists(self):
        """Verify Dockerfile exists."""
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists()

    def test_dockerfile_has_api_stage(self):
        """Verify Dockerfile has API stage."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "FROM deps as api" in content

    def test_dockerfile_has_worker_stage(self):
        """Verify Dockerfile has worker stage."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "FROM deps as worker" in content

    def test_dockerfile_has_scheduler_stage(self):
        """Verify Dockerfile has scheduler stage."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "FROM deps as scheduler" in content

    def test_dockerfile_has_migrate_stage(self):
        """Verify Dockerfile has migration stage."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "FROM deps as migrate" in content

    def test_dockerfile_has_healthcheck(self):
        """Verify Dockerfile has health check."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content

    def test_docker_compose_prod_exists(self):
        """Verify production docker-compose exists."""
        compose = Path("docker-compose.prod.yml")
        assert compose.exists()

    def test_docker_compose_prod_services(self):
        """Verify production docker-compose has all services."""
        compose = Path("docker-compose.prod.yml")
        content = compose.read_text()

        services = ["api:", "worker:", "scheduler:", "postgres:", "redis:"]
        for service in services:
            assert service in content, f"Missing service: {service}"


class TestRailwayConfiguration:
    """Tests for Railway deployment configuration."""

    def test_railway_toml_exists(self):
        """Verify railway.toml exists."""
        railway = Path("railway.toml")
        assert railway.exists()

    def test_railway_toml_has_build_config(self):
        """Verify railway.toml has build configuration."""
        railway = Path("railway.toml")
        content = railway.read_text()
        assert "[build]" in content
        assert "dockerfile" in content.lower()

    def test_railway_toml_has_deploy_config(self):
        """Verify railway.toml has deploy configuration."""
        railway = Path("railway.toml")
        content = railway.read_text()
        assert "[deploy]" in content
        assert "healthcheckPath" in content

    def test_railway_toml_health_check_path(self):
        """Verify railway.toml has correct health check path."""
        railway = Path("railway.toml")
        content = railway.read_text()
        # Updated for Day 24 route changes
        assert "/api/health" in content


class TestProcfile:
    """Tests for Procfile configuration."""

    def test_procfile_exists(self):
        """Verify Procfile exists."""
        procfile = Path("Procfile")
        assert procfile.exists()

    def test_procfile_has_web_process(self):
        """Verify Procfile has web process."""
        procfile = Path("Procfile")
        content = procfile.read_text()
        assert "web:" in content

    def test_procfile_has_worker_process(self):
        """Verify Procfile has worker process."""
        procfile = Path("Procfile")
        content = procfile.read_text()
        assert "worker:" in content

    def test_procfile_has_release_command(self):
        """Verify Procfile has release command for migrations."""
        procfile = Path("Procfile")
        content = procfile.read_text()
        assert "release:" in content
        assert "alembic" in content


class TestMigrations:
    """Tests for database migrations configuration."""

    def test_alembic_ini_exists(self):
        """Verify alembic.ini exists."""
        alembic_ini = Path("alembic.ini")
        assert alembic_ini.exists()

    def test_migrations_env_exists(self):
        """Verify migrations/env.py exists."""
        migrations_env = Path("migrations/env.py")
        assert migrations_env.exists()

    def test_migrations_env_imports_all_models(self):
        """Verify migrations/env.py imports all models."""
        migrations_env = Path("migrations/env.py")
        content = migrations_env.read_text()

        # Check for model imports
        required_imports = [
            "User",
            "Site",
            "Competitor",
            "Run",
            "Report",
            "Snapshot",
            "MonitoringSchedule",
            "Alert",
            "AlertConfig",
            "Subscription",
            "UsageRecord",
            "BillingEvent",
        ]

        for model in required_imports:
            assert model in content, f"Missing model import: {model}"

    def test_initial_migration_exists(self):
        """Verify initial migration exists."""
        migrations_dir = Path("migrations/versions")
        migrations = list(migrations_dir.glob("*.py"))
        assert len(migrations) > 0, "No migrations found"


class TestDeploymentDocs:
    """Tests for deployment documentation."""

    def test_deployment_md_exists(self):
        """Verify DEPLOYMENT.md exists."""
        deployment_md = Path("DEPLOYMENT.md")
        assert deployment_md.exists()

    def test_deployment_md_sections(self):
        """Verify DEPLOYMENT.md has all required sections."""
        deployment_md = Path("DEPLOYMENT.md")
        content = deployment_md.read_text(encoding="utf-8")

        required_sections = [
            "Prerequisites",
            "Railway Deployment",
            "Docker Deployment",
            "Environment Variables",
            "Database Setup",
            "Post-Deployment",
            "Monitoring",
            "Troubleshooting",
        ]

        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_deployment_md_has_health_check_info(self):
        """Verify DEPLOYMENT.md documents health checks."""
        deployment_md = Path("DEPLOYMENT.md")
        content = deployment_md.read_text(encoding="utf-8")
        assert "/api/health" in content
        assert "/api/ready" in content


class TestSecurityConfiguration:
    """Tests for security-related configuration."""

    def test_non_root_user_in_dockerfile(self):
        """Verify Dockerfile uses non-root user."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "useradd" in content
        assert "USER appuser" in content

    def test_env_example_no_real_secrets(self):
        """Verify .env.example doesn't contain real secrets."""
        env_example = Path(".env.example")
        content = env_example.read_text()

        # Check for placeholder patterns
        assert "xxx" in content.lower() or "your-" in content.lower()

        # Make sure no real-looking secrets
        import re

        # Real Stripe keys start with sk_live_ or pk_live_
        assert not re.search(r"sk_live_[A-Za-z0-9]+", content)
        assert not re.search(r"pk_live_[A-Za-z0-9]+", content)
