from __future__ import annotations

import json
import wave
from pathlib import Path

import httpx
import numpy as np
from app.adapters.gateway.client import GatewayClient
from app.services.glossary import Glossary, apply_fuzzy, correct_text, jamo_similarity
from eval.augment_noise import measured_snr_db, mix_at_snr, synthetic_cabin_noise
from eval.common import load_items, select_scripts
from eval.compare_stt import evaluate_split
from eval.metrics import macro_f1
from eval.run_eval import CreditRates, audio_for, estimate_credits, load_scripts, plan_condition, render_report
from eval.stage_cache import ensure_stage
from eval.synthesize_speech import synthesize_scripts

RATES = CreditRates(
    stt_per_minute=6,
    masking_per_text_call=5,
    extract_per_call=8,
    classify_per_call=0.1,
    assumed_audio_seconds=12,
)


def test_cut_in_mishearings_need_driving_context() -> None:
    driving = correct_text("왼쪽에서 검은 차가 코딩해서 끼어들었어요.")
    assert "컷인해서" in driving
    assert "코딩해서" not in driving
    plain = correct_text("파이썬으로 코딩해서 앱을 만들었어요.")
    assert "코딩해서" in plain
    assert "컷인" not in plain
    heard = correct_text("승용차가 코린에서 앞으로 들어왔다.")
    assert "컷인해서" in heard


def test_glossary_exact_and_conservative_fuzzy() -> None:
    assert "컷인" in correct_text("검은 차가 컷 인해서 급제동했다.")
    assert "라바콘" in correct_text("라바 콘이 쓰러져 있었다.")
    assert jamo_similarity("라바콘", "라바콘") == 1
    fuzzy = Glossary(terms=["라바콘"], replacements=[], fuzzy_threshold=0.84)
    assert jamo_similarity("라바콘", "라바콬") >= 0.84
    assert "라바콘" in apply_fuzzy("앞에 라바콬이 있다", fuzzy)
    untouched = Glossary(terms=["컷인"], replacements=[], fuzzy_threshold=1)
    assert apply_fuzzy("갑자기 급제동", untouched) == "갑자기 급제동"


def test_noise_mix_hits_target_snr() -> None:
    sample_rate = 16000
    time_axis = np.arange(sample_rate) / sample_rate
    signal = (0.1 * np.sin(2 * np.pi * 220 * time_axis)).astype(np.float32)
    noise = synthetic_cabin_noise(sample_rate, sample_rate, seed=3)
    mixed = mix_at_snr(signal, noise, 20)
    assert abs(measured_snr_db(signal, mixed) - 20) < 1.5


