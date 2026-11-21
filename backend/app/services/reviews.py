from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Recording, RecordingReview, User
from app.models.base import utcnow
from app.schemas.reviews import ReviewOut, ReviewWrite


def to_review(review: RecordingReview) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        recording_id=review.recording_id,
        title=review.title,
        status=review.status,  # type: ignore[arg-type]
        note=review.note,
        fields=dict(review.fields),
        other_fields=list(review.other_fields),
        other_field_values=dict(review.other_field_values),
        updated_at=review.updated_at,
    )


def visible_recording(db: Session, recording_id: uuid.UUID, user: User) -> Recording | None:
    recording = db.get(Recording, recording_id)
    if recording is None:
        return None
    if user.role != "admin" and recording.user_id != user.id:
        return None
    return recording


def get_review(db: Session, recording_id: uuid.UUID, user: User) -> RecordingReview | None:
    if visible_recording(db, recording_id, user) is None:
        return None
    return db.scalar(select(RecordingReview).where(RecordingReview.recording_id == recording_id))


def list_reviews(db: Session, user: User) -> list[RecordingReview]:
    stmt = select(RecordingReview).join(RecordingReview.recording)
    if user.role != "admin":
        stmt = stmt.where(Recording.user_id == user.id)
    return list(db.scalars(stmt.order_by(RecordingReview.updated_at.desc())))


def save_review(db: Session, recording: Recording, payload: ReviewWrite) -> RecordingReview:
    """음성 원본은 바꾸지 않는다. 같은 녹음의 검토는 한 행만 유지한다."""
    review = db.scalar(select(RecordingReview).where(RecordingReview.recording_id == recording.id))
    if review is None:
        review = RecordingReview(
            recording_id=recording.id,
            title="",
            status=payload.status,
            note="",
            fields={},
            other_fields=[],
            other_field_values={},
        )
        db.add(review)
    review.title = payload.title
    review.status = payload.status
    review.note = payload.note
    review.fields = payload.fields
    review.other_fields = payload.other_fields
    review.other_field_values = payload.other_field_values
    review.updated_at = utcnow()
    db.commit()
    db.refresh(review)
    return review
