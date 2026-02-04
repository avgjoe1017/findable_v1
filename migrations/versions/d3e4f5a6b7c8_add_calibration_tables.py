"""add_calibration_tables

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-02-02 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create calibration_configs table first (referenced by others)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_configs (
            id UUID PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,

            -- Status
            status VARCHAR(50) NOT NULL DEFAULT 'draft',
            is_active BOOLEAN NOT NULL DEFAULT FALSE,

            -- Pillar weights (must sum to 100)
            weight_technical FLOAT NOT NULL DEFAULT 15.0,
            weight_structure FLOAT NOT NULL DEFAULT 20.0,
            weight_schema FLOAT NOT NULL DEFAULT 15.0,
            weight_authority FLOAT NOT NULL DEFAULT 15.0,
            weight_retrieval FLOAT NOT NULL DEFAULT 25.0,
            weight_coverage FLOAT NOT NULL DEFAULT 10.0,

            -- Answerability thresholds
            threshold_fully_answerable FLOAT NOT NULL DEFAULT 0.7,
            threshold_partially_answerable FLOAT NOT NULL DEFAULT 0.3,

            -- Signal matching threshold
            threshold_signal_match FLOAT NOT NULL DEFAULT 0.6,

            -- Scoring weights within simulation
            scoring_relevance_weight FLOAT NOT NULL DEFAULT 0.4,
            scoring_signal_weight FLOAT NOT NULL DEFAULT 0.4,
            scoring_confidence_weight FLOAT NOT NULL DEFAULT 0.2,

            -- Validation metrics
            validation_accuracy FLOAT,
            validation_sample_count INTEGER,
            validation_optimism_bias FLOAT,
            validation_pessimism_bias FLOAT,
            validation_f1_score FLOAT,

            -- Audit trail
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            notes TEXT,

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            validated_at TIMESTAMP WITH TIME ZONE,
            activated_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    # Create indexes for calibration_configs
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_configs_status ON calibration_configs(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_configs_is_active ON calibration_configs(is_active)"
    )

    # Create calibration_experiments table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_experiments (
            id UUID PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            description TEXT,

            -- Experiment setup
            control_config_id UUID NOT NULL REFERENCES calibration_configs(id) ON DELETE CASCADE,
            treatment_config_id UUID NOT NULL REFERENCES calibration_configs(id) ON DELETE CASCADE,

            -- Traffic allocation
            treatment_allocation FLOAT NOT NULL DEFAULT 0.1,

            -- Status
            status VARCHAR(50) NOT NULL DEFAULT 'draft',

            -- Sample requirements
            min_samples_per_arm INTEGER NOT NULL DEFAULT 100,

            -- Results
            control_samples INTEGER NOT NULL DEFAULT 0,
            treatment_samples INTEGER NOT NULL DEFAULT 0,
            control_accuracy FLOAT,
            treatment_accuracy FLOAT,
            control_optimism FLOAT,
            treatment_optimism FLOAT,

            -- Statistical significance
            p_value FLOAT,
            is_significant BOOLEAN,

            -- Winner
            winner VARCHAR(50),
            winner_reason TEXT,

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE,
            concluded_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    # Create indexes for calibration_experiments
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_experiments_status ON calibration_experiments(status)"
    )

    # Create calibration_samples table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_samples (
            id UUID PRIMARY KEY,

            -- References
            site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            question_id VARCHAR(64) NOT NULL,

            -- Simulation prediction
            sim_answerability VARCHAR(50) NOT NULL,
            sim_score FLOAT NOT NULL,
            sim_signals_found INTEGER NOT NULL,
            sim_signals_total INTEGER NOT NULL,
            sim_relevance_score FLOAT NOT NULL DEFAULT 0.0,

            -- Observation outcome (ground truth)
            obs_mentioned BOOLEAN NOT NULL,
            obs_cited BOOLEAN NOT NULL,
            obs_sentiment VARCHAR(50),
            obs_confidence VARCHAR(50),
            obs_provider VARCHAR(100) NOT NULL,
            obs_model VARCHAR(100) NOT NULL,

            -- Derived outcome
            outcome_match VARCHAR(50) NOT NULL,
            prediction_accurate BOOLEAN NOT NULL,

            -- Context for analysis
            question_category VARCHAR(50) NOT NULL,
            question_difficulty VARCHAR(50) NOT NULL,
            question_text TEXT NOT NULL,
            domain_industry VARCHAR(100),

            -- Pillar scores at time of sample
            pillar_scores JSONB,

            -- Experiment tracking
            experiment_id UUID REFERENCES calibration_experiments(id) ON DELETE SET NULL,
            experiment_arm VARCHAR(50),

            -- Config used
            config_id UUID REFERENCES calibration_configs(id) ON DELETE SET NULL,

            -- Timestamp
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        )
        """
    )

    # Create indexes for calibration_samples
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_site_id ON calibration_samples(site_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_run_id ON calibration_samples(run_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_question_id ON calibration_samples(question_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_outcome_match ON calibration_samples(outcome_match)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_prediction_accurate ON calibration_samples(prediction_accurate)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_question_category ON calibration_samples(question_category)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_created_at ON calibration_samples(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_samples_experiment_id ON calibration_samples(experiment_id)"
    )

    # Create calibration_drift_alerts table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS calibration_drift_alerts (
            id UUID PRIMARY KEY,

            -- What drifted
            drift_type VARCHAR(50) NOT NULL,
            affected_pillar VARCHAR(50),

            -- Metrics
            expected_value FLOAT NOT NULL,
            observed_value FLOAT NOT NULL,
            drift_magnitude FLOAT NOT NULL,

            -- Context
            sample_window_start TIMESTAMP WITH TIME ZONE NOT NULL,
            sample_window_end TIMESTAMP WITH TIME ZONE NOT NULL,
            sample_count INTEGER NOT NULL,

            -- Baseline reference
            baseline_window_start TIMESTAMP WITH TIME ZONE,
            baseline_window_end TIMESTAMP WITH TIME ZONE,
            baseline_sample_count INTEGER,

            -- Status
            status VARCHAR(50) NOT NULL DEFAULT 'open',

            -- Resolution
            resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
            resolution_notes TEXT,
            resolution_action VARCHAR(100),

            -- Timestamps
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            acknowledged_at TIMESTAMP WITH TIME ZONE,
            resolved_at TIMESTAMP WITH TIME ZONE
        )
        """
    )

    # Create indexes for calibration_drift_alerts
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_drift_alerts_drift_type ON calibration_drift_alerts(drift_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_drift_alerts_status ON calibration_drift_alerts(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_calibration_drift_alerts_created_at ON calibration_drift_alerts(created_at)"
    )


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.execute("DROP TABLE IF EXISTS calibration_drift_alerts")
    op.execute("DROP TABLE IF EXISTS calibration_samples")
    op.execute("DROP TABLE IF EXISTS calibration_experiments")
    op.execute("DROP TABLE IF EXISTS calibration_configs")
