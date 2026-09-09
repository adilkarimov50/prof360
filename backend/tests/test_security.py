"""Security and token tests."""
from app.core.rbac import allow_pii, has_capability
from app.core.security import create_access_token, decode_token
from app.models.user import Role, User


def test_token_version_in_payload():
    token = create_access_token("user1", "admin", token_version=3)
    payload = decode_token(token)
    assert payload is not None
    assert payload["tv"] == 3
    assert payload["type"] == "access"


def test_allow_pii_minors_flag():
    user = User(username="u", full_name="U", hashed_password="x", role=Role.ANALYST, can_access_minors=True)
    assert allow_pii(user)


def test_allow_pii_osint_denied():
    user = User(username="o", full_name="O", hashed_password="x", role=Role.OSINT_USER)
    assert not allow_pii(user)


def test_rbac_ingest_analyst():
    user = User(username="a", full_name="A", hashed_password="x", role=Role.ANALYST)
    assert has_capability(user, "ingest")
