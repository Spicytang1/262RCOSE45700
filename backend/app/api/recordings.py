from __future__ import annotations

import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.errors import (
    DRIVE_NOT_OPEN,
    EXTERNAL_FAILED,
    RESP_401,
    RESP_413,
    RESP_422,
    RESP_503,
    UPLOAD_TOO_LARGE,
)
from app.auth.deps import get_current_user, get_db, get_settings
from app.config import Settings
from app.models import Issue, Recording, User
from app.schemas.issues import LocationStatus, RecordingResult, StartTrigger
from app.services.drives import open_drive_for_operator
from app.services.issues import to_issue_out
from app.services.pipeline import ExternalCallError, RecordingMeta, run_pipeline

router = APIRouter()


ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
CHUNK_BYTES = 1024 * 1024


def _store_upload(upload: UploadFile, storage_dir: str, max_bytes: int) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(status_code=422, detail="지원하지 않는 오디오 형식입니다.")
    destination_dir = Path(storage_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    path = destination_dir / f"{uuid.uuid4()}{suffix}"
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := upload.file.read(CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail=UPLOAD_TOO_LARGE)
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="오디오 파일이 비어 있습니다.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _resolve_location_status(
    latitude: float | None, longitude: float | None, status: LocationStatus | None
) -> LocationStatus:
    """좌표와 위치 상태가 서로 어긋나지 않게 맞춘다. 위치가 없어도 녹음은 저장한다."""
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude 와 longitude 는 함께 보내야 합니다.")
    if latitude is not None and not -90 <= latitude <= 90:
        raise HTTPException(status_code=422, detail="latitude 범위가 아닙니다.")
    if longitude is not None and not -180 <= longitude <= 180:
        raise HTTPException(status_code=422, detail="longitude 범위가 아닙니다.")
    if latitude is not None:
        if status not in (None, "available"):
            raise HTTPException(status_code=422, detail="좌표가 있으면 location_status 는 available 이어야 합니다.")
        return "available"
    if status == "available":
        raise HTTPException(status_code=422, detail="location_status 가 available 이면 좌표가 필요합니다.")
    return status or "unavailable"


@router.post(
    "",
    response_model=RecordingResult,
    summary="녹음 업로드",
    description=(
        "STT, 용어 보정, 사실 추출, 분류, 검증 후 draft 이슈를 만듭니다. 소유자는 로그인한 사용자입니다. "
        "허용 형식은 wav, mp3, m4a, webm, ogg 이고 크기 상한은 MAX_UPLOAD_MB 입니다. "
        "위치를 얻지 못해도 녹음은 저장합니다. 이때 좌표는 보내지 말고 location_status 에 실패 사유를 보냅니다."
    ),
    operation_id="uploadRecording",
    responses={**RESP_401, **RESP_413, **RESP_422, **RESP_503},
)
def create_recording(
    audio: UploadFile = File(..., description="녹음 파일"),
    recorded_at: datetime | None = Form(default=None, description="발화 시각. 없으면 서버 시각"),
    vehicle_number: str | None = Form(default=None, description="차량 번호"),
    occurred_on: date | None = Form(default=None, description="발생일자. 발화 시각과 별개"),
    autonomy_version: str | None = Form(default=None, description="자율주행 버전"),
    map_version: str | None = Form(default=None, description="맵 버전"),
    latitude: float | None = Form(default=None, description="녹음을 시작할 때의 기기 위도. 위치를 못 얻었으면 생략"),
    longitude: float | None = Form(default=None, description="녹음을 시작할 때의 기기 경도. 위치를 못 얻었으면 생략"),
    drive_session_id: uuid.UUID | None = Form(default=None, description="진행 중인 본인 운행 회차"),
    duration_sec: float | None = Form(default=None, ge=0, le=86400, description="녹음 길이(초)"),
    start_trigger: StartTrigger = Form(default="button", description="녹음 시작 방식. 현재 앱은 button 만 보냅니다."),
    location_status: LocationStatus | None = Form(
        default=None, description="위치 요청 결과. 좌표가 있으면 available, 없으면 실패 사유(생략하면 unavailable)"
    ),
    location_accuracy_m: float | None = Form(default=None, ge=0, description="위치 정확도(미터)"),
    location_requested_at: datetime | None = Form(default=None, description="위치를 요청한 시각"),
    location_captured_at: datetime | None = Form(default=None, description="위치를 얻은 시각"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RecordingResult:
    resolved_status = _resolve_location_status(latitude, longitude, location_status)
    if drive_session_id is not None and open_drive_for_operator(db, drive_session_id, user) is None:
        raise HTTPException(status_code=422, detail=DRIVE_NOT_OPEN)
    path = _store_upload(audio, settings.storage_dir, settings.max_upload_bytes)
    try:
        issue = run_pipeline(
            db,
            settings,
            user_id=user.id,
            audio_path=path,
            recorded_at=recorded_at,
            vehicle_number=vehicle_number,
            occurred_on=occurred_on,
            autonomy_version=autonomy_version,
            map_version=map_version,
            latitude=latitude,
            longitude=longitude,
            drive_session_id=drive_session_id,
            meta=RecordingMeta(
                duration_sec=duration_sec,
                start_trigger=start_trigger,
                location_status=resolved_status,
                location_accuracy_m=location_accuracy_m,
                location_requested_at=location_requested_at,
                location_captured_at=location_captured_at,
            ),
        )
    except ExternalCallError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=EXTERNAL_FAILED) from exc
    except Exception:
        path.unlink(missing_ok=True)
        raise
    stored = db.scalar(
        select(Issue).options(joinedload(Issue.recording).joinedload(Recording.transcript)).where(Issue.id == issue.id)
    )
    if stored is None:
        raise HTTPException(status_code=503, detail=EXTERNAL_FAILED)
    viewed = to_issue_out(stored)
    return RecordingResult(
        recording_id=viewed.recording_id,
        issue_id=viewed.id,
        recorded_at=viewed.recorded_at,
        status=viewed.status,
        transcript=viewed.transcript,
        extraction=viewed.ai_extraction,
        ticket=viewed.ticket,
        pipeline_meta=viewed.pipeline_meta,
        drive_session_id=viewed.drive_session_id,
        duration_sec=viewed.duration_sec,
        start_trigger=viewed.start_trigger,
        location=viewed.location,
    )
