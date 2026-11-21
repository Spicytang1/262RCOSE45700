from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DriveSession, User
from app.models.base import utcnow
from app.schemas.drives import DriveOut


def to_drive(drive: DriveSession) -> DriveOut:
    return DriveOut(
        id=drive.id,
        operator_id=drive.user_id,
        number=drive.number,
        started_at=drive.started_at,
        ended_at=drive.ended_at,
    )


def list_drives(db: Session, user: User) -> list[DriveSession]:
    stmt = select(DriveSession)
    if user.role != "admin":
        stmt = stmt.where(DriveSession.user_id == user.id)
    return list(db.scalars(stmt.order_by(DriveSession.started_at.desc())))


def get_drive(db: Session, drive_id: uuid.UUID, user: User) -> DriveSession | None:
    drive = db.get(DriveSession, drive_id)
    if drive is None:
        return None
    if user.role != "admin" and drive.user_id != user.id:
        return None
    return drive


def open_drive_for_operator(db: Session, drive_id: uuid.UUID, user: User) -> DriveSession | None:
    """업로드에 붙일 수 있는 회차. 본인 것이고 아직 끝나지 않아야 한다."""
    drive = db.get(DriveSession, drive_id)
    if drive is None or drive.user_id != user.id or drive.ended_at is not None:
        return None
    return drive


def start_drive(db: Session, user: User) -> DriveSession:
    """진행 중 회차가 있으면 새로 만들지 않고 그 회차를 돌려준다."""
    active = db.scalar(select(DriveSession).where(DriveSession.user_id == user.id, DriveSession.ended_at.is_(None)))
    if active is not None:
        return active
    current = db.scalar(
        select(DriveSession.number).where(DriveSession.user_id == user.id).order_by(DriveSession.number.desc())
    )
    drive = DriveSession(
        user_id=user.id,
        number=(current or 0) + 1,
        started_at=utcnow(),
        ended_at=None,
    )
    db.add(drive)
    db.commit()
    db.refresh(drive)
    return drive


def end_drive(db: Session, drive: DriveSession) -> DriveSession:
    if drive.ended_at is None:
        drive.ended_at = utcnow()
        db.commit()
        db.refresh(drive)
    return drive
