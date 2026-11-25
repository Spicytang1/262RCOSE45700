from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FIELD_KEYS = {
    "roadType",
    "previousAction",
    "targetType",
    "reaction",
    "location",
    "event",
    "situation",
    "weather",
}
STRUCTURED_KEYS = {"roadType", "previousAction", "targetType", "reaction"}
ReviewStatus = Literal["new", "reviewed", "flagged"]


class ReviewWrite(BaseModel):
    """프론트 RecordingReview 전체. 자동 저장은 이 스냅샷을 통째로 보낸다."""

    title: str = Field(default="", max_length=120)
    status: ReviewStatus
    note: str = Field(default="", max_length=4000)
    fields: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "정리 항목. 키는 roadType, previousAction, targetType, reaction, "
            "location, event, situation, weather 만 허용"
        ),
    )
    other_fields: list[str] = Field(
        default_factory=list,
        description="'기타'를 직접 입력 중인 항목. roadType, previousAction, targetType, reaction 중에서",
    )
    other_field_values: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "보행자 급감속",
                    "status": "reviewed",
                    "note": "횡단보도 앞에서 확인함",
                    "fields": {
                        "roadType": "직선로",
                        "previousAction": "직진",
                        "targetType": "보행자",
                        "reaction": "급감속",
                    },
                    "other_fields": ["reaction"],
                    "other_field_values": {"reaction": "수동 감속"},
                }
            ]
        }
    )

    @field_validator("fields")
    @classmethod
    def known_fields(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > len(FIELD_KEYS):
            raise ValueError("정리 항목이 너무 많습니다.")
        for key, item in value.items():
            if key not in FIELD_KEYS:
                raise ValueError("알 수 없는 정리 항목입니다.")
            if len(item) > 200:
                raise ValueError("정리 항목 값이 너무 깁니다.")
        return value

    @field_validator("other_fields")
    @classmethod
    def known_other_fields(cls, value: list[str]) -> list[str]:
        if any(item not in STRUCTURED_KEYS for item in value):
            raise ValueError("기타 항목 키가 올바르지 않습니다.")
        if len(value) != len(set(value)):
            raise ValueError("기타 항목이 중복되었습니다.")
        return value

    @field_validator("other_field_values")
    @classmethod
    def known_other_values(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            if key not in STRUCTURED_KEYS:
                raise ValueError("기타 입력 키가 올바르지 않습니다.")
            if len(item) > 200:
                raise ValueError("기타 입력이 너무 깁니다.")
        return value


class ReviewOut(ReviewWrite):
    id: uuid.UUID
    recording_id: uuid.UUID
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    **ReviewWrite.model_config["json_schema_extra"]["examples"][0],
                    "id": "11111111-1111-4111-8111-111111111111",
                    "recording_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "updated_at": "2026-11-18T01:05:00Z",
                }
            ]
        }
    )
