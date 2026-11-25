from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters.extractor.factory import get_extractor
from app.adapters.extractor.gateway_claude import ExtractionFailed
from app.adapters.gateway.errors import GatewayError
from app.api.errors import RESP_401, RESP_403, RESP_422, SUMMARY_FAILED, error_response
from app.auth.deps import get_db, get_settings, require_role
from app.config import Settings
from app.models import User
from app.schemas.issues import WeeklySummary
from app.services.pipeline import ExternalCallError
from app.services.summary import aggregate_weekly

router = APIRouter()


@router.get(
    "/weekly",
    operation_id="getWeeklySummary",
    response_model=WeeklySummary,
    summary="주간 요약",
    description=(
        "건수와 분포는 SQL 집계만 사용하고, 문장은 그 숫자를 풀어 쓴 결과입니다. "
        "휴지통에 있는 이슈는 집계하지 않습니다. 관리자 전용입니다."
    ),
    responses={**RESP_401, **RESP_403, **RESP_422, 503: error_response(SUMMARY_FAILED)},
)
def weekly_summary(
    from_: datetime = Query(alias="from"),
    to: datetime = Query(),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: User = Depends(require_role("admin")),
) -> WeeklySummary:
    if to <= from_:
        raise HTTPException(status_code=422, detail="to 는 from 보다 이후여야 합니다.")
    if to - from_ > timedelta(days=366):
        raise HTTPException(status_code=422, detail="조회 기간이 너무 깁니다.")
    stats = aggregate_weekly(db, from_, to)
    try:
        narrative = get_extractor(settings).summarize(stats.model_dump())
    except (NotImplementedError, ExternalCallError, GatewayError, ExtractionFailed) as exc:
        raise HTTPException(status_code=503, detail=SUMMARY_FAILED) from exc
    return WeeklySummary.model_validate({"from": from_, "to": to, "stats": stats, "narrative": narrative})
