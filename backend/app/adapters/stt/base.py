from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.common import WordToken


class STTCapabilities(BaseModel):
    supports_hints: bool
    supports_word_confidence: bool
    supports_word_timestamps: bool


class TranscriptSegment(BaseModel):
    speaker: str | None = None
    text: str
    start: float
    end: float


class Transcript(BaseModel):
    text: str
    words: list[WordToken]
    language: str
    provider: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


class STTAdapter:
    provider_name: str

    @property
    def capabilities(self) -> STTCapabilities:
        raise NotImplementedError

    def transcribe(self, audio_path: Path, hints: list[str]) -> Transcript:
        raise NotImplementedError
