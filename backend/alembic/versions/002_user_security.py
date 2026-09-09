"""Add token_version and must_change_password to users."""

revision = "002_user_security"
down_revision = "001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    from alembic import op

    op.drop_column("users", "must_change_password")
    op.drop_column("users", "token_version")
