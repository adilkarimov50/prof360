"""Initial schema baseline — use for fresh installs; existing DB uses _ensure_columns."""

revision = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline managed by SQLAlchemy create_all + incremental alters in init_db.
    pass


def downgrade() -> None:
    pass
