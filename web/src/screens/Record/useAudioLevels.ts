import { useEffect, useState, type RefObject } from "react";
import type { MicVAD } from "@ricky0123/vad-web";

const BAR_COUNT = 40;
export const INTERVAL_MS = 50;
const EMPTY_LEVELS = Array<number>(BAR_COUNT).fill(0);

const FFT_SIZE = 2048;
const SPEECH_LOW_HZ = 180;
const SPEECH_HIGH_HZ = 3400;
const SPEECH_PROBABILITY = 0.5;

/**
 * ignoreRef 가 true 인 동안(앱이 음성 안내를 읽는 중)은 들리는 소리를 목소리로 보지 않는다.
 * 스피커 안내가 마이크로 들어가 "말을 시작했다"고 잘못 판단하는 것을 막는다.
 */
export default function useAudioLevels(stream: MediaStream | null, ignoreRef?: RefObject<boolean>): { levels: number[]; quietMs: number; startingSilentMs: number; vadFailed: boolean } {
  const [levels, setLevels] = useState<number[]>(EMPTY_LEVELS);
  const [quietMs, setQuietMs] = useState(0);
  const [startingSilentMs, setStartingSilentMs] = useState(0);
  const [vadFailed, setVadFailed] = useState(false);

  useEffect(() => {
    if (!stream) return;

    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const highpass = audioContext.createBiquadFilter();
    highpass.type = "highpass";
    highpass.frequency.value = SPEECH_LOW_HZ;
    const lowpass = audioContext.createBiquadFilter();
    lowpass.type = "lowpass";
    lowpass.frequency.value = SPEECH_HIGH_HZ;
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = FFT_SIZE;
    source.connect(highpass);
    highpass.connect(lowpass);
    lowpass.connect(analyser);

    const data = new Float32Array(analyser.fftSize);
    const timer = setInterval(() => {
      analyser.getFloatTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) sumSquares += data[i] * data[i];
      const level = Math.min(Math.sqrt(sumSquares / data.length) * 6, 1);
      setLevels((prev) => [...prev.slice(1), level]);
    }, INTERVAL_MS);

    let cancelled = false;
    let vad: MicVAD | null = null;
    let heard = false;
    let quiet = 0;
    let startingSilent = 0;

    void import("@ricky0123/vad-web").then(({ MicVAD: Vad }) => Vad.new({
      model: "v5",
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      startOnLoad: false,
      getStream: async () => stream,
      pauseStream: async () => { },
      resumeStream: async (resumed) => resumed,
      onFrameProcessed: (probabilities) => {
        if (probabilities.isSpeech >= SPEECH_PROBABILITY && !ignoreRef?.current) {
          heard = true;
          quiet = 0;
          startingSilent = 0;
          setStartingSilentMs(0);
        } else if (!heard) {
          startingSilent += 32;
          setStartingSilentMs(startingSilent);
        } else {
          quiet += 32;
        }
        setQuietMs(quiet);
      },
    })).then(async (instance) => {
      if (cancelled) { await instance.destroy(); return; }
      vad = instance;
      await instance.start();
    }).catch(() => { if (!cancelled) setVadFailed(true); });

    return () => {
      cancelled = true;
      clearInterval(timer);
      void vad?.destroy();
      source.disconnect();
      void audioContext.close();
    };
  }, [stream, ignoreRef]);

  return { levels, quietMs, startingSilentMs, vadFailed };
}
