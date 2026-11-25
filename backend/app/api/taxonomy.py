from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.errors import RESP_401
from app.auth.deps import get_current_user
from app.domain.taxonomy.loader import GUIDE_IDS, load_taxonomy
from app.models import User
from app.schemas.taxonomy import GuideId, ReviewFieldKey, TaxonomyGuideGroup, TaxonomyOption, TaxonomyOut

router = APIRouter()

REVIEW_FIELD_BY_GUIDE: dict[GuideId, ReviewFieldKey] = {
    "road_type": "roadType",
    "ego_action_before": "previousAction",
    "target_type": "targetType",
    "ego_reaction": "reaction",
}


@router.get(
    "",
    operation_id="getTaxonomy",
    response_model=TaxonomyOut,
    summary="이슈 분류 보기",
    description=(
        "이슈 유형, 심각도, 네 개의 안내 항목(도로 유형·직전 동작·대상 유형·이후 반응)의 key 와 한국어 이름을 줍니다. "
        "이슈 응답의 값은 key 로 오므로, 화면에는 이 목록의 label 로 바꿔 보여 줍니다. "
        "앱을 시작할 때 한 번 받아 두면 됩니다. 값이 바뀌면 version 이 바뀝니다."
    ),
    responses=RESP_401,
)
def get_taxonomy(_: User = Depends(get_current_user)) -> TaxonomyOut:
    taxonomy = load_taxonomy()
    return TaxonomyOut(
        version=taxonomy.version,
        event_types=[TaxonomyOption(key=i.key, label=i.label, description=i.description) for i in taxonomy.event_types],
        severity_levels=[
            TaxonomyOption(key=i.key, label=i.label, description=i.description) for i in taxonomy.severity_levels
        ],
        guide=[
            TaxonomyGuideGroup(
                id=guide_id,
                review_field=REVIEW_FIELD_BY_GUIDE[guide_id],
                label=taxonomy.guide[guide_id].label,
                prompt=taxonomy.guide[guide_id].prompt,
                options=[
                    TaxonomyOption(key=o.key, label=o.label, description=o.description)
                    for o in taxonomy.guide[guide_id].options
                ],
            )
            for guide_id in GUIDE_IDS
        ],
    )
