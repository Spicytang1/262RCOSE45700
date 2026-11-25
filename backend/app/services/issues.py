from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.models import Issue, IssueEdit, Recording, RecordingReview, Transcript, User
from app.models.base import utcnow
from app.schemas.common import IssueExtraction
from app.schemas.issues import (
    IssueOut,
    IssueTicket,
    IssueUpdate,
    PipelineMeta,
    RecordingLocation,
    TranscriptOut,
)


def _extraction(payload: dict | None) -> IssueExtraction | None:
    if payload is None:
        return None
    return IssueExtraction.model_validate(payload)


def _active_extraction(issue: Issue) -> dict:
    return issue.final_extraction or issue.ai_extraction


def field_value(issue: Issue, name: str) -> object:
    payload = _active_extraction(issue)
    field = payload.get(name)
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


def recording_location(recording: Recording) -> RecordingLocation | None:
    """위치 상태가 없는 옛 녹음은 좌표가 있을 때만 성공으로 본다."""
    if recording.location_status is None:
        if recording.latitude is None or recording.longitude is None:
            return None
        return RecordingLocation(status="available", latitude=recording.latitude, longitude=recording.longitude)
    return RecordingLocation(
        status=recording.location_status,  # type: ignore[arg-type]
        latitude=recording.latitude,
        longitude=recording.longitude,
        accuracy_m=recording.location_accuracy_m,
        requested_at=recording.location_requested_at,
        captured_at=recording.location_captured_at,
    )


def to_issue_out(issue: Issue) -> IssueOut:
    recording = issue.recording
    transcript = recording.transcript
    if transcript is None:
        raise RuntimeError("이슈에 전사문이 없습니다.")
    return IssueOut(
        id=issue.id,
        recording_id=issue.recording_id,
        recorded_at=recording.recorded_at,
        operator_id=recording.user_id,
        status=issue.status,  # type: ignore[arg-type]
        ai_extraction=IssueExtraction.model_validate(issue.ai_extraction),
        final_extraction=_extraction(issue.final_extraction),
        confirmed_at=issue.confirmed_at,
        confirmed_by=issue.confirmed_by,
        pipeline_meta=PipelineMeta.model_validate(issue.pipeline_meta),
        ticket=ticket_from_issue(issue),
        transcript=TranscriptOut(
            raw_text=transcript.raw_text,
            corrected_text=transcript.corrected_text,
            words=list(transcript.words),
            stt_provider=transcript.stt_provider,
        ),
        drive_session_id=recording.drive_session_id,
        duration_sec=recording.duration_sec,
        start_trigger=recording.start_trigger,  # type: ignore[arg-type]
        location=recording_location(recording),
        trashed_at=issue.trashed_at,
    )


def get_visible_issue(db: Session, issue_id: uuid.UUID, user: User) -> Issue | None:
    """본인(관리자는 전체) 이슈. 휴지통에 있는 것도 돌려주므로 상태는 trashed_at 으로 확인한다."""
    issue = db.scalar(
        select(Issue).options(joinedload(Issue.recording).joinedload(Recording.transcript)).where(Issue.id == issue_id)
    )
    if issue is None or issue.recording is None:
        return None
    if user.role != "admin" and issue.recording.user_id != user.id:
        return None
    return issue


def list_visible_issues(
    db: Session,
    user: User,
    *,
    status: str | None,
    event_type: str | None,
    start: datetime | None,
    end: datetime | None,
    trashed: bool = False,
) -> list[Issue]:
    stmt = (
        select(Issue)
        .join(Recording, Recording.id == Issue.recording_id)
        .options(joinedload(Issue.recording).joinedload(Recording.transcript))
        .where(Issue.trashed_at.is_not(None) if trashed else Issue.trashed_at.is_(None))
        .order_by(Issue.trashed_at.desc() if trashed else Recording.recorded_at.desc())
    )
    if user.role != "admin":
        stmt = stmt.where(Recording.user_id == user.id)
    if status is not None:
        stmt = stmt.where(Issue.status == status)
    if start is not None:
        stmt = stmt.where(Recording.recorded_at >= start)
    if end is not None:
        stmt = stmt.where(Recording.recorded_at < end)
    issues = list(db.scalars(stmt).unique().all())
    if event_type is None:
        return issues
    return [issue for issue in issues if field_value(issue, "event_type") == event_type]


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def ticket_from_issue(issue: Issue) -> IssueTicket:
    return IssueTicket(
        vehicle_number=issue.vehicle_number,
        occurred_on=issue.occurred_on,
        autonomy_version=issue.autonomy_version,
        map_version=issue.map_version,
        latitude=issue.latitude,
        longitude=issue.longitude,
        content=issue.content,
    )


