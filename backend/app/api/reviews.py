from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.errors import RECORDING_NOT_FOUND, RESP_401, RESP_422, error_response
from app.auth.deps import get_current_user, get_db
from app.models import User
from app.schemas.reviews import ReviewOut, ReviewWrite
from app.services.reviews import get_review, list_reviews, save_review, to_review, visible_recording

router = APIRouter()

RESP_RECORDING_404 = {404: error_response(RECORDING_NOT_FOUND)}


@router.get(
    "",
    response_model=list[ReviewOut],
    summary="검토 목록",
    description="오퍼레이터는 자신의 녹음 검토만, 관리자는 전체를 봅니다.",
    responses={**RESP_401},
)
def get_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ReviewOut]:
    return [to_review(review) for review in list_reviews(db, user)]


@router.get(
    "/{recording_id}",
    response_model=ReviewOut,
    summary="검토 조회",
    description="녹음이 없거나 다른 오퍼레이터의 녹음이면 404 입니다. 검토를 한 번도 저장하지 않아도 404 입니다.",
    responses={**RESP_401, **RESP_RECORDING_404},
)
def get_recording_review(
    recording_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    review = get_review(db, recording_id, user)
    if review is None:
        raise HTTPException(status_code=404, detail=RECORDING_NOT_FOUND)
    return to_review(review)


@router.put(
    "/{recording_id}",
    response_model=ReviewOut,
    summary="검토 저장",
    description="제목, 상태, 정리 항목, 기타 입력, 메모를 통째로 저장합니다. 음성 원본과 AI 추출값은 바꾸지 않습니다.",
    responses={**RESP_401, **RESP_RECORDING_404, **RESP_422},
)
def put_recording_review(
    recording_id: uuid.UUID,
    payload: ReviewWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    recording = visible_recording(db, recording_id, user)
    if recording is None:
        raise HTTPException(status_code=404, detail=RECORDING_NOT_FOUND)
    return to_review(save_review(db, recording, payload))
