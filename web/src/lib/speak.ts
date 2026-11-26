// 브라우저 내장 음성 합성(speechSynthesis)으로 짧은 안내를 읽어 준다. 키·서버가 필요 없다.
// 운전 중에는 화면을 보기 어려워서, 중요한 안내는 글자와 함께 소리로도 알려 준다.

function synth(): SpeechSynthesis | null {
  return typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;
}

function koreanVoice(engine: SpeechSynthesis) {
  return engine.getVoices().find(voice => voice.lang.toLowerCase().startsWith("ko")) ?? null;
}

/**
 * iOS 사파리는 사용자가 누른 순간에 한 번 말하게 해야 이후 자동 안내가 소리 난다.
 * 녹음 버튼을 누를 때 소리 없는 안내를 한 번 보내 둔다.
 */
export function primeSpeech() {
  const engine = synth();
  if (!engine) return;
  try {
    const utterance = new SpeechSynthesisUtterance(" ");
    utterance.volume = 0;
    engine.speak(utterance);
  } catch {
    // 음성 합성을 못 쓰면 글자 안내만 보여 준다.
  }
}

/** 안내를 읽고, 다 읽거나 실패하면 끝난다. 브라우저가 끝 신호를 안 주는 경우를 대비해 시간 제한을 둔다. */
export function speak(text: string, timeoutMs = 6000): Promise<void> {
  const engine = synth();
  if (!engine) return Promise.resolve();
  return new Promise(resolve => {
    let done = false;
    const finish = () => { if (!done) { done = true; clearTimeout(timer); resolve(); } };
    const timer = setTimeout(finish, timeoutMs);
    try {
      engine.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ko-KR";
      const voice = koreanVoice(engine);
      if (voice) utterance.voice = voice;
      utterance.rate = 1.05;
      utterance.onend = finish;
      utterance.onerror = finish;
      engine.speak(utterance);
    } catch {
      finish();
    }
  });
}

export function stopSpeaking() {
  try { synth()?.cancel(); } catch { /* 무시 */ }
}
