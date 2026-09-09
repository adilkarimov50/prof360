"""Справочники МКБ-10 и государственных мер поддержки."""

revision = "005_entitlements_icd"
down_revision = "004_commission_legal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # create_all в init_db


def downgrade() -> None:
    pass
