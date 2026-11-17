import { useEffect, useRef, useState } from "react";
import { MicOff, Square } from "lucide-react";
import Button from "@/components/Button";
import { formatTime } from "@/lib/formatTime";
import useAudioLevels, { INTERVAL_MS } from "./useAudioLevels";
import Waveform from "./Waveform";

/** 녹음이 끝난 이유: 사용자가 직접 끝냈는지, 무음으로 자동 종료됐는지 */
export type FinishReason = "manual" | "silence";

type Props = {
  onFinish: (blob: Blob, durationSec: number, reason: FinishReason) => void;
  onCancel: () => void;
};

const SILENCE_LEVEL = 0.05; // 이 값 미만이면 무음으로 본다 (0~1, 현장 테스트 후 조정)
const SILENCE_MS = 4000; // 자동 종료까지 필요한 무음 지속 시간
const SILENCE_SAMPLES = Math.ceil(SILENCE_MS / INTERVAL_MS); // 50회

export default function Record({ onFinish, onCancel }: Props) {
  const [seconds, setSeconds] = useState(0);
  const [ready, setReady] = useState(false); // 녹음이 실제로 시작됐는지
  const [error, setError] = useState("");
  const [micStream, setMicStream] = useState<MediaStream | null>(null);
  const levels = useAudioLevels(micStream);

  // useRef: 화면을 다시 그리지 않고 값을 계속 들고 있는 상자
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const silentCountRef = useRef(0); // 연속 무음 측정 횟수
  const heardSpeechRef = useRef(false); // 첫 소리가 들어온 뒤인지 여부

  useEffect(() => {
    let ignore = false; // 화면이 먼저 사라졌는지 표시
    let timer: ReturnType<typeof setInterval> | undefined;
    let stream: MediaStream | undefined;

    async function startRecording() {
      try {
        // 마이크 권한 요청 (사용자가 허용해야 진행됨)
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        if (ignore) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        const recorder = new MediaRecorder(stream);
        recorderRef.current = recorder;
        chunksRef.current = [];

        // 녹음 데이터가 조각으로 들어올 때마다 모아둠
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data);
        };

        recorder.start();
        setMicStream(stream);
        setReady(true);

        // 녹음이 시작된 뒤부터 타이머 동작
        timer = setInterval(() => {
          setSeconds((prev) => prev + 1);
        }, 1000);
      } catch (err) {
        // console.error는 Next 개발 모드에서 오류 오버레이를 띄워서 warn으로 남긴다
        console.warn(err);
        setError("마이크를 사용할 수 없어요. 브라우저의 마이크 권한을 확인해 주세요.");
      }
    }

    void startRecording();

    // 화면이 사라질 때 정리: 타이머, 녹음기, 마이크 모두 끄기
    return () => {
      ignore = true;
      clearInterval(timer);
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function handleFinish(reason: FinishReason) {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;

    // 녹음이 완전히 멈춘 뒤 조각들을 하나의 파일(Blob)로 합침
    const durationSec = seconds;
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
      onFinish(blob, durationSec, reason);
    };
    recorder.stop();
  }

  // 측정값이 갱신될 때마다 무음 지속 여부 확인 (4초 무음이면 자동 종료)
  useEffect(() => {
    if (!ready || error) return;

    const latest = levels[levels.length - 1];

    if (latest >= SILENCE_LEVEL) {
      heardSpeechRef.current = true;
      silentCountRef.current = 0;
      return;
    }

    // 아직 말을 시작하기 전이면 무음을 세지 않는다
    if (!heardSpeechRef.current) return;

    silentCountRef.current += 1;
    if (silentCountRef.current >= SILENCE_SAMPLES) {
      silentCountRef.current = 0;
      handleFinish("silence");
    }
  }, [levels, ready, error]);

  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] flex-col bg-ink px-5 pt-6 pb-8 text-white">
      <header className="flex justify-center">
        {error ? (
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3.5 py-1.5 text-[13px] font-semibold text-white/70">
            <MicOff className="size-4" aria-hidden="true" />
            마이크 꺼짐
          </span>
        ) : (
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3.5 py-1.5 text-[13px] font-semibold">
            <span
              aria-hidden="true"
              className={`size-2 rounded-full ${ready ? "bg-danger animate-blink" : "bg-white/40"}`}
            />
            {ready ? "녹음 중" : "준비 중"}
          </span>
        )}
      </header>

      <section className="flex flex-1 flex-col items-center justify-center gap-3">
        <p className="text-[64px] leading-none font-extrabold tabular-nums tracking-tight">
          {formatTime(seconds)}
        </p>

        {error ? (
          <p role="alert" className="mt-2 max-w-[300px] text-center text-[15px] font-semibold text-[#ff8a80]">
            {error}
          </p>
        ) : (
          <p className="text-[16px] font-semibold text-kakao" aria-live="polite">
            {ready ? "듣는 중이에요. 4초 동안 조용하면 자동으로 끝나요" : "마이크 준비 중..."}
          </p>
        )}

        {/* 파형 표시 (마이크를 못 쓰면 숨김) */}
        {!error && (
          <div className="mt-10 w-full">
            <Waveform levels={levels} />
          </div>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <Button onClick={() => handleFinish("manual")} disabled={!ready} className="w-full disabled:bg-white/15 disabled:text-white/40">
          <Square className="size-4 fill-current" aria-hidden="true" />
          녹음 끝내기
        </Button>
        <Button variant="ghostDark" onClick={onCancel} className="w-full text-[16px] font-semibold">
          {error ? "돌아가기" : "취소"}
        </Button>
      </section>
    </main>
  );
}
