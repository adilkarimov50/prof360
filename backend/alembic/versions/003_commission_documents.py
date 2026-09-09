"""Commission documents table for prevention commission module."""

revision = "003_commission_documents"
down_revision = "002_user_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    op.create_table(
        "commission_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("district", sa.String(128), nullable=False),
        sa.Column("period", sa.String(64), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=True),
        sa.Column("stored_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("uploaded_by", sa.String(64), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("analysis_document", sa.JSON(), nullable=True),
        sa.Column("analysis_execution", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("effectiveness_score", sa.Float(), nullable=True),
        sa.Column("include_recommendation", sa.String(64), nullable=True),
    )
    op.create_index("ix_commission_documents_doc_type", "commission_documents", ["doc_type"])
    op.create_index("ix_commission_documents_district", "commission_documents", ["district"])
    op.create_index("ix_commission_documents_period", "commission_documents", ["period"])
    op.create_index("ix_commission_documents_uploaded_at", "commission_documents", ["uploaded_at"])
    op.create_index("ix_commission_documents_status", "commission_documents", ["status"])


def downgrade() -> None:
    from alembic import op

    op.drop_index("ix_commission_documents_status", "commission_documents")
    op.drop_index("ix_commission_documents_uploaded_at", "commission_documents")
    op.drop_index("ix_commission_documents_period", "commission_documents")
    op.drop_index("ix_commission_documents_district", "commission_documents")
    op.drop_index("ix_commission_documents_doc_type", "commission_documents")
    op.drop_table("commission_documents")
