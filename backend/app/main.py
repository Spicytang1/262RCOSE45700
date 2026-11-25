from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.drives import router as drives_router
from app.api.issues import router as issues_router
from app.api.recordings import router as recordings_router
from app.api.reviews import router as reviews_router
from app.api.summary import router as summary_router
from app.api.taxonomy import router as taxonomy_router
from app.api.users import router as users_router
from app.config import Settings, assert_runtime_secrets, get_settings
from app.db import make_engine, make_session_factory
from app.schemas.common import HealthOut

OPENAPI_TAGS = [
    {"name": "system", "description": "서버 상태"},
    {"name": "auth", "description": "로그인, 토큰 갱신, 로그아웃"},
    {"name": "users", "description": "관리자용 사용자 관리"},
    {"name": "recordings", "description": "녹음 업로드와 파이프라인"},
    {"name": "drives", "description": "운행 회차 시작과 종료"},
    {"name": "reviews", "description": "녹음 검토 저장"},
    {"name": "issues", "description": "이슈 조회, 오퍼레이터 확인, 휴지통과 영구 삭제"},
    {"name": "taxonomy", "description": "이슈 분류 보기(유형·심각도·안내 항목)와 한국어 이름"},
    {"name": "summary", "description": "관리자용 주간 요약"},
]

DESCRIPTION = """
오퍼레이터 음성 기반 주행 이슈 리포팅 API.

녹음을 텍스트로 바꾸고, 사실과 사건 유형을 정리해 저장한 뒤 주간 요약을 만듭니다.

## 인증 사용법
1. `POST /api/auth/login` 에 `{"code": "..."}` 를 보냅니다.
   로그인 코드(영문+숫자 8자 이상) 하나가 아이디와 비밀번호를 겸합니다.
2. 응답의 `access_token` 을 `Authorization: Bearer <token>` 으로 보내 보호된 API 를 호출합니다.
   Swagger 에서는 Authorize 에 토큰을 붙여 넣습니다.
3. access token 이 만료되면 `POST /api/auth/refresh` 로 갱신합니다. refresh token 은 HttpOnly 쿠키라서
   브라우저 요청에 `credentials: 'include'` 가 필요하고, 서버 CORS 허용 출처에 프런트 주소가 있어야 합니다.
4. `POST /api/auth/logout` 으로 현재 세션을 끝냅니다.

## 공통 규칙
- 시각은 ISO 8601 이며 서버 값은 UTC 입니다. ID 는 UUID 입니다.
- 오류는 `{"detail": "화면에 보여 줘도 되는 문장"}` 입니다. 형식 검증 실패(422)만 `detail` 이 배열입니다.
- 오퍼레이터는 본인 데이터만, 관리자는 전체를 봅니다. 남의 데이터는 403 이 아니라 404 로 숨깁니다.
- 이슈 분류 값(유형, 심각도, 안내 항목)은 key 로 오갑니다. 한국어 이름은 `GET /api/taxonomy` 에서 받습니다.

## 이슈의 세 가지 상태
정상 → 휴지통 → 영구 삭제.
`POST /api/issues/{id}/trash` 로 휴지통에 넣고(`trashed_at` 이 채워짐), `POST /api/issues/{id}/restore` 로 되돌립니다.
휴지통에 있는 이슈만 `DELETE /api/issues/{id}` 로 영구 삭제할 수 있습니다.
이때 녹음 원본과 전사·검토도 함께 지워져 되돌릴 수 없습니다.
휴지통 이슈는 기본 목록, 주간 요약, 검토 목록에서 빠집니다.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        assert_runtime_secrets(app.state.settings)
        yield

    app = FastAPI(
        title="주행 이슈 리포팅 API",
        version="0.1.0",
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if active.enable_docs else None,
        redoc_url="/redoc" if active.enable_docs else None,
        swagger_ui_parameters={"persistAuthorization": True},
        lifespan=lifespan,
    )
    app.state.settings = active
    app.state.engine = make_engine(active)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(users_router, prefix="/api/users", tags=["users"])
    app.include_router(recordings_router, prefix="/api/recordings", tags=["recordings"])
    app.include_router(drives_router, prefix="/api/drives", tags=["drives"])
    app.include_router(reviews_router, prefix="/api/reviews", tags=["reviews"])
    app.include_router(issues_router, prefix="/api/issues", tags=["issues"])
    app.include_router(summary_router, prefix="/api/summary", tags=["summary"])
    app.include_router(taxonomy_router, prefix="/api/taxonomy", tags=["taxonomy"])

    @app.get(
        "/health",
        operation_id="getHealth",
        response_model=HealthOut,
        tags=["system"],
        summary="서버 상태 확인",
        description="프로세스 상태를 확인합니다. 인증이 필요 없습니다.",
    )
    def health() -> HealthOut:
        return HealthOut(status="ok")

    return app


app = create_app()
