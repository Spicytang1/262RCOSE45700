import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { focusStyle } from "@/lib/recordingPresentation";
import { formatTime } from "@/lib/formatTime";

/** 원본 음성은 서버에서 인증을 붙여 받아야 해서 load 함수로 받는다. 화면을 열면 미리 받아 둔다. */
export default function RecordingPlayer({ load, durationSec, tone = "light", compact = false }: { load: (signal: AbortSignal) => Promise<Blob>; durationSec: number; tone?: "light" | "dark"; compact?: boolean }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const loadRef = useRef(load);

  useEffect(() => {
    const element = audioRef.current;
    if (!element) return;
    const controller = new AbortController();
    let url = "";
    loadRef.current(controller.signal).then(blob => {
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob);
      element.src = url;
      setReady(true);
    }, () => { if (!controller.signal.aborted) setError("원본 음성을 불러오지 못했어요. 목록으로 돌아가 다시 열어 주세요."); });
    return () => { controller.abort(); element.pause(); element.removeAttribute("src"); element.load(); if (url) URL.revokeObjectURL(url); };
  }, []);

  async function toggle() {
    const element = audioRef.current;
    if (!element || !ready) return;
    setError("");
    if (!element.paused) { element.pause(); return; }
    try { await element.play(); }
    catch { setError("재생하지 못했어요. 재생 버튼을 다시 눌러 주세요."); }
  }

  return <div>
    <audio ref={audioRef} preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => { setPlaying(false); setCurrent(0); if (audioRef.current) audioRef.current.currentTime = 0; }} onTimeUpdate={() => setCurrent(audioRef.current?.currentTime ?? 0)} onError={() => setError("녹음을 읽지 못했어요. 목록으로 돌아가 다시 열어 주세요.")} />
    <div className="flex items-center gap-3">
      <button type="button" onClick={() => void toggle()} aria-label={playing ? "원본 음성 일시정지" : "원본 음성 재생"} disabled={!ready} aria-busy={!ready && !error} className={`order-1 flex size-12 shrink-0 items-center justify-center rounded-full bg-kakao hover:bg-kakao-press disabled:opacity-40 ${focusStyle}`}>{playing ? <Pause className="size-5" aria-hidden="true" /> : <Play className="size-5" aria-hidden="true" />}</button>
      <div className={compact ? "contents" : "min-w-0 flex-1"}>
        <label htmlFor="audio-position" className={compact ? "order-3 shrink-0 text-[13px] font-semibold tabular-nums text-ink-sub" : `flex justify-between text-[12px] font-semibold ${tone === "dark" ? "text-white/60" : "text-ink-sub"}`}><span className={compact ? "sr-only" : undefined}>재생 위치</span><span className="tabular-nums">{formatTime(Math.min(current, durationSec))} / {formatTime(durationSec)}</span></label>
        <input id="audio-position" type="range" min="0" max={Math.max(durationSec, 0.1)} step="0.1" value={Math.min(current, durationSec)} aria-valuetext={`${Math.floor(current)}초, 전체 ${durationSec}초`} onChange={event => {
          const value = Number(event.target.value);
          if (audioRef.current) {
            try { audioRef.current.currentTime = value; setCurrent(value); }
            catch { setError("아직 이동할 수 없어요. 재생 후 다시 시도해 주세요."); }
          }
        }} className={`min-h-11 ${compact ? "order-2 min-w-0 flex-1" : "w-full"} ${tone === "dark" ? "accent-kakao" : "accent-ink"} ${focusStyle}`} />
      </div>
    </div>
    {error && <p role="alert" className="mt-3 text-[13px] text-danger-ink">{error}</p>}
  </div>;
}
