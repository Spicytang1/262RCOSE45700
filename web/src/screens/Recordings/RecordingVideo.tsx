import { useEffect, useState } from "react";
import { Pause, Play, Video } from "lucide-react";
import { formatTime } from "@/lib/formatTime";
import { focusStyle } from "@/lib/recordingPresentation";
import { RecordingFold } from "./RecordingChrome";

/**
 * 녹음 중 차량 영상 항목 (시연용 모양만 구현).
 * 차량 연동 전까지 실제 영상은 없고, 재생 버튼은 시간만 흘려 보이는 가짜 동작이다.
 * TODO(backend): 녹음 시각과 맞춘 차량 영상 URL을 서버에서 받아 <video>로 교체한다.
 */
export default function RecordingVideo({ durationSec }: { durationSec: number }) {
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);

  const active = playing && position < durationSec;

  // 재생 중이면 1초마다 위치를 올린다
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      setPosition((prev) => Math.min(prev + 1, durationSec));
    }, 1000);
    return () => clearInterval(timer);
  }, [active, durationSec]);

  const progress = durationSec > 0 ? (position / durationSec) * 100 : 0;

  return (
    <RecordingFold title="녹음 당시 차량 영상" badge="시연용 예시">
      <div className="relative flex aspect-video w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-button bg-ink text-white/70">
        <Video className="size-8" aria-hidden="true" />
        <p className="text-[13px]">차량 영상이 아직 연결되지 않았어요</p>
        <p className="absolute right-3 top-2 text-[12px] font-semibold tabular-nums">{formatTime(position)} / {formatTime(durationSec)}</p>
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full w-full origin-left bg-kakao transition-transform duration-300 ease-out motion-reduce:transition-none" style={{ transform: `scaleX(${progress / 100})` }} />
      </div>
      <button
        type="button"
        onClick={() => {
          if (position >= durationSec) { setPosition(0); setPlaying(true); }
          else setPlaying((prev) => !prev);
        }}
        aria-pressed={active}
        className={`mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-button bg-ink px-4 text-[14px] font-bold text-white ${focusStyle}`}
      >
        {active ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
        {active ? "일시정지" : "영상 재생 (시연)"}
      </button>
    </RecordingFold>
  );
}
