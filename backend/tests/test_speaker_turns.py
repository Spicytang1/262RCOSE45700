from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
from app.adapters.extractor.gateway_claude import (
    MULTI_SPEAKER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    GatewayClaudeExtractor,
)
from app.adapters.gateway.client import GatewayClient
from app.adapters.stt.base import Transcript, TranscriptSegment
from app.adapters.stt.gateway import _transcript_if_terminal, segments_from_body, words_from_segments
from app.config import Settings
from app.schemas.common import WordToken
from app.services.pipeline import run_pipeline
from app.services.speaker_turns import (
    has_speaker_labels,
    prepare_speaker_transcript,
    select_driver_text,
)
from sqlalchemy.orm import Session


def _client(handler) -> GatewayClient:
    return GatewayClient(
        "https://factchat.mindlogic-kr-api.com/v1/gateway",
        "test-key",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )


def _audio_with_segments(tmp_path: Path, segments: list[dict[str, object]]) -> Path:
    audio = tmp_path / f"{uuid.uuid4().hex}.wav"
    audio.write_bytes(b"")
    audio.with_name(f"{audio.stem}.segments.json").write_text(
        json.dumps(segments, ensure_ascii=False),
        encoding="utf-8",
    )
    return audio


def test_gateway_stt_preserves_speaker_on_segments_and_words() -> None:
    body = {
        "status": "completed",
        "text": "배고프다 방금 교차로에서 컷인해서 급제동했어요",
        "segments": [
            {"speaker": "Speaker 1", "text": "배고프다", "start_ms": 0, "end_ms": 900},
            {"speaker": "Speaker 2", "text": "방금 교차로에서 컷인해서 급제동했어요", "start_ms": 1200, "end_ms": 4200},
        ],
    }
    transcript = _transcript_if_terminal(body, language="ko")
    assert transcript is not None
    assert [(seg.speaker, seg.text) for seg in transcript.segments] == [
        ("Speaker 1", "배고프다"),
        ("Speaker 2", "방금 교차로에서 컷인해서 급제동했어요"),
    ]
    assert transcript.words[0].speaker == "Speaker 1"
    assert transcript.words[1].speaker == "Speaker 2"
    assert segments_from_body(body["segments"])[1].start == 1.2
    assert words_from_segments(body["segments"])[-1].speaker == "Speaker 2"


def test_single_speaker_passes_through_without_labels() -> None:
    transcript = Transcript(
        text="강남대로에서 검은 차가 컷 인해서 급제동했다",
        words=[WordToken(text="강남대로에서", start=0.0, end=0.5, speaker="Speaker 1")],
        segments=[
            TranscriptSegment(
                speaker="Speaker 1",
                text="강남대로에서 검은 차가 컷 인해서 급제동했다",
                start=0.0,
                end=3.0,
            )
        ],
        language="ko",
        provider="gateway",
    )
    prep = prepare_speaker_transcript(transcript)
    assert prep.is_multi_speaker is False
    assert prep.speaker_count == 1
    assert prep.llm_text == prep.corrected_text
    assert not has_speaker_labels(prep.llm_text)
    assert "[화자" not in prep.llm_text


def test_consecutive_same_speaker_turns_merge_and_glossary_applies() -> None:
    transcript = Transcript(
        text="강남대로에서 컷 인해서 급제동했어요 아 깜짝이야",
        words=[],
        segments=[
            TranscriptSegment(speaker="Speaker 1", text="강남대로에서", start=0.0, end=1.0),
            TranscriptSegment(speaker="Speaker 1", text="컷 인해서 급제동했어요", start=1.1, end=2.5),
            TranscriptSegment(speaker="Speaker 2", text="아 깜짝이야", start=2.8, end=3.6),
        ],
        language="ko",
        provider="gateway",
    )
    prep = prepare_speaker_transcript(transcript)
    assert prep.is_multi_speaker is True
    assert prep.speaker_count == 2
    assert prep.llm_text == "[화자1] 강남대로에서 컷인해서 급제동했어요\n[화자2] 아 깜짝이야"
    assert prep.corrected_text == "강남대로에서 컷인해서 급제동했어요 아 깜짝이야"


