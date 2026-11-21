from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.errors import DRIVE_NOT_FOUND, RESP_401, error_response
from app.auth.deps import get_current_user, get_db
from app.models import User
from app.schemas.drives import DriveOut
from app.services.drives import end_drive, get_drive, list_drives, start_drive, to_drive

router = APIRouter()

RESP_DRIVE_404 = {404: error_response(DRIVE_NOT_FOUND)}


@router.get(
    "",
    response_model=list[DriveOut],
    summary="운행 회차 목록",
    description="오퍼레이터는 자신의 회차만, 관리자는 전체를 봅니다. 최신 시작이 먼저입니다.",
    responses={**RESP_401},
)
def get_drives(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DriveOut]:
    return [to_drive(drive) for drive in list_drives(db, user)]


@router.post(
    "",
    response_model=DriveOut,
    summary="운행 시작",
    description="진행 중인 회차가 있으면 새 번호를 만들지 않고 그 회차를 돌려줍니다.",
    responses={**RESP_401},
)
def post_drive(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DriveOut:
    return to_drive(start_drive(db, user))


@router.post(
    "/{drive_id}/end",
    response_model=DriveOut,
    summary="운행 종료",
    description="이미 끝난 회차도 같은 종료 시각을 유지한 채 성공합니다. 다른 오퍼레이터의 회차는 404 입니다.",
    responses={**RESP_401, **RESP_DRIVE_404},
)
def post_end_drive(
    drive_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DriveOut:
    drive = get_drive(db, drive_id, user)
    if drive is None:
        raise HTTPException(status_code=404, detail=DRIVE_NOT_FOUND)
    return to_drive(end_drive(db, drive))
