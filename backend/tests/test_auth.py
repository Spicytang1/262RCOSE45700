import uuid
from datetime import timedelta

import pytest
from app.auth.security import decode_access_token, encode_access_token, hash_refresh_token
from app.config import JWT_SECRET_PLACEHOLDER, Settings, assert_runtime_secrets
from app.main import create_app
from app.models import AuthSession, Base, RefreshToken, User
from app.models.base import utcnow
from app.services.login_code import LOGIN_CODE_RULE, digest_login_code, is_login_code
from app.services.users import add_user
from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_CODE,
    OPERATOR_CODE,
    OTHER_CODE,
    auth_header,
    login,
    refresh_cookie,
    refresh_with,
)

LOGIN_FAILED = "로그인 코드가 올바르지 않습니다"


def test_code_only_login_and_same_failure_message(client: TestClient, app) -> None:
    ok = login(client, OPERATOR_CODE)
    body = ok.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == app.state.settings.access_token_expires_in
    assert body["user"]["display_name"] == "오퍼레이터1"
    assert body["user"]["role"] == "operator"
    for secret in ("username", "employee_number", "code_digest", "password"):
        assert secret not in ok.text
    cookie = ok.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/auth" in cookie
    attributes = cookie.split(";", maxsplit=1)[1]
    assert "secure" not in attributes

    form_login = client.post("/api/auth/login", data={"code": OPERATOR_CODE})
    assert form_login.status_code == 422

    created = app.state.session_factory()
    inactive = add_user(created, app.state.settings, code="inactive9", display_name="중지", role="operator")
    inactive.is_active = False
    created.commit()
    created.close()
    failures = [
        client.post("/api/auth/login", json={"code": code})
        for code in (
            "nobody123",
            OPERATOR_CODE.upper(),
            "short1",
            "onlyletters",
            "12345678",
            "inactive9",
            "오퍼레이터1",
        )
    ]
    assert {failure.status_code for failure in failures} == {401}
    assert {failure.json()["detail"] for failure in failures} == {LOGIN_FAILED}


def test_login_code_format_rules() -> None:
    assert is_login_code("operator1")
    assert is_login_code("A1b2C3d4")
    assert not is_login_code("operator")
    assert not is_login_code("12345678")
    assert not is_login_code("op1")
    assert not is_login_code("operator-1")
    assert not is_login_code("operator1" * 9)


def test_admin_creates_user_and_rejects_bad_or_duplicate_code(client: TestClient) -> None:
    admin = auth_header(login(client, ADMIN_CODE).json()["access_token"])
    created = client.post(
        "/api/users", json={"code": "operator6", "display_name": "오퍼레이터6", "role": "operator"}, headers=admin
    )
    assert created.status_code == 201, created.text
    assert set(created.json()) == {"id", "display_name", "role", "is_active"}
    assert login(client, "operator6").json()["user"]["display_name"] == "오퍼레이터6"

    duplicate = client.post(
        "/api/users", json={"code": "operator6", "display_name": "중복", "role": "operator"}, headers=admin
    )
    assert duplicate.status_code == 409
    weak = client.post(
        "/api/users", json={"code": "operator", "display_name": "약함", "role": "operator"}, headers=admin
    )
    assert weak.status_code == 422
    assert weak.json()["detail"] == LOGIN_CODE_RULE
    operator = auth_header(login(client, OPERATOR_CODE).json()["access_token"])
    assert (
        client.post(
            "/api/users", json={"code": "operator7", "display_name": "x", "role": "operator"}, headers=operator
        ).status_code
        == 403
    )


def test_admin_resets_code_and_old_sessions_end(client: TestClient, accounts) -> None:
    old = login(client, OPERATOR_CODE).json()["access_token"]
    admin = auth_header(login(client, ADMIN_CODE).json()["access_token"])
    reset = client.patch(f"/api/users/{accounts['operator']}", json={"code": "operator9"}, headers=admin)
    assert reset.status_code == 200, reset.text
    assert client.get("/api/auth/me", headers=auth_header(old)).status_code == 401
    assert client.post("/api/auth/login", json={"code": OPERATOR_CODE}).status_code == 401
    assert login(client, "operator9").status_code == 200
    taken = client.patch(f"/api/users/{accounts['operator']}", json={"code": OTHER_CODE}, headers=admin)
    assert taken.status_code == 409


