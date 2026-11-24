"""번갈아 말한 화자 구간 정리.

- 화자가 하나뿐이면 원문 흐름을 그대로 둔다.
- 둘 이상이면 연속된 같은 화자 구간을 묶고 용어 보정을 적용한 뒤
  `[화자1] ...` 줄바꿈 텍스트를 만든다.
- 추출된 근거가 어느 화자 발화에 속하는지 보고 운전자 발화만 골라 분류에 넘긴다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.adapters.stt.base import Transcript
from app.services.glossary import Glossary, correct_text

SPEAKER_TAG_RE = re.compile(r"^\[(화자\d+)\]\s*")
SPEAKER_LINE_RE = re.compile(r"^\[(화자\d+)\]\s+(.+)$", re.MULTILINE)

DRIVER_POSITIVE_CUES = (
    "급제동",
    "급정거",
    "급감속",
    "급가속",
    "과조향",
    "컷인",
    "끼어들",
    "끼어 들",
    "보행자",
    "이륜차",
    "오토바이",
    "자전거",
    "킥보드",
    "불법주정차",
    "이중주차",
    "라바콘",
    "공사",
    "신호등",
    "신호위반",
    "교차로",
    "합류로",
    "직선로",
    "곡선로",
    "횡단보도",
    "브레이크",
    "차선",
    "핸들",
    "운전",
    "직진",
    "좌회전",
    "우회전",
    "유턴",
    "정차",
    "회피",
    "방금",
    "아까",
    "했습니다",
    "했어요",
    "했다",
    "신고",
)

NON_DRIVER_CUES = (
    "목적지",
    "경로 안내",
    "안내를 시작",
    "안내를 종료",
    "좌회전하세요",
    "우회전하세요",
    "직진하세요",
    "유턴하세요",
    "재탐색",
    "제한속도",
    "전방에",
    "라디오",
    "청취자",
    "뉴스",
    "날씨",
    "깜짝이야",
    "놀라",
    "커피",
    "배고프",
    "점심",
    "저녁",
)


@dataclass(frozen=True)
class SpeakerTurn:
    speaker: str
    label: str
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SpeakerPrep:
    is_multi_speaker: bool
    corrected_text: str
    llm_text: str
    turns: list[SpeakerTurn]
    speaker_count: int


def has_speaker_labels(text: str) -> bool:
    labels = {match.group(1) for match in SPEAKER_LINE_RE.finditer(text)}
    return len(labels) >= 2


def parse_labelled_turns(text: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for line in text.splitlines():
        matched = SPEAKER_LINE_RE.match(line.strip())
        if matched:
            turns.append((matched.group(1), matched.group(2).strip()))
    return turns


def strip_speaker_tag(text: str) -> str:
    return SPEAKER_TAG_RE.sub("", text.strip(), count=1)


def prepare_speaker_transcript(transcript: Transcript, glossary: Glossary | None = None) -> SpeakerPrep:
    raw_turns = _raw_turns(transcript)
    distinct = {speaker for speaker, _text, _start, _end in raw_turns if speaker}
    if len(distinct) <= 1:
        corrected = correct_text(transcript.text, glossary)
        count = 1 if (distinct or transcript.text.strip()) else 0
        return SpeakerPrep(
            is_multi_speaker=False,
            corrected_text=corrected,
            llm_text=corrected,
            turns=[],
            speaker_count=count,
        )

    merged: list[tuple[str, list[str], float, float]] = []
    for speaker, text, start, end in raw_turns:
        cleaned = text.strip()
        if not cleaned:
            continue
        key = speaker or "unknown"
        if merged and merged[-1][0] == key:
            merged[-1][1].append(cleaned)
            merged[-1] = (key, merged[-1][1], merged[-1][2], max(merged[-1][3], end))
        else:
            merged.append((key, [cleaned], start, end))

    labels: dict[str, str] = {}
    turns: list[SpeakerTurn] = []
    for key, parts, start, end in merged:
        if key not in labels:
            labels[key] = f"화자{len(labels) + 1}"
        corrected_turn = correct_text(" ".join(parts), glossary)
        if not corrected_turn:
            continue
        turns.append(SpeakerTurn(speaker=key, label=labels[key], text=corrected_turn, start=start, end=end))

    corrected_text = " ".join(turn.text for turn in turns)
    llm_text = "\n".join(f"[{turn.label}] {turn.text}" for turn in turns)
    return SpeakerPrep(
        is_multi_speaker=len({turn.label for turn in turns}) >= 2,
        corrected_text=corrected_text,
        llm_text=llm_text,
        turns=turns,
        speaker_count=len(distinct),
    )


def select_driver_text(prep: SpeakerPrep, evidences: list[str | None]) -> tuple[str, str | None]:
    if not prep.is_multi_speaker or not prep.turns:
        return prep.corrected_text, None

    hits: dict[str, int] = {}
    first_order: dict[str, int] = {}
    for index, turn in enumerate(prep.turns):
        first_order.setdefault(turn.label, index)
        for evidence in evidences:
            if evidence and evidence in turn.text:
                hits[turn.label] = hits.get(turn.label, 0) + 1

    if hits:
        chosen_label = max(hits, key=lambda label: (hits[label], -first_order[label]))
    else:
        chosen_label = pick_driver_label([(turn.label, turn.text) for turn in prep.turns])

    merged = " ".join(turn.text for turn in prep.turns if turn.label == chosen_label)
    return (merged or prep.corrected_text), chosen_label


def pick_driver_label(turns: list[tuple[str, str]]) -> str:
    if not turns:
        return ""
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for label, text in turns:
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(text)

    scored: list[tuple[int, int, str]] = []
    for index, label in enumerate(order):
        combined = " ".join(grouped[label])
        score = _driver_score(combined)
        scored.append((score, -index, label))
    return max(scored)[2]


def _driver_score(text: str) -> int:
    pos = sum(2 for cue in DRIVER_POSITIVE_CUES if cue in text)
    neg = sum(3 for cue in NON_DRIVER_CUES if cue in text)
    return pos - neg


def _raw_turns(transcript: Transcript) -> list[tuple[str | None, str, float, float]]:
    if transcript.segments:
        return [
            (segment.speaker, segment.text, segment.start, segment.end)
            for segment in transcript.segments
            if segment.text.strip()
        ]
    if not any(word.speaker for word in transcript.words):
        return []
    grouped: list[tuple[str | None, list[str], float, float]] = []
    for word in transcript.words:
        if not word.text.strip():
            continue
        if grouped and grouped[-1][0] == word.speaker:
            grouped[-1][1].append(word.text)
            grouped[-1] = (word.speaker, grouped[-1][1], grouped[-1][2], max(grouped[-1][3], word.end))
        else:
            grouped.append((word.speaker, [word.text], word.start, word.end))
    return [(speaker, " ".join(tokens), start, end) for speaker, tokens, start, end in grouped]
