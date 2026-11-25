"""STT 에 넘기기 전 음성을 16kHz mono 로 맞춘다.

학교 게이트웨이는 webm·amr 처럼 길이 메타데이터가 없는 컨테이너를 400 으로 거절한다.
Chrome MediaRecorder webm 은 여기서 wav 로 바꾼 뒤 보낸다. 원본 파일은 건드리지 않는다.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TARGET_SAMPLE_RATE = 16000
DEEPFILTER_SAMPLE_RATE = 48000
FFMPEG_DENOISE_FILTER = "highpass=f=80,afftdn=nf=-25"
MIN_MP3_BITRATE_KBPS = 16
MAX_MP3_BITRATE_KBPS = 64
# multipart 프레이밍이 본문 한도에 걸리지 않도록 남기는 여유.
MULTIPART_MARGIN_BYTES = 8 * 1024
FFMPEG_TIMEOUT_SECONDS = 180

WAV_CONTENT_TYPE = "audio/wav"
MP3_CONTENT_TYPE = "audio/mpeg"

DenoiseMode = Literal["off", "ffmpeg_afftdn", "deepfilternet"]


class AudioNormalizeError(Exception):
    pass


@dataclass
class NormalizedAudio:
    path: Path
    filename: str
    content_type: str
    directory: Path

    def cleanup(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)


def normalize_for_stt(
    source: Path,
    *,
    max_bytes: int,
    ffmpeg_bin: str = "ffmpeg",
    denoise: DenoiseMode = "off",
    denoise_bin: str = "deepFilter",
    work_dir: Path | None = None,
) -> NormalizedAudio:
    if not source.is_file():
        raise AudioNormalizeError(f"오디오 파일을 찾을 수 없습니다: {source.name}")
    if source.stat().st_size == 0:
        raise AudioNormalizeError("오디오 파일이 비어 있습니다.")

    directory = Path(tempfile.mkdtemp(prefix="stt-", dir=work_dir))
    wav_path = directory / "audio.wav"
    try:
        input_path = source
        filter_args: list[str] = []
        if denoise == "ffmpeg_afftdn":
            filter_args = ["-af", FFMPEG_DENOISE_FILTER]
        elif denoise == "deepfilternet":
            input_path = _run_deepfilternet(ffmpeg_bin, denoise_bin, source, directory)

        _run_ffmpeg(
            ffmpeg_bin,
            input_path,
            wav_path,
            [*filter_args, "-c:a", "pcm_s16le", "-f", "wav"],
        )
        if _fits(wav_path.stat().st_size, max_bytes):
            return NormalizedAudio(
                path=wav_path,
                filename="audio.wav",
                content_type=WAV_CONTENT_TYPE,
                directory=directory,
            )
        bitrate = _mp3_bitrate_kbps(_wav_duration_seconds(wav_path), max_bytes)
        mp3_path = directory / "audio.mp3"
        _run_ffmpeg(
            ffmpeg_bin,
            input_path,
            mp3_path,
            [*filter_args, "-c:a", "libmp3lame", "-b:a", f"{bitrate}k"],
        )
        wav_path.unlink(missing_ok=True)
        if not _fits(mp3_path.stat().st_size, max_bytes):
            raise AudioNormalizeError(_too_large_message(max_bytes))
        return NormalizedAudio(
            path=mp3_path,
            filename="audio.mp3",
            content_type=MP3_CONTENT_TYPE,
            directory=directory,
        )
    except AudioNormalizeError:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def _run_deepfilternet(ffmpeg_bin: str, denoise_bin: str, source: Path, directory: Path) -> Path:
    df_in = directory / "df_in.wav"
    df_out_dir = directory / "df_out"
    df_out_dir.mkdir(exist_ok=True)
    _run_ffmpeg(
        ffmpeg_bin,
        source,
        df_in,
        ["-c:a", "pcm_s16le", "-f", "wav"],
        sample_rate=DEEPFILTER_SAMPLE_RATE,
    )
    try:
        completed = subprocess.run(
            [denoise_bin, "-o", str(df_out_dir), str(df_in)],
            check=False,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise AudioNormalizeError(
            f"DeepFilterNet 실행 파일을 찾을 수 없습니다 ({denoise_bin}). STT_DENOISE_BIN 을 확인하세요."
        ) from None
    except subprocess.TimeoutExpired:
        raise AudioNormalizeError("DeepFilterNet 잡음 제거 시간이 초과되었습니다.") from None
    candidates = sorted(df_out_dir.glob("*.wav"))
    if completed.returncode != 0 or not candidates or candidates[0].stat().st_size == 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        tail = detail[-400:] if detail else "출력 없음"
        raise AudioNormalizeError(f"DeepFilterNet 잡음 제거에 실패했습니다: {tail}")
    return candidates[0]


def _fits(size: int, max_bytes: int) -> bool:
    return size + MULTIPART_MARGIN_BYTES <= max_bytes


def _too_large_message(max_bytes: int) -> str:
    limit_mb = max(max_bytes // (1024 * 1024), 1)
    return f"정규화한 오디오가 STT 본문 한도({limit_mb}MB)를 넘습니다. 녹음을 더 짧게 나누어 주세요."


def _wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            frames = handle.getnframes()
    except wave.Error:
        raise AudioNormalizeError("변환한 wav 의 길이를 읽지 못했습니다.") from None
    if rate <= 0:
        raise AudioNormalizeError("변환한 wav 의 샘플레이트를 읽지 못했습니다.")
    return frames / rate


def _mp3_bitrate_kbps(duration_seconds: float, max_bytes: int) -> int:
    budget = max_bytes - MULTIPART_MARGIN_BYTES
    if budget <= 0 or duration_seconds <= 0:
        raise AudioNormalizeError(_too_large_message(max_bytes))
    kbps = int(budget * 8 / duration_seconds / 1000)
    if kbps < MIN_MP3_BITRATE_KBPS:
        raise AudioNormalizeError(_too_large_message(max_bytes))
    return min(kbps, MAX_MP3_BITRATE_KBPS)


def _run_ffmpeg(
    ffmpeg_bin: str,
    source: Path,
    destination: Path,
    codec_args: list[str],
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
) -> None:
    command = [
        ffmpeg_bin,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        *codec_args,
        str(destination),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise AudioNormalizeError(
            f"ffmpeg 를 찾을 수 없습니다 ({ffmpeg_bin}). PATH 또는 FFMPEG_BIN 을 확인하세요."
        ) from None
    except subprocess.TimeoutExpired:
        raise AudioNormalizeError("ffmpeg 변환 시간이 초과되었습니다.") from None
    if completed.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        tail = detail[-400:] if detail else "출력 없음"
        raise AudioNormalizeError(f"ffmpeg 변환에 실패했습니다: {tail}")