def test_claude_uses_multi_speaker_prompt_only_when_labelled_and_strips_tag() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if len(seen) == 1:
            data = {
                "cause": "컷인",
                "cause_evidence": "검은 차가 컷인해서 급제동했어요",
                "location": "강남대로",
                "location_evidence": "강남대로에서",
                "mentioned_time": None,
                "mentioned_time_evidence": None,
            }
        else:
            data = {
                "cause": "보행자 돌출",
                "cause_evidence": "[화자2] 보행자가 갑자기 나와서 급정거했습니다",
                "location": "선릉역",
                "location_evidence": "선릉역 앞에서",
                "mentioned_time": "방금",
                "mentioned_time_evidence": "방금",
            }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(data)}}]})

    extractor = GatewayClaudeExtractor(_client(handler), "claude-opus-5-5")

    single = extractor.extract("강남대로에서 검은 차가 컷인해서 급제동했어요")
    assert seen[0]["messages"][0]["content"].startswith(SYSTEM_PROMPT.split("{terms}")[0])
    assert single.cause.value == "컷인"

    multi_text = "[화자1] 아 오늘 점심 뭐 먹지\n[화자2] 방금 선릉역 앞에서 보행자가 갑자기 나와서 급정거했습니다"
    multi = extractor.extract(multi_text)
    assert seen[1]["messages"][0]["content"].startswith(MULTI_SPEAKER_SYSTEM_PROMPT.split("{terms}")[0])
    assert multi.cause.value == "보행자 돌출"
    assert multi.cause.evidence == "보행자가 갑자기 나와서 급정거했습니다"
    assert multi.location.value == "선릉역"


def test_select_driver_prefers_evidence_then_falls_back_to_heuristic() -> None:
    transcript = Transcript(
        text="전방에 과속단속 구간입니다 좌회전하세요 방금 교차로에서 앞차가 급제동해서 브레이크 밟았어요",
        words=[],
        segments=[
            TranscriptSegment(speaker="Speaker 1", text="전방에 과속단속 구간입니다 좌회전하세요", start=0.0, end=2.0),
            TranscriptSegment(
                speaker="Speaker 2",
                text="방금 교차로에서 앞차가 급제동해서 브레이크 밟았어요",
                start=2.4,
                end=5.0,
            ),
        ],
        language="ko",
        provider="gateway",
    )
    prep = prepare_speaker_transcript(transcript)

    driver_text, label = select_driver_text(prep, ["급제동해서 브레이크 밟았어요", "교차로에서"])
    assert label == "화자2"
    assert driver_text == "방금 교차로에서 앞차가 급제동해서 브레이크 밟았어요"

    fallback_text, fallback_label = select_driver_text(prep, [None, None, None])
    assert fallback_label == "화자2"
    assert "급제동" in fallback_text


def test_pipeline_merges_driver_turns_and_ignores_passenger_and_nav(
    db: Session,
    settings: Settings,
    tmp_path: Path,
    accounts: dict[str, uuid.UUID],
) -> None:
    audio = _audio_with_segments(
        tmp_path,
        [
            {"speaker": "Speaker 1", "text": "아 깜짝이야 커피 쏟을 뻔했네", "start_ms": 0, "end_ms": 1500},
            {"speaker": "Speaker 2", "text": "방금 강남대로에서 직진하고 있었는데", "start_ms": 1800, "end_ms": 3400},
            {
                "speaker": "Speaker 3",
                "text": "전방에 좌회전하세요 목적지 안내를 시작합니다",
                "start_ms": 3600,
                "end_ms": 5100,
            },
            {
                "speaker": "Speaker 2",
                "text": "검은 차가 갑자기 컷인해서 급제동했습니다",
                "start_ms": 5400,
                "end_ms": 7800,
            },
        ],
    )
    issue = run_pipeline(db, settings, user_id=accounts["operator"], audio_path=audio, recorded_at=None)
    assert issue.status == "draft"
    ext = issue.ai_extraction
    assert ext["location"]["value"] == "강남대로"
    assert ext["location"]["span"] is not None
    assert ext["cause"]["value"] == "컷인"
    assert ext["cause"]["span"] is not None
    assert ext["event_type"]["value"] == "cut_in"
    assert issue.pipeline_meta["speakers"]["count"] == 3
    assert issue.pipeline_meta["speakers"]["driver"] == "화자2"
    assert issue.recording.transcript.words[0]["speaker"] == "Speaker 1"
