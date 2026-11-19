"""조용한 녹음에 차 실내 소음을 SNR 별로 섞는다.

사용자 소음 파일이 없으면 갈색·핑크 잡음과 저역 럼블을 만든다.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import yaml

from eval.common import backend_root

DATASET = backend_root() / "eval" / "dataset"


def load_eval_config() -> dict[str, object]:
    return yaml.safe_load((DATASET / "eval_config.yaml").read_text(encoding="utf-8"))


def synthetic_cabin_noise(sample_count: int, sample_rate: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(sample_count)
    brown = np.cumsum(white)
    brown = brown / (np.max(np.abs(brown)) + 1e-9)
    pink = _pink_from_white(white)
    time_axis = np.arange(sample_count) / sample_rate
    rumble = 0.35 * np.sin(2 * np.pi * 48 * time_axis) + 0.15 * np.sin(2 * np.pi * 97 * time_axis)
    noise = 0.55 * brown + 0.3 * pink + 0.15 * rumble
    return _normalize(noise)


def mix_at_snr(signal: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    if noise.size == 0 or signal.size == 0:
        raise ValueError("신호와 소음이 비어 있습니다.")
    repeated = np.resize(noise, signal.shape)
    signal_rms = _rms(signal)
    noise_rms = _rms(repeated)
    target_rms = signal_rms / (10 ** (snr_db / 20))
    mixed = signal + repeated * (target_rms / noise_rms)
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.99:
        mixed = mixed / peak * 0.99
    return mixed.astype(np.float32)


def measured_snr_db(signal: np.ndarray, mixed: np.ndarray) -> float:
    noise = mixed[: signal.size] - signal[: mixed.size]
    return 20 * np.log10((_rms(signal) + 1e-9) / (_rms(noise) + 1e-9))


def augment_directory(
    source_dir: Path,
    output_root: Path,
    *,
    snr_levels: list[float],
    noise_path: Path | None,
    sample_rate: int,
    ffmpeg_bin: str = "ffmpeg",
) -> list[Path]:
    written: list[Path] = []
    sources = sorted(path for path in source_dir.glob("s*.*") if "_car" not in path.stem and path.suffix != "")
    for source in sources:
        if source.parent == output_root or "noise" in source.parts:
            continue
        signal, rate = load_mono(source, sample_rate, ffmpeg_bin)
        noise = _load_noise(noise_path, signal.size, rate, ffmpeg_bin, seed=abs(hash(source.stem)) % 10_000)
        for snr in snr_levels:
            destination = output_root / f"{int(snr)}dB" / f"{source.stem}.wav"
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_wav(destination, mix_at_snr(signal, noise, snr), rate)
            written.append(destination)
    return written


def load_mono(path: Path, sample_rate: int, ffmpeg_bin: str) -> tuple[np.ndarray, int]:
    if shutil.which(ffmpeg_bin):
        command = [
            ffmpeg_bin,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "f32le",
            "-",
        ]
        completed = subprocess.run(command, check=False, capture_output=True)
        if completed.returncode == 0 and completed.stdout:
            return np.frombuffer(completed.stdout, dtype=np.float32).copy(), sample_rate
    if path.suffix.lower() != ".wav":
        raise RuntimeError(f"ffmpeg 없이 {path.name} 을 읽지 못했습니다.")
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
        width = handle.getsampwidth()
        channels = handle.getnchannels()
    if width != 2:
        raise RuntimeError("wav 는 16-bit 여야 합니다.")
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, rate


def main(argv: list[str] | None = None) -> int:
    config = load_eval_config()
    noise_config = config["noise"]
    parser = argparse.ArgumentParser(description="녹음에 차 실내 소음을 섞습니다.")
    parser.add_argument("--input-dir", type=Path, default=DATASET / "audio")
    parser.add_argument("--output-dir", type=Path, default=DATASET / "audio" / "noise")
    parser.add_argument("--noise", type=Path, default=None, help="차 실내 소음 wav/m4a. 없으면 합성 소음")
    parser.add_argument("--snr", default=",".join(str(item) for item in noise_config["snr_db"]))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    levels = [float(item) for item in args.snr.split(",") if item.strip()]
    written = augment_directory(
        args.input_dir,
        args.output_dir,
        snr_levels=levels,
        noise_path=args.noise,
        sample_rate=int(noise_config["sample_rate"]),
        ffmpeg_bin=args.ffmpeg,
    )
    if not written:
        print("섞을 조용한 녹음이 없습니다. audio/s01.m4a 형식의 파일을 넣은 뒤 다시 실행하세요.")
        return 0
    print(f"{len(written)}개 파일을 썼습니다.")
    return 0


def _load_noise(
    noise_path: Path | None,
    sample_count: int,
    sample_rate: int,
    ffmpeg_bin: str,
    seed: int,
) -> np.ndarray:
    if noise_path is not None:
        noise, _rate = load_mono(noise_path, sample_rate, ffmpeg_bin)
        return noise
    return synthetic_cabin_noise(sample_count, sample_rate, seed)


def _pink_from_white(white: np.ndarray) -> np.ndarray:
    # Paul Kellet 의 간단한 핑크 필터 근사.
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    output = np.zeros_like(white)
    for index in range(len(white)):
        value = b[0] * white[index]
        if index >= 1:
            value += b[1] * white[index - 1] - a[1] * output[index - 1]
        if index >= 2:
            value += b[2] * white[index - 2] - a[2] * output[index - 2]
        if index >= 3:
            value += b[3] * white[index - 3] - a[3] * output[index - 3]
        output[index] = value
    return _normalize(output)


def _normalize(values: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(values))) + 1e-9
    return (values / peak).astype(np.float32)


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values.astype(np.float64)))))


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    pcm = np.clip(samples, -1, 1)
    frames = (pcm * 32767).astype(np.int16).tobytes()
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)


if __name__ == "__main__":
    raise SystemExit(main())
