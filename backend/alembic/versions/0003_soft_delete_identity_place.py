"""이슈 소프트 삭제, 회사 식별 번호, 녹음 장소 좌표."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_soft_delete_identity_place"
down_revision: str | None = "0002_drives_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("issues", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recordings", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("recordings", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("employee_number", sa.String(length=32), nullable=True))
    op.execute("UPDATE users SET employee_number = username WHERE employee_number IS NULL")
    op.alter_column("users", "employee_number", existing_type=sa.String(length=32), nullable=False)
    op.create_unique_constraint("uq_users_employee_number", "users", ["employee_number"])


def downgrade() -> None:
    op.drop_constraint("uq_users_employee_number", "users", type_="unique")
    op.drop_column("users", "employee_number")
    op.drop_column("recordings", "longitude")
    op.drop_column("recordings", "latitude")
    op.drop_column("issues", "deleted_at")