def test_self_service_name_and_code_change(client: TestClient) -> None:
    token = login(client, OPERATOR_CODE).json()["access_token"]
    headers = auth_header(token)
    renamed = client.patch("/api/auth/me", json={"display_name": "김감독"}, headers=headers)
    assert renamed.status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["display_name"] == "김감독"
    assert (
        client.patch("/api/auth/me", json={"role": "admin", "display_name": "김감독"}, headers=headers).json()["role"]
        == "operator"
    )

    wrong = client.put(
        "/api/auth/me/code", json={"current_code": "wrongcode1", "new_code": "newcode123"}, headers=headers
    )
    assert wrong.status_code == 403
    taken = client.put(
        "/api/auth/me/code", json={"current_code": OPERATOR_CODE, "new_code": OTHER_CODE}, headers=headers
    )
    assert taken.status_code == 409
    weak = client.put(
        "/api/auth/me/code", json={"current_code": OPERATOR_CODE, "new_code": "weakcode"}, headers=headers
    )
    assert weak.status_code == 422
    changed = client.put(
        "/api/auth/me/code", json={"current_code": OPERATOR_CODE, "new_code": "newcode123"}, headers=headers
    )
    assert changed.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.post("/api/auth/login", json={"code": OPERATOR_CODE}).status_code == 401
    assert login(client, "newcode123").status_code == 200


def test_token_missing_expired_and_forged(client: TestClient, app) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth_header("not-a-token")).status_code == 401
    logged = login(client, OPERATOR_CODE)
    payload = decode_access_token(logged.json()["access_token"], app.state.settings)
    assert payload is not None
    expired = encode_access_token(
        user_id=str(payload["sub"]),
        session_id=str(payload["sid"]),
        settings=app.state.settings,
        issued_at=int(utcnow().timestamp()) - 3600,
        expires_at=int(utcnow().timestamp()) - 10,
    )
    assert client.get("/api/auth/me", headers=auth_header(expired)).status_code == 401


def test_refresh_rotation_grace_and_reuse(client: TestClient, app) -> None:
    first = login(client, OPERATOR_CODE)
    assert "refresh_token" not in first.json()
    raw_first = refresh_cookie(first)
    access_first = first.json()["access_token"]
    rotated = refresh_with(client, raw_first)
    assert rotated.status_code == 200, rotated.text
    assert "refresh_token" not in rotated.json()
    access_second = rotated.json()["access_token"]
    raw_second = refresh_cookie(rotated)
    assert raw_second != raw_first

    reused = refresh_with(client, raw_first)
    assert reused.status_code == 401
    assert client.get("/api/auth/me", headers=auth_header(access_first)).status_code == 200

    db = app.state.session_factory()
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw_first)).one()
    row.used_at = utcnow() - timedelta(seconds=app.state.settings.refresh_reuse_grace_seconds + 5)
    db.commit()
    db.close()

    stolen = refresh_with(client, raw_first)
    assert stolen.status_code == 401
    assert client.get("/api/auth/me", headers=auth_header(access_first)).status_code == 401
    assert client.get("/api/auth/me", headers=auth_header(access_second)).status_code == 401

    assert refresh_with(client, raw_second).status_code == 401


def test_logout_is_immediate_idempotent_and_accepts_refresh_cookie(client: TestClient, app) -> None:
    logged = login(client, OPERATOR_CODE)
    access = logged.json()["access_token"]
    payload = decode_access_token(access, app.state.settings)
    assert payload is not None
    expired = encode_access_token(
        user_id=str(payload["sub"]),
        session_id=str(payload["sid"]),
        settings=app.state.settings,
        issued_at=int(utcnow().timestamp()) - 120,
        expires_at=int(utcnow().timestamp()) - 30,
    )
    assert client.post("/api/auth/logout", headers=auth_header(expired)).status_code == 204
    assert client.get("/api/auth/me", headers=auth_header(access)).status_code == 401
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/logout", headers=auth_header(access)).status_code == 204


