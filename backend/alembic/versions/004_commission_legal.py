"""Add legal compliance fields to commission_documents."""

revision = "004_commission_legal"
down_revision = "003_commission_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    op.add_column("commission_documents", sa.Column("analysis_legal", sa.JSON(), nullable=True))
    op.add_column("commission_documents", sa.Column("legal_compliance_score", sa.Float(), nullable=True))


def downgrade() -> None:
    from alembic import op

    op.drop_column("commission_documents", "legal_compliance_score")
    op.drop_column("commission_documents", "analysis_legal")
