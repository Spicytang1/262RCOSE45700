"""게이트웨이 실호출.

GATEWAY_API_KEY 가 없으면 요청하지 않고 끝난다. 테스트 스위트에서는 호출하지 않는다.

    cd backend
    uv run python -m scripts.stt_smoke path/to/clip.webm
    uv run python -m scripts.stt_smoke path/to/clip.wav --model stt-async-v6
    uv run python -m scripts.stt_smoke --text "직진하다가 컷인해서 급제동했습니다."
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.audio import AudioNormalizeError
from app.adapters.classifier.factory import get_classifier
from app.adapters.classifier.gateway_jev import ClassificationFailed
from app.adapters.extractor.factory import get_extractor
from app.adapters.extractor.gateway_claude import ExtractionFailed
from app.adapters.gateway.errors import GatewayError
from app.adapters.stt.factory import get_stt_adapter
from app.config import Settings
from app.domain.taxonomy.questions import build_questions
from app.services.mentioned_time import resolve_mentioned_time
from app.services.state_text import build_state_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="게이트웨이 STT 실호출. 키가 있을 때만 요청합니다.")
    parser.add_argument("audio", nargs="?", type=Path, help="wav, mp3, m4a, webm 등")
    parser.add_argument("--model", choices=["stt-async-v5", "stt-async-v6"])
    parser.add_argument("--text", help="전사문. 있으면 STT 없이 추출 1회, 분류 1회만 호출합니다.")
    args = parser.parse_args(argv)

    settings = Settings()
    if not settings.gateway_api_key.strip():
        print("GATEWAY_API_KEY 가 없어 스모크를 건너뜁니다.")
        return 0
    if args.text is not None:
        return _run_llm(settings, args.text)
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


def _run_llm(settings: Settings, text: str) -> int:
    tuned = settings.model_copy(update={"extractor_provider": "gateway_claude", "classifier_provider": "gateway_jev"})
    try:
        extracted = get_extractor(tuned).extract(text)
        state = build_state_text(text, extracted.cause.value, extracted.location.value)
        classified = get_classifier(tuned).classify(state, build_questions())
    except (GatewayError, ExtractionFailed, ClassificationFailed) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(extracted.model_dump_json(ensure_ascii=False))
    resolved = resolve_mentioned_time(
        text,
        mention=extracted.mentioned_time.value or extracted.mentioned_time.evidence,
        words=None,
        recorded_at=datetime.now(UTC),
    )
    if resolved is None:
        print("mentioned_time_resolved=null")
    else:
        print(resolved.model_dump_json(ensure_ascii=False))
    print(classified.model_dump_json(ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
