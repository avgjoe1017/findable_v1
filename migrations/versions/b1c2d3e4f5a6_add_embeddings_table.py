"""add_embeddings_table

Revision ID: b1c2d3e4f5a6
Revises: 4556f7a9cae5
Create Date: 2026-01-31 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "4556f7a9cae5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create embeddings table with pgvector support
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            id UUID PRIMARY KEY,
            chunk_id UUID NOT NULL,
            page_id UUID NOT NULL,
            site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,

            content TEXT NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            embedding vector(384),

            model_name VARCHAR(100) NOT NULL,
            dimensions INTEGER NOT NULL,

            chunk_index INTEGER DEFAULT 0,
            chunk_type VARCHAR(50) DEFAULT 'text',
            heading_context TEXT,
            position_ratio FLOAT DEFAULT 0.0,
            source_url TEXT,
            page_title TEXT,

            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,

            CONSTRAINT unique_chunk_site UNIQUE (content_hash, site_id)
        )
        """
    )

    # Create indexes for lookups
    op.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_site_id ON embeddings(site_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_page_id ON embeddings(page_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_content_hash ON embeddings(content_hash)")

    # Create vector index for similarity search (IVFFlat)
    # Note: IVFFlat requires data to exist before creating the index efficiently
    # For initial setup, we create it anyway - can be recreated after data load
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_content_hash")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_page_id")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_site_id")
    op.execute("DROP TABLE IF EXISTS embeddings")
