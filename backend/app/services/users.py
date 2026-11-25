from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import revoke_all_sessions
from app.config import Settings
from app.models import User
from app.models.base import utcnow
from app.schemas.auth import UserUpdate
from app.services.login_code import digest_login_code, is_login_code


class DuplicateLoginCodeError(Exception):
    pass


class InvalidLoginCodeError(Exception):
    pass


def find_user_by_code(db: Session, settings: Settings, code: str) -> User | None:
    if not is_login_code(code):
        return None
    return db.scalar(select(User).where(User.code_digest == digest_login_code(code, settings)))


def _digest_for_new_code(db: Session, settings: Settings, code: str, *, owner: User | None) -> str:
    if not is_login_code(code):
        raise InvalidLoginCodeError
    digest = digest_login_code(code, settings)
    existing = db.scalar(select(User).where(User.code_digest == digest))
    if existing is not None and (owner is None or existing.id != owner.id):
        raise DuplicateLoginCodeError
    return digest


def add_user(db: Session, settings: Settings, *, code: str, display_name: str, role: str) -> User:
    user = User(
        code_digest=_digest_for_new_code(db, settings, code, owner=None),
        display_name=display_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def change_login_code(db: Session, settings: Settings, user: User, new_code: str) -> None:
    """코드를 바꾸고 그 사용자의 모든 세션을 폐기한다. 새 코드로 다시 로그인해야 한다."""
    user.code_digest = _digest_for_new_code(db, settings, new_code, owner=user)
    revoke_all_sessions(db, user.id, "code_changed", utcnow())
    db.add(user)


def update_user(db: Session, settings: Settings, user: User, payload: UserUpdate) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.code is not None:
        change_login_code(db, settings, user, payload.code)
    if payload.is_active is False:
        user.is_active = False
        revoke_all_sessions(db, user.id, "deactivated", utcnow())
    elif payload.is_active is True:
        user.is_active = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
