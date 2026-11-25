from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

JWT_SECRET_PLACEHOLDER = "change-me"


class Settings(BaseSettings):
    app_env: str = "dev"
    enable_docs: bool = True
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/issues"
    storage_dir: str = "storage"
    max_upload_mb: int = 25

    jwt_secret: str = JWT_SECRET_PLACEHOLDER
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    session_absolute_days: int = 30
    refresh_reuse_grace_seconds: int = 10
    refresh_cookie_name: str = "refresh_token"
    refresh_cookie_secure: bool | None = None
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    refresh_cookie_path: str = "/api/auth"

    # 로그인 코드 해시에 섞는 서버 비밀값. 바꾸면 기존 코드로 로그인할 수 없으니 처음에 정하고 유지한다.
    login_code_pepper: str = ""

    # 데모 계정의 로그인 코드. 영문과 숫자를 모두 포함한 8자 이상. 비워 둔 계정은 만들지 않는다.
    seed_admin_code: str = ""
    seed_operator1_code: str = ""
    seed_operator2_code: str = ""
    seed_operator3_code: str = ""
    seed_operator4_code: str = ""
    seed_operator5_code: str = ""

    # Claude, GPT, Jev, 게이트웨이 STT 가 같은 키를 쓴다.
    # 기본 주소는 고려대 FactChat. 공개 factchat-cloud 호스트가 아니다.
    gateway_base_url: str = "https://factchat.mindlogic-kr-api.com/v1/gateway"
    gateway_api_key: str = ""
    gateway_timeout_seconds: float = 120
    gateway_max_retries: int = 3
    gateway_retry_backoff_seconds: float = 0.5
    claude_model: str = ""
    # 사실 추출 chat/completions 모델. 비우면 claude_model 을 쓴다.
    extract_model: str = "claude-opus-5-5"
    jev_model_version: str = "jev-1.14.0"

    stt_provider: Literal["mock", "gateway"] = "mock"
    # 학교 게이트웨이에서 v5·v6 를 확인했다. 같은 클립에서 전사가 같았고 기본은 v5.
    stt_model: Literal["stt-async-v5", "stt-async-v6"] = "stt-async-v5"
    stt_language: str = "ko"
    stt_diarization: bool = True
    stt_poll_interval_seconds: float = 2
    stt_poll_timeout_seconds: float = 300
    stt_max_audio_mb: int = 25
    ffmpeg_bin: str = "ffmpeg"
    extractor_provider: Literal["mock", "gateway_claude"] = "mock"
    classifier_provider: Literal["mock", "gateway_jev"] = "mock"

    # 임시값. tune 데이터로 보정 후 확정.
    cls_conf_high: float = 0.85
    cls_conf_low: float = 0.55
    stt_conf_min: float = 0.6

    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("refresh_cookie_secure", mode="before")
    @classmethod
    def empty_secure_is_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value

    @field_validator("jev_model_version")
    @classmethod
    def reject_latest_alias(cls, value: str) -> str:
        if value.strip().lower() == "latest":
            raise ValueError("JEV_MODEL_VERSION 에 latest 별칭을 쓸 수 없습니다.")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if not origins or "*" in origins:
            raise RuntimeError("CORS origin 은 명시 목록이어야 하며 '*' 는 허용하지 않습니다.")
        return origins

    @property
    def cookie_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.app_env != "dev"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def stt_max_audio_bytes(self) -> int:
        return self.stt_max_audio_mb * 1024 * 1024

    @property
    def access_token_expires_in(self) -> int:
        return self.access_token_expire_minutes * 60


def assert_runtime_secrets(settings: Settings) -> None:
    if settings.jwt_secret == JWT_SECRET_PLACEHOLDER:
        message = "JWT_SECRET 이 자리표시 값입니다. .env 에서 바꾼 뒤 실행하세요."
        if settings.app_env == "dev":
            logger.warning(message)
            return
        raise RuntimeError(message)


@lru_cache
def get_settings() -> Settings:
    return Settings()
