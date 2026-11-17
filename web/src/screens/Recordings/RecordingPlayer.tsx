import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { focusStyle } from "@/lib/recordingPresentation";
import { formatTime } from "@/lib/formatTime";

export default function RecordingPlayer({ audio, durationSec }: { audio: Blob; durationSec: number }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    const element = audioRef.current;
    if (!element) return;
    const url = URL.createObjectURL(audio);
    element.src = url;
    return () => { element.pause(); element.removeAttribute("src"); element.load(); URL.revokeObjectURL(url); };
  }, [audio]);

  async function toggle() {
    const element = audioRef.current;
    if (!element) return;
    setError("");
    if (!element.paused) { element.pause(); return; }
    try { await element.play(); }
    catch { setError("재생하지 못했어요. 재생 버튼을 다시 눌러 주세요."); }
  }

  return <div>
    <audio ref={audioRef} preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => { setPlaying(false); setCurrent(0); if (audioRef.current) audioRef.current.currentTime = 0; }} onTimeUpdate={() => setCurrent(audioRef.current?.currentTime ?? 0)} onError={() => setError("녹음을 읽지 못했어요. 목록으로 돌아가 다시 열어 주세요.")} />
    <div className="flex items-center gap-3">
      <button type="button" onClick={() => void toggle()} aria-label={playing ? "원본 음성 일시정지" : "원본 음성 재생"} className={`flex size-12 shrink-0 items-center justify-center rounded-full bg-kakao hover:bg-kakao-press ${focusStyle}`}>{playing ? <Pause className="size-5" aria-hidden="true" /> : <Play className="size-5" aria-hidden="true" />}</button>
      <div className="min-w-0 flex-1">
        <label htmlFor="audio-position" className="flex justify-between text-[12px] font-semibold text-ink-sub"><span>재생 위치</span><span className="tabular-nums">{formatTime(Math.min(current, durationSec))} / {formatTime(durationSec)}</span></label>
        <input id="audio-position" type="range" min="0" max={Math.max(durationSec, 0.1)} step="0.1" value={Math.min(current, durationSec)} aria-valuetext={`${Math.floor(current)}초, 전체 ${durationSec}초`} onChange={event => {
          const value = Number(event.target.value);
          if (audioRef.current) {
            try { audioRef.current.currentTime = value; setCurrent(value); }
            catch { setError("아직 이동할 수 없어요. 재생 후 다시 시도해 주세요."); }
          }
        }} className={`min-h-11 w-full accent-ink ${focusStyle}`} />
      </div>
    </div>
    {error && <p role="alert" className="mt-3 text-[13px] text-danger-ink">{error}</p>}
  </div>;
}