def test_tts_caches_pcm_as_wav_and_skips(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert json.loads(request.content)["model"] == "gemini-3.8-flash-tts"
        return httpx.Response(200, content=b"\x01\x00" * 50, headers={"content-type": "audio/pcm"})

    client = GatewayClient(
        "https://example.test/v1/gateway",
        "k",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    scripts = [{"id": "s01", "script": "방금 교차로에서 컷인"}]
    created, skipped = synthesize_scripts(
        client,
        scripts,
        tmp_path,
        model="gemini-3.8-flash-tts",
        voices=["Kore"],
        sample_rate=24000,
        channels=1,
        sample_width=2,
    )
    assert (created, skipped, calls["n"]) == (1, 0, 1)
    with wave.open(str(tmp_path / "Kore" / "s01.wav"), "rb") as handle:
        assert handle.getframerate() == 24000
        assert handle.getnchannels() == 1
    created, skipped = synthesize_scripts(
        client,
        scripts,
        tmp_path,
        model="gemini-3.8-flash-tts",
        voices=["Kore"],
        sample_rate=24000,
        channels=1,
        sample_width=2,
    )
    assert (created, skipped, calls["n"]) == (0, 1, 1)


def test_stage_cache_skips_second_compute(tmp_path: Path) -> None:
    calls = {"n": 0}

    def compute() -> dict[str, object]:
        calls["n"] += 1
        return {"text": "컷인"}

    path = tmp_path / "stt.json"
    first, ran = ensure_stage(path, "abc", compute)
    second, ran_again = ensure_stage(path, "abc", compute)
    third, reran = ensure_stage(path, "changed", compute)
    assert first == second == {"text": "컷인"}
    assert (ran, ran_again, reran) == (True, False, True)
    assert calls["n"] == 2
    assert third == {"text": "컷인"}


def test_dry_run_counts_uncached_audio_only(tmp_path: Path) -> None:
    audio = tmp_path / "audio"
    audio.mkdir()
    _write_silence(audio / "s01.wav", seconds=1.0)
    scripts = [{"id": "s01", "script": "방금"}, {"id": "s02", "script": "아까"}]
    plan = plan_condition(
        scripts,
        "original",
        audio_dir=audio,
        cache_dir=tmp_path / "cache",
        rates=RATES,
        stt_model="stt-async-v5",
        extract_model="claude-opus-5-5",
    )
    assert plan["stt_calls"] == 1
    assert plan["extract_calls"] == 1
    assert plan["classify_calls"] == 1
    assert plan["credits"] == estimate_credits(
        stt_calls=1,
        stt_seconds=1,
        extract_calls=1,
        classify_calls=1,
        rates=RATES,
    )
    assert audio_for("s02", "original", audio) is None


def test_credit_formula() -> None:
    total = estimate_credits(stt_calls=1, stt_seconds=60, extract_calls=1, classify_calls=1, rates=RATES)
    assert total == 6 + 10 + 8 + 0.1


def test_macro_f1_and_report() -> None:
    score = macro_f1(["cut_in", "other"], ["cut_in", "cut_in"], ["cut_in", "other"])
    assert 0 < score < 1
    report = render_report({"original": {"cer": 0.1, "wer": 0.2, "term_recall_after": 0.9}}, {"cer_max": 0.35})
    assert "original" in report
    assert "0.100" in report


def test_ids_filter_limits_scripts_and_dry_run() -> None:
    scripts = [{"id": "s01", "script": "가"}, {"id": "s02", "script": "나"}, {"id": "s36", "script": "다"}]
    assert [item["id"] for item in select_scripts(scripts, "s36,s01", None)] == ["s01", "s36"]
    assert [item["id"] for item in select_scripts(scripts, None, 1)] == ["s01"]


def test_report_shows_pass_fail_and_small_sample_note() -> None:
    matrix = {"cut_in": {"cut_in": 1, "None": 0}, "None": {"cut_in": 0, "None": 0}}
    summary = {
        "n": 1,
        "cer": 0.1,
        "wer": 0.2,
        "term_recall_after": 0.9,
        "event_type_macro_f1": 1.0,
        "field_accuracy": 1.0,
        "location_accuracy": 1.0,
        "mentioned_time_accuracy": 1.0,
        "mentioned_time_resolved_accuracy": 1.0,
        "hallucination": 0.0,
        "event_type_confusion": matrix,
        "pass": {"cer_max": True, "event_type_macro_f1_min": False},
    }
    report = render_report({"original": summary}, {"cer_max": 0.35, "event_type_macro_f1_min": 0.6})
    assert "통과" in report
    assert "실패" in report
    assert "장소" in report
    assert "해석 시각" in report
    assert "혼동 행렬" in report
    assert "1건" in report


def test_resolved_time_scores_against_gold() -> None:
    from eval.run_eval import score_sample

    script = {
        "id": "s02",
        "script": "방금 30초 전에 합류 구간에서 끼어들었어요.",
        "expected": {"relative_time": "30초 전", "location": "합류 구간", "issue_type": {"key": "cut_in"}},
    }
    record = {
        "raw_text": script["script"],
        "corrected_text": script["script"],
        "location": "합류 구간",
        "mentioned_time": "30초 전",
        "event_type": "cut_in",
    }
    scored = score_sample(script, record, ["컷인"])
    assert scored["mentioned_time_resolved_correct"] is True


def test_dataset_has_forty_scripts_and_compare_uses_text_split() -> None:
    scripts = load_scripts()
    assert [item["id"] for item in scripts] == [f"s{index:02d}" for index in range(1, 41)]
    summary = evaluate_split(load_items("tune"))
    assert summary["samples"] != "0"
    source = Path("eval/compare_stt.py").read_text(encoding="utf-8")
    assert "RIFF" not in source
    assert "/tmp/" not in source


def _write_silence(path: Path, seconds: float) -> None:
    frames = b"\x00\x00" * int(16000 * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(frames)
