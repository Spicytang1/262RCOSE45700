from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.taxonomy.loader import choice_keys, event_type_keys, severity_keys
from app.schemas.common import IssueExtraction, WordToken

# 허용값은 taxonomy/v1.yaml 에서 읽는다. 문서(OpenAPI)에 enum 으로 그대로 나간다.
EventTypeKey = Literal[tuple(event_type_keys())]  # type: ignore[valid-type]
SeverityKey = Literal[tuple(severity_keys())]  # type: ignore[valid-type]
RoadTypeKey = Literal[tuple(choice_keys("road_type"))]  # type: ignore[valid-type]
EgoActionBeforeKey = Literal[tuple(choice_keys("ego_action_before"))]  # type: ignore[valid-type]
TargetTypeKey = Literal[tuple(choice_keys("target_type"))]  # type: ignore[valid-type]
EgoReactionKey = Literal[tuple(choice_keys("ego_reaction"))]  # type: ignore[valid-type]

LocationStatus = Literal["available", "denied", "timeout", "unavailable", "unsupported", "insecure"]
StartTrigger = Literal["button", "intervention"]


class RecordingLocation(BaseModel):
    """녹음 버튼을 누를 때 요청한 기기 위치의 결과. 사건 위치나 차량 GPS 가 아니다."""

    status: LocationStatus
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = Field(default=None, description="위치 정확도(미터)")
    requested_at: datetime | None = None
    captured_at: datetime | None = None


class PipelineThresholds(BaseModel):
    cls_conf_high: float
    cls_conf_low: float
    stt_conf_min: float


class PipelineMeta(BaseModel):
    """처리 단계 메모. 화면에 꼭 필요한 값은 아니며, errors 가 있으면 일부 단계가 실패한 것이다."""

    stt_provider: str = ""
    extractor_model: str = ""
    jev_model_version: str = ""
    taxonomy_version: str = ""
    thresholds: PipelineThresholds | None = None
    errors: dict[str, str] | None = Field(default=None, description="단계 이름(extraction, classification)별 실패 사유")


class IssueTicket(BaseModel):
    """지라에 올릴 항목 중, 발화 분류와 별도로 저장하는 값."""

    vehicle_number: str | None = None
    occurred_on: date | None = None
    autonomy_version: str | None = None
    map_version: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    content: str | None = None


IssueStatus = Literal["draft", "confirmed", "error"]


class TranscriptOut(BaseModel):
    raw_text: str
    corrected_text: str = Field(description="용어 사전으로 보정한 전사문. 화면에는 이 값을 보여 줍니다.")
    words: list[WordToken]
    stt_provider: str


class RecordingResult(BaseModel):
    recording_id: uuid.UUID
    issue_id: uuid.UUID
    recorded_at: datetime
    status: IssueStatus
    transcript: TranscriptOut
    extraction: IssueExtraction
    ticket: IssueTicket
    pipeline_meta: PipelineMeta
    drive_session_id: uuid.UUID | None = None
    duration_sec: float | None = None
    start_trigger: StartTrigger | None = None
    location: RecordingLocation | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "recording_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "issue_id": "8d8a0a3e-3c1e-4b7a-9d2a-6e3c1b2a4f10",
                    "recorded_at": "2026-11-09T05:00:00Z",
                    "status": "draft",
                    "transcript": {
                        "raw_text": "강남대로에서 검은 차가 컷 인해서 급제동했다.",
                        "corrected_text": "강남대로에서 검은 차가 컷인해서 급제동했다.",
                        "words": [{"text": "급제동했다", "start": 1.2, "end": 1.8, "confidence": 0.91}],
                        "stt_provider": "mock",
                    },
                    "extraction": IssueExtraction.model_config["json_schema_extra"]["examples"][0],
                    "ticket": {
                        "vehicle_number": "12가3456",
                        "occurred_on": "2026-11-09",
                        "autonomy_version": None,
                        "map_version": None,
                        "latitude": 37.5,
                        "longitude": 127.0,
                        "content": "강남대로에서 검은 차가 컷인해서 급제동했다.",
                    },
                    "pipeline_meta": {
                        "stt_provider": "mock",
                        "extractor_model": "",
                        "jev_model_version": "",
                        "taxonomy_version": "v1",
                        "thresholds": {"cls_conf_high": 0.85, "cls_conf_low": 0.55, "stt_conf_min": 0.6},
                    },
                }
            ]
        }
    )


