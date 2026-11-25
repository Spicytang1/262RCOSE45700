from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GuideId = Literal["road_type", "ego_action_before", "target_type", "ego_reaction"]
ReviewFieldKey = Literal["roadType", "previousAction", "targetType", "reaction"]


class TaxonomyOption(BaseModel):
    key: str = Field(description="서버가 주고받는 값. IssueUpdate 와 이슈 추출 결과의 value 가 이 key 입니다.")
    label: str = Field(description="화면에 보여 줄 한국어 이름")
    description: str


class TaxonomyGuideGroup(BaseModel):
    id: GuideId = Field(description="이슈 추출 결과와 IssueUpdate 에서 쓰는 항목 이름")
    review_field: ReviewFieldKey = Field(
        description="검토 저장(ReviewWrite.fields, other_fields)에서 같은 항목을 가리키는 이름"
    )
    label: str
    prompt: str
    options: list[TaxonomyOption]


class TaxonomyOut(BaseModel):
    """이슈 분류에 쓰는 닫힌 보기 전체. 값 목록은 서버 설정(taxonomy/v1.yaml)이 기준이다."""

    version: str
    event_types: list[TaxonomyOption]
    severity_levels: list[TaxonomyOption] = Field(description="낮은 단계부터 높은 단계 순서")
    guide: list[TaxonomyGuideGroup]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "version": "v1",
                    "event_types": [{"key": "cut_in", "label": "끼어들기", "description": "다른 차량이 끼어든 사건"}],
                    "severity_levels": [{"key": "low", "label": "낮음", "description": "경미한 이슈"}],
                    "guide": [
                        {
                            "id": "road_type",
                            "review_field": "roadType",
                            "label": "장소 또는 도로 유형",
                            "prompt": "이슈가 난 곳의 도로 모양을 고르세요.",
                            "options": [
                                {"key": "intersection", "label": "교차로", "description": "교차로 안에서 난 이슈"}
                            ],
                        }
                    ],
                }
            ]
        }
    )
