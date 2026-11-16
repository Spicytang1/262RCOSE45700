"""조건별 STT → 용어 보정 → 추출 → 분류 평가.

캐시에 같은 지문이 있으면 그 단계는 호출하지 않는다. --dry-run 은 예상 크레딧만 출력한다.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
from app.adapters.classifier.factory import get_classifier
from app.adapters.extractor.factory import get_extractor
from app.adapters.stt.factory import get_stt_adapter
from app.config import Settings
from app.domain.taxonomy.loader import load_taxonomy
from app.domain.taxonomy.questions import build_questions
from app.services.glossary import correct_text, glossary_path, load_glossary
from app.services.mentioned_time import resolve_mentioned_time
from app.services.state_text import build_state_text

from eval.augment_noise import DATASET
from eval.common import select_scripts
from eval.metrics import (
    classification_accuracy,
    confusion_matrix,
    extraction_match,
    field_key,
    hallucination_rate,
    macro_f1,
    term_recall_or_none,
    text_error_rates,
)
from eval.stage_cache import ensure_stage, file_sha256, read_stage, text_sha256

FIELD_MAP = (
    ("event_type", "issue_type"),
    ("severity", "severity"),
    ("road_type", "road_type"),
    ("ego_action_before", "prior_maneuver"),
    ("target_type", "target"),
    ("ego_reaction", "reaction"),
)


@dataclass
class CreditRates:
    stt_per_minute: float
    masking_per_text_call: float
    extract_per_call: float
    classify_per_call: float
    assumed_audio_seconds: float


def load_thresholds() -> dict[str, object]:
    return yaml.safe_load((DATASET / "thresholds.yaml").read_text(encoding="utf-8"))


def load_scripts() -> list[dict[str, object]]:
    payload = json.loads((DATASET / "ground_truth.json").read_text(encoding="utf-8"))
    return list(payload["scripts"])


def audio_for(sample_id: str, condition: str, audio_dir: Path) -> Path | None:
    if condition == "original":
        return _first_existing(audio_dir, sample_id, ("m4a", "wav", "mp3"))
    if condition == "car":
        return _first_existing(audio_dir, f"{sample_id}_car", ("m4a", "wav", "mp3"))
    if condition == "tts":
        voice_dir = audio_dir / "tts"
        if not voice_dir.is_dir():
            return None
        matches = sorted(voice_dir.glob(f"*/{sample_id}.wav"))
        return matches[0] if matches else None
    if condition.startswith("noise_") and condition.endswith("dB"):
        level = condition.removeprefix("noise_")
        candidate = audio_dir / "noise" / level / f"{sample_id}.wav"
        return candidate if candidate.is_file() else None
    return None


def estimate_credits(
    *,
    stt_calls: int,
    stt_seconds: float,
    extract_calls: int,
    classify_calls: int,
    rates: CreditRates,
) -> float:
    text_calls = extract_calls + classify_calls
    return (
        (stt_seconds / 60) * rates.stt_per_minute
        + text_calls * rates.masking_per_text_call
        + extract_calls * rates.extract_per_call
        + classify_calls * rates.classify_per_call
    )


def plan_condition(
    scripts: list[dict[str, object]],
    condition: str,
    *,
    audio_dir: Path,
    cache_dir: Path,
    rates: CreditRates,
    stt_model: str,
    extract_model: str,
) -> dict[str, float]:
    stt_calls = 0
    extract_calls = 0
    classify_calls = 0
    stt_seconds = 0.0
    glossary_sha = text_sha256(glossary_path().read_text(encoding="utf-8"))
    for item in scripts:
        sample_id = str(item["id"])
        audio = audio_for(sample_id, condition, audio_dir)
        stt_path = cache_dir / condition / sample_id / "stt.json"
        stt_cached = _cached_fingerprint(stt_path, _stt_fingerprint(audio, stt_model) if audio else None)
        if audio is None:
            continue
        duration = _duration_seconds(audio) or rates.assumed_audio_seconds
        if not stt_cached:
            stt_calls += 1
            stt_seconds += duration
            extract_calls += 1
            classify_calls += 1
            continue
        stt_payload = _payload(stt_path)
        glossary_path_cache = cache_dir / condition / sample_id / "glossary.json"
        corrected = ""
        glossary_hit = False
        if isinstance(stt_payload, dict):
            glossary_fp = text_sha256(str(stt_payload.get("text", ""))) + glossary_sha
            glossary_hit = _cached_fingerprint(glossary_path_cache, glossary_fp)
            if glossary_hit:
                glossary_payload = _payload(glossary_path_cache)
                if isinstance(glossary_payload, dict):
                    corrected = str(glossary_payload.get("text", ""))
        if not glossary_hit:
            extract_calls += 1
            classify_calls += 1
            continue
        extraction_path = cache_dir / condition / sample_id / "extraction.json"
        extraction_fp = text_sha256(corrected) + glossary_sha + extract_model
        if not _cached_fingerprint(extraction_path, extraction_fp):
            extract_calls += 1
            classify_calls += 1
            continue
        extraction_payload = _payload(extraction_path)
        state = corrected
        if isinstance(extraction_payload, dict):
            state = build_state_text(
                corrected,
                _nested_str(extraction_payload, "cause"),
                _nested_str(extraction_payload, "location"),
            )
        classification_fp = text_sha256(state) + _wording_sha()
        classification_path = cache_dir / condition / sample_id / "classification.json"
        if not _cached_fingerprint(classification_path, classification_fp):
            classify_calls += 1
    return {
        "stt_calls": stt_calls,
        "extract_calls": extract_calls,
        "classify_calls": classify_calls,
        "stt_seconds": stt_seconds,
        "credits": estimate_credits(
            stt_calls=stt_calls,
            stt_seconds=stt_seconds,
            extract_calls=extract_calls,
            classify_calls=classify_calls,
            rates=rates,
        ),
    }


def score_sample(script: dict[str, object], record: dict[str, object], terms: list[str]) -> dict[str, object]:
    expected = script["expected"]
    if not isinstance(expected, dict):
        expected = {}
    reference = str(script["script"])
    raw_text = str(record.get("raw_text", ""))
    corrected = str(record.get("corrected_text", ""))
    cer_score, wer_score = text_error_rates(reference, corrected)
    before = term_recall_or_none(reference, raw_text, terms)
    after = term_recall_or_none(reference, corrected, terms)
    taxonomy = load_taxonomy()
    known = {
        "event_type": {item.key for item in taxonomy.event_types},
        "severity": {item.key for item in taxonomy.severity_levels},
        "road_type": {item.key for item in taxonomy.guide["road_type"].options},
        "ego_action_before": {item.key for item in taxonomy.guide["ego_action_before"].options},
        "target_type": {item.key for item in taxonomy.guide["target_type"].options},
        "ego_reaction": {item.key for item in taxonomy.guide["ego_reaction"].options},
    }
    fields: dict[str, object] = {}
    errors: list[dict[str, str]] = []
    for predicted_name, gold_name in FIELD_MAP:
        raw_gold = expected.get(gold_name)
        if isinstance(raw_gold, dict) and raw_gold.get("in_taxonomy") is False:
            fields[predicted_name] = {"skipped": True}
            continue
        gold = field_key(raw_gold)
        if gold is not None and gold not in known[predicted_name]:
            fields[predicted_name] = {"skipped": True}
            continue
        predicted = record.get(predicted_name)
        predicted_key = predicted if isinstance(predicted, str) or predicted is None else None
        fields[predicted_name] = {"gold": gold, "predicted": predicted_key, "correct": gold == predicted_key}
        if gold != predicted_key:
            errors.append(
                {
                    "id": str(script["id"]),
                    "field": predicted_name,
                    "expected": "" if gold is None else gold,
                    "actual": "" if predicted_key is None else predicted_key,
                }
            )
    location_gold = expected.get("location")
    location_gold = None if location_gold is None else str(location_gold)
    cause_gold = expected.get("cause")
    cause_gold = None if cause_gold is None else str(cause_gold)
    time_gold = expected.get("relative_time")
    time_gold = None if time_gold is None else str(time_gold)
    location_ok = extraction_match(location_gold, _optional_str(record.get("location")))
    time_ok = extraction_match(time_gold, _optional_str(record.get("mentioned_time")))
    resolved_ok = _resolved_time_correct(expected, corrected, _optional_str(record.get("mentioned_time")))
    cause_ok = None if "cause" not in expected else extraction_match(cause_gold, _optional_str(record.get("cause")))
    if not location_ok:
        errors.append(_error(script, "location", location_gold, record.get("location")))
    if not time_ok:
        errors.append(_error(script, "mentioned_time", time_gold, record.get("mentioned_time")))
    if cause_ok is False:
        errors.append(_error(script, "cause", cause_gold, record.get("cause")))
    return {
        "id": script["id"],
        "cer": cer_score,
        "wer": wer_score,
        "term_recall_before": before,
        "term_recall_after": after,
        "fields": fields,
        "location_correct": location_ok,
        "mentioned_time_correct": time_ok,
        "mentioned_time_resolved_correct": resolved_ok,
        "cause_correct": cause_ok,
        "hallucination": record.get("hallucination"),
        "errors": errors,
    }


def render_report(condition_rows: dict[str, dict[str, object]], thresholds: dict[str, float]) -> str:
    header = (
        "| 조건 | n | CER | WER | 용어 재현(보정 후) | 사건 유형 macro F1 | "
        "필드 정확도 | 장소 | 상대 시각 | 해석 시각 | 환각 |"
    )
    divider = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines = ["# 음성 평가", "", header, divider]
    for condition, summary in condition_rows.items():
        row = (
            "| {condition} | {n} | {cer} | {wer} | {term} | {f1} | {field} | {loc} | {mention} | {resolved} | {hall} |"
        )
        lines.append(
            row.format(
                condition=condition,
                n=summary.get("n", "n/a"),
                cer=_fmt(summary.get("cer")),
                wer=_fmt(summary.get("wer")),
                term=_fmt(summary.get("term_recall_after")),
                f1=_fmt(summary.get("event_type_macro_f1")),
                field=_fmt(summary.get("field_accuracy")),
                loc=_fmt(summary.get("location_accuracy")),
                mention=_fmt(summary.get("mentioned_time_accuracy")),
                resolved=_fmt(summary.get("mentioned_time_resolved_accuracy")),
                hall=_fmt(summary.get("hallucination")),
            )
        )
        sample_count = summary.get("n")
        if isinstance(sample_count, int) and sample_count < 10:
            lines.append("")
            note = (
                f"{condition}: 표본이 {sample_count}건이라 "
                "사건 유형 macro F1 은 라벨이 비는 칸 때문에 낮게 보일 수 있습니다."
            )
            lines.append(note)
    lines.extend(["", "## 기준 통과", ""])
    for condition, summary in condition_rows.items():
        verdicts = summary.get("pass")
        if not isinstance(verdicts, dict):
            verdicts = passes(summary, thresholds)
        if not verdicts:
            continue
        for name, ok in verdicts.items():
            lines.append(f"- {condition} {name}: {'통과' if ok else '실패'}")
    lines.extend(["", "## 기준값", ""])
    for name, limit in thresholds.items():
        lines.append(f"- {name}: {limit}")
    for condition, summary in condition_rows.items():
        matrix = summary.get("event_type_confusion")
        if not isinstance(matrix, dict) or not matrix:
            continue
        lines.extend(["", f"## 사건 유형 혼동 행렬 ({condition})", ""])
        labels = list(matrix)
        lines.append("| 정답\\\\예측 | " + " | ".join(labels) + " |")
        lines.append("|---|" + "---:|" * len(labels))
        for gold in labels:
            row = matrix.get(gold)
            if not isinstance(row, dict):
                continue
            cells = " | ".join(str(row.get(label, 0)) for label in labels)
            lines.append(f"| {gold} | {cells} |")
    lines.append("")
    return "\n".join(lines)


def summarize_condition(samples: list[dict[str, object]], labels: list[str]) -> dict[str, object]:
    event_golds: list[str | None] = []
    event_preds: list[str | None] = []
    field_hits: list[tuple[str | None, str | None]] = []
    hallucinations: list[float] = []
    for sample in samples:
        fields = sample["fields"]
        if isinstance(fields, dict) and isinstance(fields.get("event_type"), dict) and "gold" in fields["event_type"]:
            event_golds.append(fields["event_type"]["gold"])
            event_preds.append(fields["event_type"]["predicted"])
        if isinstance(fields, dict):
            for name, value in fields.items():
                if isinstance(value, dict) and "gold" in value:
                    field_hits.append((value["gold"], value["predicted"]))
        if isinstance(sample.get("hallucination"), float):
            hallucinations.append(float(sample["hallucination"]))
    return {
        "cer": _mean([float(item["cer"]) for item in samples]),
        "wer": _mean([float(item["wer"]) for item in samples]),
        "term_recall_before": _mean(_present(samples, "term_recall_before")),
        "term_recall_after": _mean(_present(samples, "term_recall_after")),
        "event_type_macro_f1": macro_f1(event_golds, event_preds, labels),
        "event_type_confusion": confusion_matrix(event_golds, event_preds, labels),
        "field_accuracy": classification_accuracy(field_hits),
        "hallucination": _mean(hallucinations),
        "n": len(samples),
        "location_accuracy": _ratio(samples, "location_correct"),
        "mentioned_time_accuracy": _ratio(samples, "mentioned_time_correct"),
        "mentioned_time_resolved_accuracy": _ratio(samples, "mentioned_time_resolved_correct"),
        "cause_accuracy": _ratio(samples, "cause_correct"),
    }


def passes(summary: dict[str, object], thresholds: dict[str, float]) -> dict[str, bool]:
    checks = {
        "cer_max": _at_most(summary.get("cer"), thresholds.get("cer_max")),
        "wer_max": _at_most(summary.get("wer"), thresholds.get("wer_max")),
        "term_recall_after_min": _at_least(summary.get("term_recall_after"), thresholds.get("term_recall_after_min")),
        "event_type_macro_f1_min": _at_least(
            summary.get("event_type_macro_f1"),
            thresholds.get("event_type_macro_f1_min"),
        ),
        "field_accuracy_min": _at_least(summary.get("field_accuracy"), thresholds.get("field_accuracy_min")),
        "hallucination_max": _at_most(summary.get("hallucination"), thresholds.get("hallucination_max")),
    }
    return {name: value for name, value in checks.items() if value is not None}


def run_cached_pipeline(
    audio: Path,
    cache_dir: Path,
    *,
    settings: Settings,
    glossary_sha: str,
    wording_sha: str,
) -> dict[str, object]:
    sample_cache = cache_dir
    model = settings.stt_model
    stt_payload, _ = ensure_stage(
        sample_cache / "stt.json",
        _stt_fingerprint(audio, model),
        lambda: _run_stt(audio, settings),
    )
    raw_text = str(stt_payload.get("text", ""))
    glossary_payload, _ = ensure_stage(
        sample_cache / "glossary.json",
        text_sha256(raw_text) + glossary_sha,
        lambda: {"text": correct_text(raw_text)},
    )
    corrected = str(glossary_payload.get("text", ""))
    extraction_payload, _ = ensure_stage(
        sample_cache / "extraction.json",
        text_sha256(corrected) + glossary_sha + settings.extract_model,
        lambda: _run_extraction(corrected, settings),
    )
    state = build_state_text(
        corrected,
        _nested_str(extraction_payload, "cause"),
        _nested_str(extraction_payload, "location"),
    )
    classification_payload, _ = ensure_stage(
        sample_cache / "classification.json",
        text_sha256(state) + wording_sha,
        lambda: _run_classification(state, settings),
    )
    transcript = corrected
    evidence_fields = [
        (_nested_str(extraction_payload, "cause"), _nested_evidence(extraction_payload, "cause")),
        (_nested_str(extraction_payload, "location"), _nested_evidence(extraction_payload, "location")),
        (_nested_str(extraction_payload, "mentioned_time"), _nested_evidence(extraction_payload, "mentioned_time")),
    ]
    record = {
        "raw_text": raw_text,
        "corrected_text": corrected,
        "cause": _nested_str(extraction_payload, "cause"),
        "location": _nested_str(extraction_payload, "location"),
        "mentioned_time": _nested_str(extraction_payload, "mentioned_time"),
        "mentioned_time_resolved": _resolved_payload(corrected, _nested_str(extraction_payload, "mentioned_time")),
        "hallucination": hallucination_rate(evidence_fields, transcript),
    }
    record.update(classification_payload)
    return record


def main(argv: list[str] | None = None) -> int:
    config = load_thresholds()
    rates = _rates(config["credits"])
    parser = argparse.ArgumentParser(description="조건별 평가. --dry-run 은 호출하지 않습니다.")
    parser.add_argument("--conditions", default=",".join(config["conditions"]))
    parser.add_argument("--audio-dir", type=Path, default=DATASET / "audio")
    parser.add_argument("--cache-dir", type=Path, default=DATASET / "cache")
    parser.add_argument("--report-dir", type=Path, default=DATASET / "reports")
    parser.add_argument("--ids", default=None, help="쉼표로 구분한 대본 id. 예: s01,s36")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    scripts = select_scripts(load_scripts(), args.ids, None)
    settings = Settings()
    conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
    plans = []
    for condition in conditions:
        plan = plan_condition(
            scripts,
            condition,
            audio_dir=args.audio_dir,
            cache_dir=args.cache_dir,
            rates=rates,
            stt_model=settings.stt_model,
            extract_model=settings.extract_model,
        )
        plans.append((condition, plan))
        print(
            f"{condition}\tSTT {int(plan['stt_calls'])}회 {plan['stt_seconds']:.1f}s\t"
            f"추출 {int(plan['extract_calls'])}\t분류 {int(plan['classify_calls'])}\t"
            f"약 {plan['credits']:.2f} cr"
        )
    if args.dry_run:
        return 0
    needs_gateway = (
        settings.stt_provider != "mock"
        or settings.extractor_provider != "mock"
        or settings.classifier_provider != "mock"
    )
    if needs_gateway and not settings.gateway_api_key.strip():
        print("GATEWAY_API_KEY 가 없습니다. mock 으로 돌리거나 키를 넣은 뒤 다시 실행하세요.")
        return 2
    glossary_sha = text_sha256(glossary_path().read_text(encoding="utf-8"))
    wording_sha = _wording_sha()
    terms = load_glossary().terms
    labels = [item.key for item in load_taxonomy().event_types]
    summaries: dict[str, dict[str, object]] = {}
    error_rows: list[dict[str, str]] = []
    for condition, _plan in plans:
        samples: list[dict[str, object]] = []
        for item in scripts:
            audio = audio_for(str(item["id"]), condition, args.audio_dir)
            if audio is None:
                continue
            record = run_cached_pipeline(
                audio,
                args.cache_dir / condition / str(item["id"]),
                settings=settings,
                glossary_sha=glossary_sha,
                wording_sha=wording_sha,
            )
            scored = score_sample(item, record, terms)
            for error in scored["errors"]:
                if isinstance(error, dict):
                    error_rows.append({"condition": condition, **error})
            samples.append(scored)
        summaries[condition] = summarize_condition(samples, labels)
        summaries[condition]["pass"] = passes(summaries[condition], config["metrics"])
    args.report_dir.mkdir(parents=True, exist_ok=True)
    metrics_thresholds = {key: float(value) for key, value in config["metrics"].items()}
    (args.report_dir / "eval_report.md").write_text(render_report(summaries, metrics_thresholds), encoding="utf-8")
    _write_csv(args.report_dir / "eval_report.csv", summaries)
    _write_errors(args.report_dir / "errors.csv", error_rows)
    print(f"보고서를 썼습니다: {args.report_dir}")
    return 0


def _run_stt(audio: Path, settings: Settings) -> dict[str, object]:
    transcript = get_stt_adapter(settings).transcribe(audio, [])
    return {"text": transcript.text, "words": [word.model_dump() for word in transcript.words]}


def _run_extraction(text: str, settings: Settings) -> dict[str, object]:
    extracted = get_extractor(settings).extract(text)
    return extracted.model_dump()


def _run_classification(state: str, settings: Settings) -> dict[str, object]:
    result = get_classifier(settings).classify(state, build_questions())
    values: dict[str, object] = {}
    taxonomy = load_taxonomy()
    for answer in result.answers:
        if getattr(answer, "kind", "") == "choice":
            values[answer.id] = answer.value
        elif answer.id == "severity" and answer.score is not None:
            levels = taxonomy.severity_levels
            if 0 <= answer.score < len(levels):
                values["severity"] = levels[answer.score].key
    return values


def _rates(raw: object) -> CreditRates:
    if not isinstance(raw, dict):
        raise ValueError("credits 설정이 없습니다.")
    return CreditRates(
        stt_per_minute=float(raw["stt_per_minute"]),
        masking_per_text_call=float(raw["masking_per_text_call"]),
        extract_per_call=float(raw["extract_per_call"]),
        classify_per_call=float(raw["classify_per_call"]),
        assumed_audio_seconds=float(raw["assumed_audio_seconds"]),
    )


def _stt_fingerprint(audio: Path | None, model: str) -> str:
    if audio is None:
        return "missing"
    return file_sha256(audio) + model


def _wording_sha() -> str:
    root = DATASET.parents[1] / "app" / "domain"
    parts = [
        (root / "jev_questions.yaml").read_text(encoding="utf-8"),
        (root / "taxonomy" / "v1.yaml").read_text(encoding="utf-8"),
    ]
    return text_sha256("\n".join(parts))


def _cached_fingerprint(path: Path, fingerprint: str | None) -> bool:
    if fingerprint is None:
        return False
    cached = read_stage(path)
    return cached is not None and cached.get("fingerprint") == fingerprint


def _payload(path: Path) -> dict[str, object] | None:
    cached = read_stage(path)
    if cached is None or not isinstance(cached.get("payload"), dict):
        return None
    return cached["payload"]


def _first_existing(root: Path, stem: str, suffixes: tuple[str, ...]) -> Path | None:
    for suffix in suffixes:
        candidate = root / f"{stem}.{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _duration_seconds(path: Path) -> float | None:
    if path.suffix.lower() != ".wav":
        return None
    import wave

    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        if rate <= 0:
            return None
        return handle.getnframes() / rate


def _nested_str(payload: dict[str, object], name: str) -> str | None:
    value = payload.get(name)
    if isinstance(value, dict):
        inner = value.get("value")
        return str(inner) if isinstance(inner, str) else None
    if isinstance(value, str):
        return value
    return None


def _nested_evidence(payload: dict[str, object], name: str) -> str | None:
    value = payload.get(name)
    if isinstance(value, dict):
        evidence = value.get("evidence")
        return str(evidence) if isinstance(evidence, str) else None
    return None


def _optional_str(value: object) -> str | None:
    return str(value) if isinstance(value, str) else None


_EVAL_ANCHOR = datetime(2026, 1, 1)


def _resolved_payload(transcript: str, mention: str | None) -> dict[str, object] | None:
    resolved = resolve_mentioned_time(transcript, mention=mention, words=None, recorded_at=_EVAL_ANCHOR)
    if resolved is None:
        return None
    return {"expression": resolved.expression, "offset_seconds": resolved.offset_seconds}


def _gold_time_expressions(expected: dict[str, object]) -> list[str]:
    found: list[str] = []
    primary = expected.get("relative_time")
    if isinstance(primary, str) and primary.strip():
        found.append(primary)
    secondary = expected.get("secondary_events")
    if isinstance(secondary, list):
        for item in secondary:
            if isinstance(item, dict) and isinstance(item.get("relative_time"), str):
                found.append(str(item["relative_time"]))
    return found


def _resolved_time_correct(expected: dict[str, object], transcript: str, mention: str | None) -> bool | None:
    golds = _gold_time_expressions(expected)
    actual = resolve_mentioned_time(transcript, mention=mention, words=None, recorded_at=_EVAL_ANCHOR)
    if not golds:
        return actual is None
    targets = []
    for expression in golds:
        resolved = resolve_mentioned_time(expression, mention=None, words=None, recorded_at=_EVAL_ANCHOR)
        if resolved is not None:
            targets.append(resolved)
    if actual is None or not targets:
        return False
    target = min(targets, key=lambda item: (0 if _looks_numeric(item.expression) else 1, item.uncertainty_seconds))
    return abs(actual.offset_seconds - target.offset_seconds) < 0.1


def _looks_numeric(expression: str) -> bool:
    markers = "0123456789일이삼사오육칠팔구십"
    return any(char in markers for char in expression)


def _error(script: dict[str, object], field: str, expected: str | None, actual: object) -> dict[str, str]:
    return {
        "id": str(script["id"]),
        "field": field,
        "expected": "" if expected is None else expected,
        "actual": "" if actual is None else str(actual),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _present(samples: list[dict[str, object]], key: str) -> list[float]:
    return [float(item[key]) for item in samples if isinstance(item.get(key), float)]


def _ratio(samples: list[dict[str, object]], key: str) -> float | None:
    values = [item[key] for item in samples if isinstance(item.get(key), bool)]
    if not values:
        return None
    return sum(1 for value in values if value) / len(values)


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return "n/a"


def _at_most(value: object, limit: object) -> bool | None:
    if not isinstance(value, float) or not isinstance(limit, int | float):
        return None
    return value <= float(limit)


def _at_least(value: object, limit: object) -> bool | None:
    if not isinstance(value, float) or not isinstance(limit, int | float):
        return None
    return value >= float(limit)


def _write_csv(path: Path, summaries: dict[str, dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, ["condition", "metric", "value"])
        writer.writeheader()
        for condition, summary in summaries.items():
            for metric, value in summary.items():
                if isinstance(value, float):
                    writer.writerow({"condition": condition, "metric": metric, "value": f"{value:.4f}"})


def _write_errors(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, ["condition", "id", "field", "expected", "actual"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
