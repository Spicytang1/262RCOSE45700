from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Issue, User
from app.models.base import utcnow
from app.services.login_code import LOGIN_CODE_RULE
from app.services.pipeline import run_pipeline
from app.services.users import InvalidLoginCodeError, add_user, find_user_by_code
from sqlalchemy import func, select


def _ensure_user(db, settings, *, code: str, display_name: str, role: str) -> User:
    existing = find_user_by_code(db, settings, code)
    if existing is not None:
        return existing
    try:
        return add_user(db, settings, code=code, display_name=display_name, role=role)
    except InvalidLoginCodeError:
        print(f"{display_name} 코드가 형식에 맞지 않습니다. {LOGIN_CODE_RULE}", file=sys.stderr)
        raise SystemExit(1) from None


def _silent_wav() -> bytes:
    return (
        b"RIFF"
        + (36).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little")
        + (8000).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (8).to_bytes(2, "little")
        + b"data"
        + (0).to_bytes(4, "little")
    )


def main() -> None:
    settings = get_settings()
    wanted = [("관리자", "admin", settings.seed_admin_code)] + [
        (f"오퍼레이터{index}", "operator", getattr(settings, f"seed_operator{index}_code")) for index in range(1, 6)
    ]
    configured = [(name, role, code) for name, role, code in wanted if code]
    if not configured:
        print("SEED_ADMIN_CODE, SEED_OPERATOR1_CODE ... 중 하나 이상을 채워야 합니다.", file=sys.stderr)
        raise SystemExit(1)
    db = make_session_factory(make_engine(settings))()
    try:
        users = [
            (name, role, _ensure_user(db, settings, code=code, display_name=name, role=role))
            for name, role, code in configured
        ]
        operators = [user for _, role, user in users if role == "operator"]
        if operators and db.scalar(select(func.count()).select_from(Issue)) == 0:
            storage = Path(settings.storage_dir)
            storage.mkdir(parents=True, exist_ok=True)
            audio_path = storage / "seed-demo.wav"
            audio_path.write_bytes(_silent_wav())
            run_pipeline(
                db,
                settings,
                user_id=operators[0].id,
                audio_path=audio_path,
                recorded_at=utcnow(),
                latitude=37.5665,
                longitude=126.9780,
            )
        db.commit()
    finally:
        db.close()
    print(f"시드 완료: {', '.join(name for name, _, _ in users)}")


if __name__ == "__main__":
    main()