def apply_issue_update(db: Session, issue: Issue, user: User, payload: IssueUpdate) -> Issue:
    ai = IssueExtraction.model_validate(issue.ai_extraction)
    current = IssueExtraction.model_validate(issue.final_extraction or issue.ai_extraction)
    updates = {
        "cause": payload.cause,
        "location": payload.location,
        "mentioned_time": payload.mentioned_time,
        "event_type": payload.event_type,
        "severity": payload.severity,
        "road_type": payload.road_type,
        "ego_action_before": payload.ego_action_before,
        "target_type": payload.target_type,
        "ego_reaction": payload.ego_reaction,
    }
    for field, new_value in updates.items():
        if new_value is None:
            continue
        target = getattr(current, field)
        if new_value == target.value:
            continue
        target.value = new_value
        db.add(
            IssueEdit(
                issue_id=issue.id,
                field=field,
                ai_value=_dump(getattr(ai, field).value),
                final_value=_dump(new_value),
                edited_by=user.id,
            )
        )
    for name in (
        "vehicle_number",
        "occurred_on",
        "autonomy_version",
        "map_version",
        "latitude",
        "longitude",
        "content",
    ):
        new_value = getattr(payload, name)
        if new_value is None:
            continue
        previous = getattr(issue, name)
        if new_value == previous:
            continue
        setattr(issue, name, new_value)
        db.add(
            IssueEdit(
                issue_id=issue.id,
                field=name,
                ai_value=_dump(previous),
                final_value=_dump(new_value),
                edited_by=user.id,
            )
        )
    if payload.confirm:
        for name in ("cause", "location", "mentioned_time"):
            field = getattr(current, name)
            field.needs_review = False
            field.review_reason = None
        for name in ("event_type", "severity", "road_type", "ego_action_before", "target_type", "ego_reaction"):
            getattr(current, name).needs_review = False
        issue.status = "confirmed"
        issue.confirmed_at = utcnow()
        issue.confirmed_by = user.id
    issue.final_extraction = current.model_dump(mode="json")
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


class NotTrashedError(Exception):
    pass


def trash_issue(db: Session, issue: Issue) -> Issue:
    """휴지통으로 옮긴다. 이미 휴지통이면 처음 시각을 유지한다."""
    if issue.trashed_at is None:
        issue.trashed_at = utcnow()
        db.add(issue)
        db.commit()
        db.refresh(issue)
    return issue


def restore_issue(db: Session, issue: Issue) -> Issue:
    if issue.trashed_at is not None:
        issue.trashed_at = None
        db.add(issue)
        db.commit()
        db.refresh(issue)
    return issue


def purge_issue(db: Session, issue: Issue) -> None:
    """휴지통에 있는 이슈를 녹음 원본·전사·검토와 함께 완전히 지운다. 되돌릴 수 없다."""
    if issue.trashed_at is None:
        raise NotTrashedError
    recording = issue.recording
    recording_id = recording.id
    audio_path = Path(recording.audio_path)
    issue_id = issue.id
    # 외래키 순서대로 한 번에 지운다. ORM 연쇄 삭제를 쓰지 않는다.
    db.execute(delete(IssueEdit).where(IssueEdit.issue_id == issue_id))
    db.execute(delete(Issue).where(Issue.id == issue_id))
    db.execute(delete(RecordingReview).where(RecordingReview.recording_id == recording_id))
    db.execute(delete(Transcript).where(Transcript.recording_id == recording_id))
    db.execute(delete(Recording).where(Recording.id == recording_id))
    db.commit()
    # DB 삭제가 확정된 뒤에만 파일을 지운다. 파일 삭제가 실패해도 DB 는 이미 정리된 상태다.
    audio_path.unlink(missing_ok=True)
