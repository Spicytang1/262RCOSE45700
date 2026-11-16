"""게이트웨이 STT 실호출.

GATEWAY_API_KEY 가 없으면 요청하지 않고 끝난다. 테스트 스위트에서는 호출하지 않는다.

    cd backend
    uv run python -m scripts.stt_smoke path/to/clip.webm
    uv run python -m scripts.stt_smoke path/to/clip.wav --model stt-async-v6
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.adapters.audio import AudioNormalizeError
from app.adapters.gateway.errors import GatewayError
from app.adapters.stt.factory import get_stt_adapter
from app.config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="게이트웨이 STT 실호출. 키가 있을 때만 요청합니다.")
    parser.add_argument("audio", nargs="?", type=Path, help="wav, mp3, m4a, webm 등")
    parser.add_argument("--model", choices=["stt-async-v5", "stt-async-v6"])
    args = parser.parse_args(argv)

    settings = Settings()
    if not settings.gateway_api_key.strip():
        print("GATEWAY_API_KEY 가 없어 스모크를 건너뜁니다.")
        return 0
    if args.audio is None:
        print("오디오 파일 경로가 필요합니다.", file=sys.stderr)
        return 2
    if not args.audio.is_file():
        print(f"오디오 파일을 찾을 수 없습니다: {args.audio}", file=sys.stderr)
        return 2

    updates: dict[str, str] = {"stt_provider": "gateway"}
    if args.model:
        updates["stt_model"] = args.model
    adapter = get_stt_adapter(settings.model_copy(update=updates))
    try:
        transcript = adapter.transcribe(args.audio, [])
    except (GatewayError, AudioNormalizeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(transcript.text)
    print(f"provider={transcript.provider} language={transcript.language} words={len(transcript.words)}")
    for word in transcript.words:
        print(f"{word.start:.3f}\t{word.end:.3f}\t{word.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
