"""상대 시각 표현을 녹음 시각 기준의 추정 시각으로 바꾼다. LLM 을 쓰지 않는다."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.schemas.common import ResolvedMentionedTime, WordToken

_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_NUMBER = r"(?:\d+|[일이삼사오육칠팔구십백]+)"
_NUMERIC = re.compile(rf"(?P<num>{_NUMBER})\s*(?P<unit>초|분)\s*전")


class TimePhrase(BaseModel):
    offset_seconds: float
    uncertainty_seconds: float


class TimeWindows(BaseModel):
    phrases: dict[str, TimePhrase]
    units: dict[str, TimePhrase]


class _Match(BaseModel):
    expression: str
    start: int
    offset_seconds: float
    uncertainty_seconds: float
    specific: bool = False


def time_windows_path() -> Path:
    return Path(__file__).resolve().parents[1] / "domain" / "time_windows.yaml"


@lru_cache
def load_time_windows() -> TimeWindows:
    raw = yaml.safe_load(time_windows_path().read_text(encoding="utf-8"))
    phrases = {
        key: TimePhrase(offset_seconds=value["offset_seconds"], uncertainty_seconds=value["uncertainty_seconds"])
        for key, value in raw["phrases"].items()
    }
    units = {}
    for unit, value in raw["units"].items():
        units[unit] = TimePhrase(
            offset_seconds=float(value["multiplier"]),
            uncertainty_seconds=float(value["uncertainty_seconds"]),
        )
    return TimeWindows(phrases=phrases, units=units)


def parse_korean_number(raw: str) -> int | None:
    text = "".join(raw.split())
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "백" in text:
        left, _, right = text.partition("백")
        if left and left not in _DIGITS:
            return None
        hundreds = _DIGITS.get(left, 1) if left else 1
        rest = _under_hundred(right) if right else 0
        if rest is None:
            return None
        return hundreds * 100 + rest
    return _under_hundred(text)


def resolve_mentioned_time(
    transcript: str,
    *,
    mention: str | None,
    words: list[WordToken] | None,
    recorded_at: datetime,
    windows: TimeWindows | None = None,
) -> ResolvedMentionedTime | None:
    spec = windows or load_time_windows()
    chosen = _choose_match(transcript, mention, spec)
    if chosen is None:
        return None
    segment_start = _word_start_at(transcript, words or [], chosen.start)
    anchor_name = "segment" if segment_start is not None else "recording_start"
    anchor_at = recorded_at if segment_start is None else recorded_at + timedelta(seconds=segment_start)
    estimated = anchor_at - timedelta(seconds=chosen.offset_seconds)
    uncertainty = timedelta(seconds=chosen.uncertainty_seconds)
    return ResolvedMentionedTime(
        expression=chosen.expression,
        offset_seconds=chosen.offset_seconds,
        uncertainty_seconds=chosen.uncertainty_seconds,
        anchor=anchor_name,
        estimated_at=estimated,
        window_start=estimated - uncertainty,
        window_end=estimated + uncertainty,
    )


def _under_hundred(text: str) -> int | None:
    if not text:
        return 0
    if "십" not in text:
        if len(text) == 1 and text in _DIGITS:
            return _DIGITS[text]
        return None
    left, _, right = text.partition("십")
    if left and left not in _DIGITS:
        return None
    tens = _DIGITS.get(left, 1) if left else 1
    if not right:
        ones = 0
    elif len(right) == 1 and right in _DIGITS:
        ones = _DIGITS[right]
    else:
        return None
    return tens * 10 + ones


def _choose_match(transcript: str, mention: str | None, windows: TimeWindows) -> _Match | None:
    matches = _find_matches(transcript, windows)
    if not matches and mention:
        matches = _find_matches(mention, windows)
    if mention:
        focused = [item for item in matches if item.expression in mention or mention in item.expression]
        focused_specific = any(item.specific for item in focused)
        any_specific = any(item.specific for item in matches)
        if focused and (focused_specific or not any_specific):
            matches = focused
    return _prefer_specific(matches)


def _find_matches(text: str, windows: TimeWindows) -> list[_Match]:
    matches: list[_Match] = []
    for phrase in sorted(windows.phrases, key=len, reverse=True):
        spec = windows.phrases[phrase]
        pattern = re.compile(r"\s*".join(re.escape(part) for part in phrase.split()))
        for found in pattern.finditer(text):
            matches.append(
                _Match(
                    expression=found.group(0),
                    start=found.start(),
                    offset_seconds=spec.offset_seconds,
                    uncertainty_seconds=spec.uncertainty_seconds,
                    specific=False,
                )
            )
    for found in _NUMERIC.finditer(text):
        number = parse_korean_number(found.group("num"))
        unit = windows.units.get(found.group("unit"))
        if number is None or unit is None:
            continue
        matches.append(
            _Match(
                expression=found.group(0),
                start=found.start(),
                offset_seconds=number * unit.offset_seconds,
                uncertainty_seconds=unit.uncertainty_seconds,
                specific=True,
            )
        )
    return matches


def _prefer_specific(matches: list[_Match]) -> _Match | None:
    if not matches:
        return None
    return min(matches, key=lambda item: (0 if item.specific else 1, item.start))


def _word_start_at(transcript: str, words: list[WordToken], char_index: int) -> float | None:
    cursor = 0
    for word in words:
        index = transcript.find(word.text, cursor)
        if index < 0:
            continue
        end = index + len(word.text)
        if index <= char_index < end:
            return word.start
        cursor = end
    return None
