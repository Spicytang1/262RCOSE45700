from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DriveOut(BaseModel):
    """프론트 DriveSession. operator_id 는 로그인한 감독관이다."""

    id: uuid.UUID
    operator_id: uuid.UUID
    number: int
    started_at: datetime
    ended_at: datetime | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "operator_id": "8d8a0a3e-3c1e-4b7a-9d2a-6e3c1b2a4f10",
                    "number": 3,
                    "started_at": "2026-11-18T01:00:00Z",
                    "ended_at": None,
                }
            ]
        }
    )