class IssueOut(BaseModel):
    id: uuid.UUID
    recording_id: uuid.UUID
    recorded_at: datetime
    operator_id: uuid.UUID
    status: IssueStatus
    ai_extraction: IssueExtraction
    final_extraction: IssueExtraction | None
    confirmed_at: datetime | None
    confirmed_by: uuid.UUID | None
    pipeline_meta: PipelineMeta
    ticket: IssueTicket
    transcript: TranscriptOut
    drive_session_id: uuid.UUID | None = Field(
        default=None, description="녹음이 속한 운행 회차. 회차 없는 옛 녹음은 null"
    )
    duration_sec: float | None = Field(default=None, description="녹음 길이(초). 옛 녹음은 null")
    start_trigger: StartTrigger | None = Field(default=None, description="녹음 시작 방식. 옛 녹음은 null")
    location: RecordingLocation | None = Field(default=None, description="녹음 시작 때 요청한 기기 위치. 없으면 null")
    trashed_at: datetime | None = Field(
        default=None, description="휴지통에 넣은 시각. null 이면 정상 상태, 값이 있으면 휴지통 상태"
    )


class IssueUpdate(BaseModel):
    """보낸 필드만 바뀝니다. 생략하거나 null 이면 그 값은 그대로 두며, 값을 비우는 용도로는 쓸 수 없습니다.

    event_type, severity 와 네 개의 안내 항목(road_type, ego_action_before, target_type, ego_reaction)은
    `GET /api/taxonomy` 가 알려주는 key 만 받습니다.
    """

    cause: str | None = None
    location: str | None = None
    mentioned_time: str | None = None
    event_type: EventTypeKey | None = None
    severity: SeverityKey | None = None
    road_type: RoadTypeKey | None = None
    ego_action_before: EgoActionBeforeKey | None = None
    target_type: TargetTypeKey | None = None
    ego_reaction: EgoReactionKey | None = None
    vehicle_number: str | None = Field(default=None, max_length=64)
    occurred_on: date | None = None
    autonomy_version: str | None = Field(default=None, max_length=64)
    map_version: str | None = Field(default=None, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    content: str | None = None
    confirm: bool = Field(default=True, description="true 면 이 저장으로 확정(confirmed)하고 확인자를 기록합니다.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "event_type": "cut_in",
                    "severity": "high",
                    "road_type": "intersection",
                    "target_type": "vehicle",
                    "ego_reaction": "hard_decel",
                    "cause": "컷인",
                    "location": "강남대로",
                    "vehicle_number": "12가3456",
                    "content": "강남대로에서 검은 차가 컷인해서 급제동했다.",
                    "confirm": True,
                }
            ]
        }
    )


class SummaryStats(BaseModel):
    count: int
    previous_count: int
    delta: int
    by_event_type: dict[str, int]
    by_cause: dict[str, int]


class WeeklySummary(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime
    stats: SummaryStats
    narrative: str

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "from": "2026-11-02T00:00:00Z",
                    "to": "2026-11-09T00:00:00Z",
                    "stats": {
                        "count": 4,
                        "previous_count": 1,
                        "delta": 3,
                        "by_event_type": {"cut_in": 2, "sudden_brake": 2},
                        "by_cause": {"컷인": 2},
                    },
                    "narrative": "이번 기간 이슈는 4건이며 직전 기간보다 3건 많습니다.",
                }
            ]
        },
    )
