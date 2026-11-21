from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.auth.sessions import revoke_all_sessions
from app.models import User
from app.models.base import utcnow
from app.schemas.auth import UserUpdate
from app.services.employee_number import is_employee_number


class DuplicateUsernameError(Exception):
    pass


class InvalidEmployeeNumberError(Exception):
    pass


def add_user(db: Session, *, username: str, password: str, display_name: str, role: str) -> User:
    if not is_employee_number(username):
        raise InvalidEmployeeNumberError(username)
    existing = db.scalar(select(User).where(User.employee_number == username))
    if existing is not None:
        raise DuplicateUsernameError(username)
    user = User(
        username=username,
        employee_number=username,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def update_user(db: Session, user: User, payload: UserUpdate) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is False:
        user.is_active = False
        revoke_all_sessions(db, user.id, "deactivated", utcnow())
    elif payload.is_active is True:
        user.is_active = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
