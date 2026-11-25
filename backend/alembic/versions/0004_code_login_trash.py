"""코드 로그인, 이슈 휴지통, 녹음 위치·길이 메타.

주의: 기존 사용자는 코드로 변환할 수 없으므로 users 와 이를 참조하는 모든 행(세션·운행 회차·녹음·전사·이슈·수정 이력)을
삭제한다. 시연·시드 데이터 전제이며, 업로드된 음성 파일은 STORAGE_DIR 에 남으므로 필요하면 직접 지운다.
적용 후 `python -m scripts.seed` 로 사용자를 다시 만든다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_code_login_trash"
down_revision: str | None = "0003_soft_delete_identity_place"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("TRUNCATE TABLE users CASCADE")
    op.add_column("users", sa.Column("code_digest", sa.String(length=64), nullable=False))
    op.create_unique_constraint("uq_users_code_digest", "users", ["code_digest"])
    op.drop_constraint("uq_users_employee_number", "users", type_="unique")
    op.drop_column("users", "employee_number")
    op.drop_column("users", "password_hash")
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_column("users", "username")

    op.add_column("recordings", sa.Column("duration_sec", sa.Float(), nullable=True))
    op.add_column("recordings", sa.Column("start_trigger", sa.String(length=16), nullable=True))
    op.add_column("recordings", sa.Column("location_status", sa.String(length=16), nullable=True))
    op.add_column("recordings", sa.Column("location_accuracy_m", sa.Float(), nullable=True))
    op.add_column("recordings", sa.Column("location_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recordings", sa.Column("location_captured_at", sa.DateTime(timezone=True), nullable=True))

    op.alter_column("issues", "deleted_at", new_column_name="trashed_at")


def downgrade() -> None:
    op.alter_column("issues", "trashed_at", new_column_name="deleted_at")

    op.drop_column("recordings", "location_captured_at")
    op.drop_column("recordings", "location_requested_at")
    op.drop_column("recordings", "location_accuracy_m")
    op.drop_column("recordings", "location_status")
    op.drop_column("recordings", "start_trigger")
    op.drop_column("recordings", "duration_sec")

    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("employee_number", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE users SET username = 'user-' || id::text, employee_number = left(id::text, 32), password_hash = '!'"
    )
    op.alter_column("users", "username", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("users", "employee_number", existing_type=sa.String(length=32), nullable=False)
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.create_unique_constraint("uq_users_employee_number", "users", ["employee_number"])
    op.drop_constraint("uq_users_code_digest", "users", type_="unique")
    op.drop_column("users", "code_digest")
