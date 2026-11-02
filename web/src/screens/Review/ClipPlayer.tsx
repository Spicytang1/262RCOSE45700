import { useEffect, useRef, useState } from "react";
import { Play, Square } from "lucide-react";
import { formatTime } from "@/lib/formatTime";

type Props = {
  url: string;
  label: string;
  durationSec: number;
};

export default function ClipPlayer({ url, label, durationSec }: Props) {
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const audio = new Audio(url);
    audio.onended = () => {
      setPlaying(false);
      setCurrent(0);
    };
    audio.ontimeupdate = () => setCurrent(audio.currentTime);
    audioRef.current = audio;

    return () => {
      audio.pause();
      audioRef.current = null;
    };
  }, [url]);

  function handlePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      audio.currentTime = 0;
      setCurrent(0);
      setPlaying(false);
    } else {
      void audio.play();
      setPlaying(true);
    }
  }

  const progress = durationSec > 0 ? Math.min(current / durationSec, 1) : 0;

  return (
    <div className="flex items-center gap-3 py-2.5">
      <button
        type="button"
        onClick={handlePlay}
        aria-label={playing ? `${label} 정지` : `${label} 재생`}
        className="flex size-11 shrink-0 items-center justify-center rounded-full bg-kakao text-ink transition-transform active:scale-95 active:bg-kakao-press"
      >
        {playing ? (
          <Square className="size-4 fill-current" aria-hidden="true" />
        ) : (
          <Play className="ml-0.5 size-5 fill-current" aria-hidden="true" />
        )}
      </button>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-baseline justify-between">
          <span className="truncate text-[15px] font-bold">{label}</span>
          <span className="text-[13px] font-medium text-ink-muted tabular-nums">
            {playing ? `${formatTime(current)} / ` : ""}
            {formatTime(durationSec)}
          </span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
          <div
            className="h-full rounded-full bg-ink transition-[width] duration-200"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
