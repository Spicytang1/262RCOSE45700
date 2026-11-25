from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import (
    CODE_DUPLICATE,
    RESP_401,
    RESP_403,
    RESP_422,
    USER_NOT_FOUND,
    error_response,
)
from app.auth.deps import get_db, get_settings, require_role
from app.config import Settings
from app.models import User
from app.schemas.auth import UserCreate, UserPublic, UserUpdate
from app.services.login_code import LOGIN_CODE_RULE
from app.services.users import DuplicateLoginCodeError, InvalidLoginCodeError, add_user, update_user

router = APIRouter()


@router.post(
    "",
    operation_id="createUser",
    response_model=UserPublic,
    status_code=201,
    summary="사용자 생성",
    description=(
        "관리자가 계정을 만듭니다. 셀프 가입은 없습니다. 로그인 코드는 영문과 숫자를 모두 포함한 8자 이상입니다."
    ),
    responses={**RESP_401, **RESP_403, 409: error_response(CODE_DUPLICATE), **RESP_422},
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(require_role("admin")),
) -> User:
    try:
        user = add_user(db, settings, code=payload.code, display_name=payload.display_name, role=payload.role)
    except InvalidLoginCodeError as exc:
        raise HTTPException(status_code=422, detail=LOGIN_CODE_RULE) from exc
    except DuplicateLoginCodeError as exc:
        raise HTTPException(status_code=409, detail=CODE_DUPLICATE) from exc
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "",
    operation_id="listUsers",
    response_model=list[UserPublic],
    summary="사용자 목록",
    description="관리자가 전체 사용자를 조회합니다. 로그인 코드는 저장하지 않으므로 응답에 없습니다.",
    responses={**RESP_401, **RESP_403},
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.asc())).all())


@router.patch(
    "/{user_id}",
    operation_id="updateUser",
    response_model=UserPublic,
    summary="사용자 수정",
    description=(
        "이름, 역할, 활성 상태, 로그인 코드를 수정합니다. "
        "비활성화하거나 코드를 바꾸면 해당 사용자의 세션을 모두 폐기합니다."
    ),
    responses={
        **RESP_401,
        **RESP_403,
        404: error_response(USER_NOT_FOUND),
        409: error_response(CODE_DUPLICATE),
        **RESP_422,
    },
)
def patch_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(require_role("admin")),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    try:
        return update_user(db, settings, user, payload)
    except InvalidLoginCodeError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=LOGIN_CODE_RULE) from exc
    except DuplicateLoginCodeError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=CODE_DUPLICATE) from exc
