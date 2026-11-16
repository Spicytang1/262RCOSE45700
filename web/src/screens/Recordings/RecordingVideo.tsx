import { useEffect, useState } from "react";
import { Pause, Play, Video } from "lucide-react";
import { formatTime } from "@/lib/formatTime";
import { focusStyle } from "@/lib/recordingPresentation";
import { RecordingPanel } from "./RecordingChrome";

/**
 * 녹음 중 차량 영상 항목 (시연용 모양만 구현).
 * 차량 연동 전까지 실제 영상은 없고, 재생 버튼은 시간만 흘려 보이는 가짜 동작이다.
 * TODO(backend): 녹음 시각과 맞춘 차량 영상 URL을 서버에서 받아 <video>로 교체한다.
 */
export default function RecordingVideo({ durationSec }: { durationSec: number }) {
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);

  // 재생 중이면 1초마다 위치를 올린다
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setPosition((prev) => Math.min(prev + 1, durationSec));
    }, 1000);
    return () => clearInterval(timer);
  }, [playing, durationSec]);

  // 끝까지 가면 자동으로 멈춘다
  useEffect(() => {
    if (playing && position >= durationSec) setPlaying(false);
  }, [playing, position, durationSec]);

  const progress = durationSec > 0 ? (position / durationSec) * 100 : 0;

  return (
    <RecordingPanel title="녹음 중 차량 영상">
      <span className="mb-3 inline-block rounded-full bg-kakao-soft px-3 py-1 text-[12px] font-bold">시연용 예시</span>
      <div className="relative flex aspect-video w-full flex-col items-center justify-center gap-2 overflow-hidden rounded-button bg-ink text-white/70">
        <Video className="size-8" aria-hidden="true" />
        <p className="text-[13px]">차량 영상이 연결되지 않은 화면이에요</p>
        <p className="absolute right-3 top-2 text-[12px] font-semibold tabular-nums">{formatTime(position)} / {formatTime(durationSec)}</p>
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full bg-kakao transition-[width] duration-1000 ease-linear" style={{ width: `${progress}%` }} />
      </div>
      <button
        type="button"
        onClick={() => {
          if (position >= durationSec) setPosition(0);
          setPlaying((prev) => !prev);
        }}
        aria-pressed={playing}
        className={`mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-button bg-ink px-4 text-[14px] font-bold text-white ${focusStyle}`}
      >
        {playing ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
        {playing ? "일시정지" : "영상 재생 (시연)"}
      </button>
      <p className="mt-2 text-[12px] text-ink-sub">실제 영상이 아니에요. 차량과 연결되면 녹음 시각에 맞춘 영상이 여기에 표시돼요.</p>
    </RecordingPanel>
  );
}
