"""운행 회차와 검토 기록."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_drives_reviews"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drive_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "number", name="uq_drive_sessions_user_number"),
    )
    op.add_column(
        "recordings",
        sa.Column(
            "drive_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drive_sessions.id"),
            nullable=True,
        ),
    )
    op.create_table(
        "recording_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("recording_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recordings.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("other_fields", postgresql.JSONB(), nullable=False),
        sa.Column("other_field_values", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("recording_id"),
    )


def downgrade() -> None:
    op.drop_table("recording_reviews")
    op.drop_column("recordings", "drive_session_id")
    op.drop_table("drive_sessions")
