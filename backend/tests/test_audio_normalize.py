from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest
from app.adapters.audio import AudioNormalizeError, normalize_for_stt


def write_pcm(path: Path, *, rate: int, seconds: float, channels: int = 1) -> None:
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames * channels)


def assert_16k_mono_wav(path: Path) -> None:
    with wave.open(str(path)) as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 16000
        assert handle.getsampwidth() == 2
        assert handle.getnframes() > 0


def test_wav_is_resampled_to_16k_mono(tmp_path: Path) -> None:
    source = tmp_path / "in.wav"
    write_pcm(source, rate=8000, seconds=0.4, channels=2)
    result = normalize_for_stt(source, max_bytes=25 * 1024 * 1024, work_dir=tmp_path)
    try:
        assert result.content_type == "audio/wav"
        assert result.filename == "audio.wav"
        assert_16k_mono_wav(result.path)
        assert source.stat().st_size > 0
    finally:
        result.cleanup()


def test_webm_is_transcoded_to_wav(tmp_path: Path) -> None:
    source = tmp_path / "sample.webm"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.4",
            "-c:a",
            "libopus",
            "-b:a",
            "32k",
            str(source),
        ],
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = normalize_for_stt(source, max_bytes=25 * 1024 * 1024, work_dir=tmp_path)
    try:
        assert result.content_type == "audio/wav"
        assert_16k_mono_wav(result.path)
    finally:
        result.cleanup()


def test_over_limit_wav_falls_back_to_mp3(tmp_path: Path) -> None:
    source = tmp_path / "long.wav"
    write_pcm(source, rate=8000, seconds=2)
    # 16kHz mono pcm 은 약 64KB 라 한도를 넘고, 64kbps mp3 는 들어간다.
    result = normalize_for_stt(source, max_bytes=50_000, work_dir=tmp_path)
    try:
        assert result.content_type == "audio/mpeg"
        assert result.filename == "audio.mp3"
        assert result.path.stat().st_size + 8 * 1024 <= 50_000
    finally:
        result.cleanup()


def test_audio_that_cannot_fit_raises(tmp_path: Path) -> None:
    source = tmp_path / "long.wav"
    write_pcm(source, rate=8000, seconds=2)
    with pytest.raises(AudioNormalizeError, match="한도"):
        normalize_for_stt(source, max_bytes=10_000, work_dir=tmp_path)
    assert list(tmp_path.glob("stt-*")) == []


def test_empty_file_raises(tmp_path: Path) -> None:
    source = tmp_path / "empty.webm"
    source.write_bytes(b"")
    with pytest.raises(AudioNormalizeError, match="비어"):
        normalize_for_stt(source, max_bytes=25 * 1024 * 1024, work_dir=tmp_path)


def test_missing_ffmpeg_raises(tmp_path: Path) -> None:
    source = tmp_path / "in.wav"
    write_pcm(source, rate=8000, seconds=0.2)
    with pytest.raises(AudioNormalizeError, match="ffmpeg"):
        normalize_for_stt(source, max_bytes=25 * 1024 * 1024, ffmpeg_bin="ffmpeg-not-installed", work_dir=tmp_path)


def test_undecodable_bytes_raise(tmp_path: Path) -> None:
    source = tmp_path / "bad.webm"
    source.write_bytes(b"this is not audio")
    with pytest.raises(AudioNormalizeError, match="ffmpeg 변환에 실패"):
        normalize_for_stt(source, max_bytes=25 * 1024 * 1024, work_dir=tmp_path)
