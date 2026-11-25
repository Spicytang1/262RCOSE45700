from __future__ import annotations

import json
import re
from pathlib import Path

from app.adapters.stt.base import STTAdapter, STTCapabilities, Transcript, TranscriptSegment
from app.schemas.common import WordToken

FIXED_TRANSCRIPT = "강남대로에서 검은 차가 컷 인해서 급제동했다. 라바 콘이 쓰러져 있었다."


def sidecar_candidates(audio_path: Path) -> list[Path]:
    return [
        Path(str(audio_path) + ".transcript.txt"),
        audio_path.with_name(f"{audio_path.stem}.transcript.txt"),
    ]


def segment_sidecar_candidates(audio_path: Path) -> list[Path]:
    return [
        Path(str(audio_path) + ".segments.json"),
        audio_path.with_name(f"{audio_path.stem}.segments.json"),
    ]


def words_for(text: str, *, speaker: str | None = None, start_offset: float = 0.0) -> list[WordToken]:
    tokens = re.findall(r"\S+", text)
    words: list[WordToken] = []
    for index, token in enumerate(tokens):
        start = round(start_offset + index * 0.4, 3)
        confidence = 0.4 if index == 0 and speaker is None else 0.95
        words.append(
            WordToken(text=token, start=start, end=round(start + 0.35, 3), confidence=confidence, speaker=speaker)
        )
    return words


class MockSTT(STTAdapter):
    provider_name = "mock"

    @property
    def capabilities(self) -> STTCapabilities:
        return STTCapabilities(
            supports_hints=True,
            supports_word_confidence=True,
            supports_word_timestamps=True,
        )

    def transcribe(self, audio_path: Path, hints: list[str]) -> Transcript:
        del hints
        for candidate in segment_sidecar_candidates(audio_path):
            if candidate.is_file():
                return _from_segment_sidecar(candidate, self.provider_name)
        text = FIXED_TRANSCRIPT
        for candidate in sidecar_candidates(audio_path):
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8").strip()
                break
        return Transcript(text=text, words=words_for(text), language="ko", provider=self.provider_name)


def _from_segment_sidecar(path: Path, provider: str) -> Transcript:
    raw = json.loads(path.read_text(encoding="utf-8"))
    segments: list[TranscriptSegment] = []
    words: list[WordToken] = []
    texts: list[str] = []
    cursor = 0.0
    for item in raw:
        seg_text = str(item["text"]).strip()
        if not seg_text:
            continue
        speaker = item.get("speaker")
        speaker_str = str(speaker).strip() if speaker is not None and str(speaker).strip() else None
        start = round(float(item["start_ms"]) / 1000, 3) if "start_ms" in item else cursor
        end = round(float(item["end_ms"]) / 1000, 3) if "end_ms" in item else round(start + 1.0, 3)
        segments.append(TranscriptSegment(speaker=speaker_str, text=seg_text, start=start, end=end))
        words.extend(words_for(seg_text, speaker=speaker_str, start_offset=start))
        texts.append(seg_text)
        cursor = end + 0.2
    return Transcript(
        text=" ".join(texts),
        words=words,
        segments=segments,
        language="ko",
        provider=provider,
    )
