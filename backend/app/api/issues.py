from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.errors import (
    ISSUE_NOT_FOUND,
    ISSUE_NOT_TRASHED,
    ISSUE_TRASHED,
    RESP_401,
    RESP_404,
    RESP_422,
    error_response,
)
from app.auth.deps import get_current_user, get_db
from app.models import User
from app.schemas.issues import EventTypeKey, IssueOut, IssueStatus, IssueUpdate
from app.services.issues import (
    NotTrashedError,
    apply_issue_update,
    get_visible_issue,
    list_visible_issues,
    purge_issue,
    restore_issue,
    to_issue_out,
    trash_issue,
)

AUDIO_MEDIA_TYPES = ("audio/wav", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg", "application/octet-stream")
AUDIO_200 = {
    200: {
        "description": "원본 음성 바이트. 형식은 업로드한 파일 그대로이고 Content-Type 으로 구분합니다.",
        "content": {media: {"schema": {"type": "string", "format": "binary"}} for media in AUDIO_MEDIA_TYPES},
    }
}

router = APIRouter()


def _require_issue(db: Session, issue_id: uuid.UUID, user: User):
    issue = get_visible_issue(db, issue_id, user)
    if issue is None:
        raise HTTPException(status_code=404, detail=ISSUE_NOT_FOUND)
    return issue


@router.get(
    "",
    operation_id="listIssues",
    response_model=list[IssueOut],
    summary="이슈 목록",
    description=(
        "오퍼레이터는 자신의 이슈만, 관리자는 전체를 봅니다. 기본은 정상 이슈이고, "
        "`trashed=true` 면 휴지통에 있는 이슈만 휴지통에 넣은 시각 최신순으로 줍니다."
    ),
    responses={**RESP_401, **RESP_422},
)
def list_issues(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: IssueStatus | None = None,
    event_type: EventTypeKey | None = None,
    from_: datetime | None = Query(default=None, alias="from", description="녹음 시각이 이 시각 이상"),
    to: datetime | None = Query(default=None, description="녹음 시각이 이 시각 미만"),
    trashed: bool = Query(default=False, description="true 면 휴지통 이슈만, false 면 정상 이슈만"),
) -> list[IssueOut]:
    issues = list_visible_issues(db, user, status=status, event_type=event_type, start=from_, end=to, trashed=trashed)
    return [to_issue_out(issue) for issue in issues]


@router.get(
    "/{issue_id}",
    operation_id="getIssue",
    response_model=IssueOut,
    summary="이슈 상세",
    description="휴지통에 있는 이슈도 조회됩니다(`trashed_at` 이 채워져 옵니다). 다른 오퍼레이터의 이슈는 404 입니다.",
    responses={**RESP_401, **RESP_404, **RESP_422},
)
def get_issue(
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueOut:
    return to_issue_out(_require_issue(db, issue_id, user))


@router.patch(
    "/{issue_id}",
    operation_id="updateIssue",
    response_model=IssueOut,
    summary="이슈 확인·수정",
    description=(
        "오퍼레이터가 값을 고치고 확정하면 final_extraction 과 issue_edits 에 수정자와 함께 남습니다. "
        "휴지통에 있는 이슈는 먼저 복원해야 합니다."
    ),
    responses={**RESP_401, **RESP_404, 409: error_response(ISSUE_TRASHED), **RESP_422},
)
def patch_issue(
    issue_id: uuid.UUID,
    payload: IssueUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueOut:
    issue = _require_issue(db, issue_id, user)
    if issue.trashed_at is not None:
        raise HTTPException(status_code=409, detail=ISSUE_TRASHED)
    updated = apply_issue_update(db, issue, user, payload)
    visible = get_visible_issue(db, updated.id, user)
    if visible is None:
        raise HTTPException(status_code=404, detail=ISSUE_NOT_FOUND)
    return to_issue_out(visible)


@router.post(
    "/{issue_id}/trash",
    operation_id="trashIssue",
    response_model=IssueOut,
    summary="휴지통에 넣기",
    description=(
        "이슈를 휴지통으로 옮깁니다. 데이터와 원본 음성은 그대로이고 기본 목록·주간 요약·검토 목록에서만 빠집니다. "
        "이미 휴지통이면 처음 시각을 유지한 채 성공합니다."
    ),
    responses={**RESP_401, **RESP_404, **RESP_422},
)
def trash(
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueOut:
    issue = trash_issue(db, _require_issue(db, issue_id, user))
    return to_issue_out(issue)


@router.post(
    "/{issue_id}/restore",
    operation_id="restoreIssue",
    response_model=IssueOut,
    summary="휴지통에서 복원",
    description="휴지통의 이슈를 정상 상태로 되돌립니다. 이미 정상이면 그대로 성공합니다.",
    responses={**RESP_401, **RESP_404, **RESP_422},
)
def restore(
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueOut:
    issue = restore_issue(db, _require_issue(db, issue_id, user))
    return to_issue_out(issue)


@router.delete(
    "/{issue_id}",
    operation_id="deleteIssuePermanently",
    status_code=204,
    summary="영구 삭제",
    description=(
        "휴지통에 있는 이슈만 영구 삭제합니다. 이슈와 함께 녹음 원본 파일, 전사, 검토 기록이 지워지고 "
        "되돌릴 수 없습니다. 정상 상태의 이슈는 먼저 `POST /api/issues/{issue_id}/trash` 로 "
        "휴지통에 넣어야 하며, 아니면 409 입니다."
    ),
    responses={**RESP_401, **RESP_404, 409: error_response(ISSUE_NOT_TRASHED), **RESP_422},
)
def delete_issue_permanently(
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    issue = _require_issue(db, issue_id, user)
    try:
        purge_issue(db, issue)
    except NotTrashedError as exc:
        raise HTTPException(status_code=409, detail=ISSUE_NOT_TRASHED) from exc


@router.get(
    "/{issue_id}/audio",
    operation_id="getIssueAudio",
    summary="원본 음성",
    description=(
        "오디오 바이트를 반환합니다. Authorization 헤더가 필요해서 `<audio src>` 에 주소를 바로 넣을 수 없습니다. "
        "fetch 로 받아 blob URL 로 재생합니다. 휴지통의 이슈도 받을 수 있습니다."
    ),
    response_class=FileResponse,
    responses={**AUDIO_200, **RESP_401, **RESP_404, **RESP_422},
)
def get_audio(
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    issue = _require_issue(db, issue_id, user)
    path = Path(issue.recording.audio_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=ISSUE_NOT_FOUND)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)
