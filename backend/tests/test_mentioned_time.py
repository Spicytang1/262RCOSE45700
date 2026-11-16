from datetime import datetime, timedelta

from app.schemas.common import WordToken
from app.services.mentioned_time import TimePhrase, TimeWindows, parse_korean_number, resolve_mentioned_time

WINDOWS = TimeWindows(
    phrases={
        "조금 전": TimePhrase(offset_seconds=90, uncertainty_seconds=120),
        "방금": TimePhrase(offset_seconds=5, uncertainty_seconds=30),
        "아까": TimePhrase(offset_seconds=600, uncertainty_seconds=600),
    },
    units={
        "초": TimePhrase(offset_seconds=1, uncertainty_seconds=5),
        "분": TimePhrase(offset_seconds=60, uncertainty_seconds=20),
    },
)
START = datetime(2026, 11, 16, 9, 0, 0)


def _resolve(text: str, *, mention: str | None = None, words: list[WordToken] | None = None):
    return resolve_mentioned_time(text, mention=mention, words=words, recorded_at=START, windows=WINDOWS)


def test_korean_numbers() -> None:
    assert parse_korean_number("10") == 10
    assert parse_korean_number("십") == 10
    assert parse_korean_number("이십") == 20
    assert parse_korean_number("십오") == 15
    assert parse_korean_number("삼십") == 30
    assert parse_korean_number("이") == 2


def test_numeric_offsets() -> None:
    assert _resolve("30초 전에 합류했다").offset_seconds == 30
    assert _resolve("1분 전에 끼어들었다").offset_seconds == 60
    assert _resolve("십 초 전에 신호가 늦었다").offset_seconds == 10
    assert _resolve("삼십 초 전").offset_seconds == 30


def test_vague_phrases_use_configured_windows() -> None:
    just_now = _resolve("방금 교차로에서")
    assert just_now is not None
    assert just_now.offset_seconds == 5
    assert just_now.uncertainty_seconds == 30
    assert just_now.estimated_at == START - timedelta(seconds=5)
    assert just_now.window_start == just_now.estimated_at - timedelta(seconds=30)
    earlier = _resolve("아까 곡선로")
    assert earlier is not None
    assert earlier.offset_seconds == 600
    bit_ago = _resolve("조금 전에 직선로")
    assert bit_ago is not None
    assert bit_ago.offset_seconds == 90


def test_segment_start_shifts_the_anchor() -> None:
    words = [WordToken(text="방금", start=1.5, end=2.0, confidence=None)]
    resolved = _resolve("방금 교차로에서", words=words)
    assert resolved is not None
    assert resolved.anchor == "segment"
    assert resolved.estimated_at == START + timedelta(seconds=1.5) - timedelta(seconds=5)


def test_mention_prefers_its_own_expression() -> None:
    text = "방금 불법주정차를 피했고, 그전에 십 초 전에 신호가 늦었다."
    resolved = _resolve(text, mention="십 초 전")
    assert resolved is not None
    assert resolved.offset_seconds == 10


def test_missing_expression_is_null() -> None:
    assert _resolve("교차로에서 좌회전했다") is None
