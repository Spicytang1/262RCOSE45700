from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.errors import (
    CODE_DUPLICATE,
    CODE_MISMATCH,
    INVALID_AUTH,
    LOGIN_FAILED,
    RESP_401,
    RESP_422,
    error_response,
)
from app.auth.cookies import clear_refresh_cookie, set_refresh_cookie
from app.auth.deps import get_current_user, get_db, get_settings, issue_access_token, refresh_cookie_scheme
from app.auth.security import decode_access_token
from app.auth.sessions import create_session, get_session, revoke_all_sessions, revoke_session
from app.auth.tokens import (
    RefreshRejectedError,
    issue_refresh_token,
    rotate_refresh_token,
    session_id_for_refresh_token,
)
from app.config import Settings
from app.models import User
from app.models.base import utcnow
from app.schemas.auth import CodeChange, LoginRequest, MeUpdate, TokenResponse, UserPublic
from app.services.login_code import LOGIN_CODE_RULE
from app.services.users import DuplicateLoginCodeError, InvalidLoginCodeError, change_login_code, find_user_by_code

router = APIRouter()


def _token_response(user: User, session_id: uuid.UUID, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=issue_access_token(user, session_id, settings),
        token_type="bearer",
        expires_in=settings.access_token_expires_in,
        user=UserPublic.model_validate(user),
    )


def _unauthorized(settings: Settings) -> JSONResponse:
    response = JSONResponse(status_code=401, content={"detail": INVALID_AUTH})
    clear_refresh_cookie(response, settings)
    return response


@router.post(
    "/login",
    operation_id="login",
    response_model=TokenResponse,
    response_model_exclude_none=True,
    summary="로그인",
    description=(
        "로그인 코드 하나로 로그인합니다. 아이디와 비밀번호를 따로 받지 않습니다. "
        "성공하면 access token 을 본문으로, refresh token 을 HttpOnly 쿠키로 내려줍니다. "
        "코드가 없거나 틀렸거나 비활성 계정이면 이유와 관계없이 같은 401 입니다."
    ),
    responses={401: error_response(LOGIN_FAILED), **RESP_422},
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    user = find_user_by_code(db, settings, payload.code)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail=LOGIN_FAILED)
    session = create_session(db, user, settings, user_agent=request.headers.get("user-agent"))
    raw_refresh = issue_refresh_token(db, session, settings)
    db.commit()
    set_refresh_cookie(response, settings, raw_refresh)
    return _token_response(user, session.id, settings)


@router.post(
    "/refresh",
    operation_id="refreshToken",
    response_model=TokenResponse,
    response_model_exclude_none=True,
    summary="access token 갱신",
    description=(
        "본문이 없습니다. refresh 쿠키(HttpOnly)를 회전하고 새 access token 을 발급합니다. "
        "요청에 `credentials: 'include'` 가 필요합니다. 동시에 여러 번 보내지 말고 한 번만 보냅니다. "
        "재사용이 유예 시간을 넘으면 세션을 폐기하고 401 을 돌려줍니다."
    ),
    responses=RESP_401,
    dependencies=[Security(refresh_cookie_scheme)],
)
def refresh(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse | JSONResponse:
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        return _unauthorized(settings)
    try:
        user, session, rotated = rotate_refresh_token(db, raw, settings)
    except RefreshRejectedError:
        db.commit()
        return _unauthorized(settings)
    db.commit()
    body = _token_response(user, session.id, settings)
    response = JSONResponse(status_code=200, content=body.model_dump(mode="json", exclude_none=True))
    set_refresh_cookie(response, settings, rotated)
    return response


@router.post(
    "/logout",
    operation_id="logout",
    status_code=204,
    summary="로그아웃",
    description="유효한 access token 또는 refresh 쿠키 중 하나만 있어도 현재 세션을 폐기합니다. 항상 204 입니다.",
)
def logout(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    session_id: uuid.UUID | None = None
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        payload = decode_access_token(header.split(" ", 1)[1], settings)
        if payload and payload.get("sid"):
            try:
                session_id = uuid.UUID(str(payload["sid"]))
            except ValueError:
                session_id = None
    if session_id is None:
        raw = request.cookies.get(settings.refresh_cookie_name)
        if raw:
            session_id = session_id_for_refresh_token(db, raw)
    if session_id is not None:
        session = get_session(db, session_id)
        if session is not None:
            revoke_session(db, session, "logout", utcnow())
            db.commit()
    response = Response(status_code=204)
    clear_refresh_cookie(response, settings)
    return response


@router.post(
    "/logout-all",
    operation_id="logoutAll",
    status_code=204,
    summary="모든 세션 로그아웃",
    description="현재 사용자의 모든 세션을 폐기합니다.",
    responses=RESP_401,
)
def logout_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    revoke_all_sessions(db, user.id, "logout_all", utcnow())
    db.commit()
    response = Response(status_code=204)
    clear_refresh_cookie(response, settings)
    return response


@router.get(
    "/me",
    operation_id="getMe",
    response_model=UserPublic,
    summary="현재 사용자",
    description="access token 의 세션이 유효하면 현재 사용자 정보를 반환합니다. 권한 판단에 쓰는 역할은 DB 값입니다.",
    responses=RESP_401,
)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch(
    "/me",
    operation_id="updateMe",
    response_model=UserPublic,
    summary="내 표시 이름 변경",
    description="본인의 표시 이름만 바꿉니다. 역할과 활성 상태는 관리자만 `PATCH /api/users/{user_id}` 로 바꿉니다.",
    responses={**RESP_401, **RESP_422},
)
def update_me(
    payload: MeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    user.display_name = payload.display_name
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put(
    "/me/code",
    operation_id="changeMyCode",
    status_code=204,
    summary="내 로그인 코드 변경",
    description=(
        "현재 코드를 확인한 뒤 새 코드로 바꿉니다. 성공하면 모든 세션이 폐기되므로 새 코드로 다시 로그인해야 합니다. "
        "새 코드는 영문과 숫자를 모두 포함한 8자 이상이어야 합니다."
    ),
    responses={
        **RESP_401,
        403: error_response(CODE_MISMATCH),
        409: error_response(CODE_DUPLICATE),
        **RESP_422,
    },
)
def change_my_code(
    payload: CodeChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    current = find_user_by_code(db, settings, payload.current_code)
    if current is None or current.id != user.id:
        raise HTTPException(status_code=403, detail=CODE_MISMATCH)
    try:
        change_login_code(db, settings, user, payload.new_code)
    except InvalidLoginCodeError as exc:
        raise HTTPException(status_code=422, detail=LOGIN_CODE_RULE) from exc
    except DuplicateLoginCodeError as exc:
        raise HTTPException(status_code=409, detail=CODE_DUPLICATE) from exc
    db.commit()
    response = Response(status_code=204)
    clear_refresh_cookie(response, settings)
    return response
