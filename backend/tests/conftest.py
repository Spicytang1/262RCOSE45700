from __future__ import annotations

import uuid

import pytest
from app.config import Settings
from app.main import create_app
from app.models import Base
from app.services.users import add_user
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

ADMIN_CODE = "admin0001"
OPERATOR_CODE = "operator1"
OTHER_CODE = "operator2"


def build_test_settings(tmp_path) -> Settings:
    """생성자 값이 프로세스 환경의 provider 보다 우선한다."""
    return Settings(
        _env_file=None,
        app_env="dev",
        database_url=f"sqlite:///{tmp_path}/app.db",
        storage_dir=str(tmp_path / "storage"),
        jwt_secret="test-secret-value-should-be-long-enough",
        cors_origins="http://localhost:5173",
        stt_provider="mock",
        extractor_provider="mock",
        classifier_provider="mock",
    )


@pytest.fixture
def settings(tmp_path) -> Settings:
    return build_test_settings(tmp_path)


@pytest.fixture
def app(settings: Settings):
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    return application


@pytest.fixture
def db(app) -> Session:
    session = app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def accounts(db: Session, settings: Settings) -> dict[str, uuid.UUID]:
    admin = add_user(db, settings, code=ADMIN_CODE, display_name="관리자", role="admin")
    operator = add_user(db, settings, code=OPERATOR_CODE, display_name="오퍼레이터1", role="operator")
    other = add_user(db, settings, code=OTHER_CODE, display_name="오퍼레이터2", role="operator")
    db.commit()
    return {"admin": admin.id, "operator": operator.id, "other": other.id}


@pytest.fixture
def client(app, accounts):
    del accounts
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, code: str):
    response = client.post("/api/auth/login", json={"code": code})
    assert response.status_code == 200, response.text
    return response


def refresh_with(client: TestClient, raw_token: str):
    """쿠키 저장소를 비우고 지정한 refresh 원문만 쿠키 헤더로 보낸다."""
    client.cookies.clear()
    return client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={raw_token}"})


def refresh_cookie(response) -> str:
    value = response.cookies.get("refresh_token")
    assert value, response.headers
    return value


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def wav_bytes() -> bytes:
    return (
        b"RIFF"
        + (36).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little")
        + (8000).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (8).to_bytes(2, "little")
        + b"data"
        + (0).to_bytes(4, "little")
    )


def upload(client: TestClient, token: str, **form):
    form.setdefault("latitude", "37.5")
    form.setdefault("longitude", "127.0")
    return client.post(
        "/api/recordings",
        files={"audio": ("sample.wav", wav_bytes(), "audio/wav")},
        data=form,
        headers=auth_header(token),
    )
