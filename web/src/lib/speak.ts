// 브라우저 내장 음성 합성(speechSynthesis)으로 짧은 안내를 읽어 준다. 키·서버가 필요 없다.
// 운전 중에는 화면을 보기 어려워서, 중요한 안내는 알림음(또는 안내 음성 파일) + 음성으로 알려 준다.
//
// 크롬에서 알려진 문제를 피하려고 다음을 지킨다.
// - cancel() 직후 바로 speak() 하면 새 안내가 소리 없이 버려질 수 있어 잠깐 기다린다.
// - 엔진이 멈춘(paused) 상태로 남는 경우가 있어 말하기 전에 resume() 한다.
// - 안내 객체가 메모리에서 정리되면 끝 신호가 안 오므로 끝날 때까지 참조를 들고 있는다.
// - 목소리 목록은 늦게 채워져서 잠깐 기다린 뒤 한국어 목소리를 고른다.

let current: SpeechSynthesisUtterance | null = null;
let audio: AudioContext | null = null;

function synth(): SpeechSynthesis | null {
  return typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;
}

const wait = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));

async function koreanVoice(engine: SpeechSynthesis) {
  let voices = engine.getVoices();
  if (!voices.length) {
    await Promise.race([
      new Promise<void>(resolve => engine.addEventListener("voiceschanged", () => resolve(), { once: true })),
      wait(800),
    ]);
    voices = engine.getVoices();
  }
  return voices.find(voice => voice.lang.toLowerCase().replace("_", "-").startsWith("ko")) ?? null;
}

export type Cue = "prompt" | "ended";

/**
 * 음성 파일이 있으면 그 파일을 튼다. (web/public/sounds/prompt.mp3, ended.mp3)
 * 팀원 목소리나 TTS로 미리 만든 안내 음성을 넣어 두면 브라우저 음성 합성이 안 되는 기기에서도 말로 들린다.
 */
async function playFile(cue: Cue): Promise<boolean> {
  try {
    const element = new Audio(`/sounds/${cue}.mp3`);
    await element.play();
    await new Promise<void>(resolve => { element.onended = () => resolve(); element.onerror = () => resolve(); setTimeout(resolve, 6000); });
    return true;
  } catch {
    return false;
  }
}

/**
 * 파일이 없을 때 쓰는 알림음. 두 상황을 소리만 듣고 구분할 수 있게 모양을 다르게 했다.
 * - prompt(말해 주세요): 올라가는 "띠-띠-띠↑"를 두 번 → 주의를 끄는 소리
 * - ended(녹음 끝남): 내려가는 "띠리링↓" 한 번 → 끝났다는 소리
 */
async function playTones(cue: Cue) {
  const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Context) return;
  audio ??= new Context();
  if (audio.state === "suspended") await audio.resume();
  const ctx = audio;
  const pattern: [number, number][] = cue === "prompt"
    ? [[660, 0], [880, 0.16], [1175, 0.32], [660, 0.75], [880, 0.91], [1175, 1.07]]
    : [[1175, 0], [880, 0.18], [587, 0.36]];
  const length = cue === "prompt" ? 0.13 : 0.22;
  const start = ctx.currentTime + 0.02;
  for (const [frequency, offset] of pattern) {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "triangle";
    oscillator.frequency.value = frequency;
    const at = start + offset;
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.6, at + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + length);
    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(at);
    oscillator.stop(at + length + 0.02);
  }
  await wait((pattern[pattern.length - 1][1] + length) * 1000 + 150);
}

/** 상황 알림: 안내 음성 파일 → 없으면 알림음. 휴대폰은 진동도 함께 준다(안드로이드). */
export async function playCue(cue: Cue) {
  try { navigator.vibrate?.(cue === "prompt" ? [200, 100, 200] : [400]); } catch { /* 무시 */ }
  if (await playFile(cue)) return true;
  try { await playTones(cue); } catch { /* 알림음을 못 내도 안내 글자는 화면에 있다. */ }
  return false;
}

/**
 * 사용자가 버튼을 누른 순간에 호출한다. 아이폰 사파리는 이렇게 한 번 열어 둬야
 * 나중에 자동으로 나오는 알림음·음성이 소리 난다.
 */
export function primeSpeech() {
  try {
    const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (Context) { audio ??= new Context(); void audio.resume(); }
  } catch { /* 무시 */ }
  const engine = synth();
  if (!engine) return;
  try {
    engine.getVoices();
    if (!engine.speaking && !engine.pending) {
      const unlock = new SpeechSynthesisUtterance("");
      unlock.volume = 0;
      engine.speak(unlock);
    }
  } catch { /* 무시 */ }
}

/**
 * 알림(음성 파일 또는 알림음) 뒤에 브라우저 음성 합성으로 안내를 읽는다.
 * 음성 파일이 있으면 그 파일이 곧 안내라서 합성은 하지 않는다.
 * 합성이 1.2초 안에 시작되지 않으면(소리 없이 실패하는 기기) 기다리지 않고 끝낸다. 녹음이 오래 멈춰 있지 않게 하기 위함.
 */
export async function speak(text: string, cue: Cue = "prompt", timeoutMs = 7000): Promise<void> {
  if (await playCue(cue)) return;
  const engine = synth();
  if (!engine) return;
  if (engine.speaking || engine.pending) { engine.cancel(); await wait(150); }
  engine.resume();
  const voice = await koreanVoice(engine);
  await new Promise<void>(resolve => {
    let done = false;
    let started = false;
    const finish = () => { if (!done) { done = true; clearTimeout(timer); clearTimeout(startTimer); if (current === utterance) current = null; resolve(); } };
    const timer = setTimeout(finish, timeoutMs);
    const startTimer = setTimeout(() => { if (!started) { console.warn("[음성 안내] 음성 합성이 시작되지 않아 알림음만 냈어요."); engine.cancel(); finish(); } }, 1200);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ko-KR";
    if (voice) utterance.voice = voice;
    utterance.rate = 1.05;
    utterance.volume = 1;
    utterance.onstart = () => { started = true; };
    utterance.onend = finish;
    utterance.onerror = event => { console.warn(`[음성 안내] 읽지 못했어요: ${event.error}`); finish(); };
    current = utterance;
    try { engine.speak(utterance); } catch { finish(); }
  });
}

export function stopSpeaking() {
  try { synth()?.cancel(); } catch { /* 무시 */ }
  current = null;
}
