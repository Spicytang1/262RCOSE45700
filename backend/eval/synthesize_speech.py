"""대본을 학교 게이트웨이 TTS 로 만든다. 이미 있는 wav 는 다시 호출하지 않는다."""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

from app.adapters.gateway.client import GatewayClient
from app.adapters.gateway.errors import GatewayError
from app.config import Settings

from eval.augment_noise import DATASET, load_eval_config
from eval.common import select_scripts

SPEECH_PATH = "audio/speech/"


def pcm_to_wav(pcm: bytes, destination: Path, *, sample_rate: int, channels: int, sample_width: int) -> None:
    trimmed = pcm[: len(pcm) - (len(pcm) % sample_width)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sample_width)
        handle.setframerate(sample_rate)
        handle.writeframes(trimmed)


def synthesize_scripts(
    client: GatewayClient,
    scripts: list[dict[str, object]],
    output_root: Path,
    *,
    model: str,
    voices: list[str],
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for item in scripts:
        text = str(item["script"])
        sample_id = str(item["id"])
        for voice in voices:
            destination = output_root / voice / f"{sample_id}.wav"
            if destination.is_file() and destination.stat().st_size > 44:
                skipped += 1
                continue
            pcm = client.post_bytes(
                SPEECH_PATH,
                {"model": model, "input": text, "voice": voice},
            )
            pcm_to_wav(
                pcm,
                destination,
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
            )
            created += 1
    return created, skipped


def main(argv: list[str] | None = None) -> int:
    config = load_eval_config()["tts"]
    parser = argparse.ArgumentParser(description="대본 TTS. GATEWAY_API_KEY 가 있을 때만 호출합니다.")
    parser.add_argument("--voices", default=",".join(config["voices"]))
    parser.add_argument("--model", default=str(config["model"]))
    parser.add_argument("--output-dir", type=Path, default=DATASET / "audio" / "tts")
    parser.add_argument("--ids", default=None, help="쉼표로 구분한 대본 id. 예: s01,s36")
    parser.add_argument("--limit", type=int, default=None, help="앞에서부터 N개만")
    args = parser.parse_args(argv)
    settings = Settings()
    if not settings.gateway_api_key.strip():
        print("GATEWAY_API_KEY 가 없어 TTS 를 건너뜁니다.")
        return 0
    ground = json.loads((DATASET / "ground_truth.json").read_text(encoding="utf-8"))
    voices = [item.strip() for item in args.voices.split(",") if item.strip()]
    scripts = select_scripts(list(ground["scripts"]), args.ids, args.limit)
    try:
        created, skipped = synthesize_scripts(
            GatewayClient.from_settings(settings),
            scripts,
            args.output_dir,
            model=args.model,
            voices=voices,
            sample_rate=int(config["sample_rate"]),
            channels=int(config["channels"]),
            sample_width=int(config["sample_width_bytes"]),
        )
    except GatewayError as exc:
        print(str(exc))
        return 1
    print(f"생성 {created}개, 캐시로 생략 {skipped}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
