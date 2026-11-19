"""STT 후보를 비교한다. 가짜 음성 파일은 만들지 않는다.

--source split 은 data/ 에 있는 정답·가설 텍스트만 비교한다.
--source dataset 은 eval/dataset/audio 의 실제 녹음을 어댑터로 옮긴다. 파일이 없으면 건너뛴다.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from app.adapters.stt.factory import get_stt_adapter
from app.config import Settings
from app.services.glossary import correct_text, load_glossary

from eval.augment_noise import DATASET
from eval.common import cer, load_items, mean_std
from eval.run_eval import audio_for, load_scripts
from eval.stt_metrics import term_recall


def evaluate_split(items: list[dict[str, object]]) -> dict[str, str]:
    glossary = load_glossary()
    cer_scores: list[float] = []
    hint_off: list[float] = []
    for item in items:
        reference = str(item["reference_text"])
        hypothesis = correct_text(str(item["hypothesis_text"]), glossary)
        cer_scores.append(cer(reference, hypothesis))
        score = term_recall(reference, hypothesis, glossary.terms)
        if score is not None:
            hint_off.append(score)
    return {"CER": mean_std(cer_scores), "term_recall": mean_std(hint_off), "samples": str(len(items))}


def evaluate_files(provider: str, audio_dir: Path) -> dict[str, str]:
    settings = Settings(_env_file=None, stt_provider=provider)  # type: ignore[arg-type]
    adapter = get_stt_adapter(settings)
    glossary = load_glossary()
    cer_scores: list[float] = []
    recalls: list[float] = []
    latencies: list[float] = []
    missing = 0
    for item in load_scripts():
        audio = audio_for(str(item["id"]), "original", audio_dir)
        if audio is None:
            missing += 1
            continue
        started = time.perf_counter()
        transcript = adapter.transcribe(audio, [])
        latencies.append(time.perf_counter() - started)
        corrected = correct_text(transcript.text, glossary)
        reference = str(item["script"])
        cer_scores.append(cer(reference, corrected))
        score = term_recall(reference, corrected, glossary.terms)
        if score is not None:
            recalls.append(score)
    cost = "0 (mock)" if provider == "mock" else "STT 6cr/min, 용어 힌트 없음"
    return {
        "CER": mean_std(cer_scores),
        "term_recall": mean_std(recalls),
        "latency_s": mean_std(latencies),
        "missing": str(missing),
        "hints": str(adapter.capabilities.supports_hints),
        "cost": cost,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STT 비교. 실제 파일이 없으면 만들지 않고 건너뜁니다.")
    parser.add_argument("--source", choices=["dataset", "split"], default="dataset")
    parser.add_argument("--providers", default="mock")
    parser.add_argument("--split", default="tune", choices=["tune", "test", "demo"])
    parser.add_argument("--audio-dir", type=Path, default=DATASET / "audio")
    args = parser.parse_args(argv)
    if args.source == "split":
        summary = evaluate_split(load_items(args.split, None))
        print(
            f"split={args.split}\tCER {summary['CER']}\tterm_recall {summary['term_recall']}\t"
            f"samples {summary['samples']}"
        )
        return 0
    for provider in [item.strip() for item in args.providers.split(",") if item.strip()]:
        summary = evaluate_files(provider, args.audio_dir)
        print(
            f"{provider}\tCER {summary['CER']}\tterm_recall {summary['term_recall']}\t"
            f"latency {summary['latency_s']}\tmissing {summary['missing']}\t"
            f"hints {summary['hints']}\t{summary['cost']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
