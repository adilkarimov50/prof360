"""Basic tests for scoring and RBAC."""
from app.analytics.scoring import risk_level
from app.core.rbac import has_capability
from app.models.user import Role, User


def test_risk_levels():
    assert risk_level(0) == "Низкий"
    assert risk_level(5) == "Средний"
    assert risk_level(11) == "Высокий"
    assert risk_level(19) == "Критический"


def test_rbac_admin():
    user = User(username="a", full_name="A", hashed_password="x", role=Role.ADMIN)
    assert has_capability(user, "admin")
    assert has_capability(user, "ingest")


def test_rbac_district():
    user = User(username="d", full_name="D", hashed_password="x", role=Role.DISTRICT_PROSECUTOR)
    assert not has_capability(user, "admin")
    assert has_capability(user, "district_only")