def test_logout_all_revokes_every_session(client: TestClient) -> None:
    first = login(client, OPERATOR_CODE)
    second = login(client, OPERATOR_CODE)
    assert client.post("/api/auth/logout-all", headers=auth_header(first.json()["access_token"])).status_code == 204
    assert client.get("/api/auth/me", headers=auth_header(first.json()["access_token"])).status_code == 401
    assert client.get("/api/auth/me", headers=auth_header(second.json()["access_token"])).status_code == 401


def test_deactivation_revokes_existing_session(client: TestClient, accounts) -> None:
    logged = login(client, OPERATOR_CODE)
    admin = login(client, ADMIN_CODE)
    response = client.patch(
        f"/api/users/{accounts['operator']}",
        json={"is_active": False},
        headers=auth_header(admin.json()["access_token"]),
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=auth_header(logged.json()["access_token"])).status_code == 401
    blocked = client.post("/api/auth/login", json={"code": OPERATOR_CODE})
    assert blocked.status_code == 401
    assert blocked.json()["detail"] == LOGIN_FAILED


def test_absolute_session_lifetime_blocks_refresh(client: TestClient, app) -> None:
    logged = login(client, OPERATOR_CODE)
    payload = decode_access_token(logged.json()["access_token"], app.state.settings)
    assert payload is not None
    db = app.state.session_factory()
    session = db.get(AuthSession, uuid.UUID(str(payload["sid"])))
    assert session is not None
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    db.close()
    assert refresh_with(client, refresh_cookie(logged)).status_code == 401


def test_secrets_are_hashed_and_hidden(client: TestClient, app) -> None:
    logged = login(client, OPERATOR_CODE)
    db = app.state.session_factory()
    user = db.query(User).filter(User.code_digest == digest_login_code(OPERATOR_CODE, app.state.settings)).one()
    raw_refresh = refresh_cookie(logged)
    digest = hash_refresh_token(raw_refresh)
    token = db.query(RefreshToken).filter(RefreshToken.token_hash == digest).one()
    assert OPERATOR_CODE not in user.code_digest
    assert len(user.code_digest) == 64
    assert token.token_hash != raw_refresh
    assert len(token.token_hash) == 64
    db.close()
    admin_token = login(client, ADMIN_CODE).json()["access_token"]
    listed = client.get("/api/users", headers=auth_header(admin_token))
    assert "code_digest" not in listed.text
    assert OPERATOR_CODE not in listed.text


def test_pepper_changes_stored_digest(settings) -> None:
    peppered = settings.model_copy(update={"login_code_pepper": "server-secret"})
    assert digest_login_code(OPERATOR_CODE, settings) != digest_login_code(OPERATOR_CODE, peppered)
    assert digest_login_code(OPERATOR_CODE, peppered) == digest_login_code(OPERATOR_CODE, peppered)


def test_secure_cookie_outside_dev(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="prod",
        jwt_secret="prod-secret-value-should-be-long-enough",
        database_url=f"sqlite:///{tmp_path}/prod.db",
        storage_dir=str(tmp_path / "storage"),
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    db = application.state.session_factory()
    add_user(db, application.state.settings, code=ADMIN_CODE, display_name="관리자", role="admin")
    db.commit()
    db.close()
    with TestClient(application) as prod_client:
        response = prod_client.post("/api/auth/login", json={"code": ADMIN_CODE})
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_placeholder_secret_guard(tmp_path, caplog) -> None:
    dev = Settings(_env_file=None, app_env="dev", jwt_secret=JWT_SECRET_PLACEHOLDER, database_url="sqlite://")
    with caplog.at_level("WARNING"):
        assert_runtime_secrets(dev)
    assert "JWT_SECRET" in caplog.text

    blocked = Settings(
        _env_file=None,
        app_env="prod",
        jwt_secret=JWT_SECRET_PLACEHOLDER,
        database_url=f"sqlite:///{tmp_path}/blocked.db",
    )
    application = create_app(blocked)
    with pytest.raises(RuntimeError):
        with TestClient(application):
            pass
