import { useEffect, useRef, useState } from "react";
import { Delete, ShieldCheck } from "lucide-react";
import type { Supervisor } from "@/types/report";
import { findSupervisorByPin, getSupervisorDirectory } from "@/lib/supervisorDirectory";

const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

export default function Login({ onLogin }: { onLogin: (supervisor: Supervisor, signal: AbortSignal) => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => () => request.current?.abort(), []);

  async function enterDigit(digit: string) {
    if (pin.length >= 4 || busy) return;
    setError("");
    const next = pin + digit;
    setPin(next);
    if (next.length === 4) {
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      try {
        const found = await findSupervisorByPin(next);
        if (controller.signal.aborted) return;
        if (found) { await onLogin(found, controller.signal); return; }
        setPin(""); setError("없는 번호예요. 다시 입력해 주세요.");
      } catch {
        if (!controller.signal.aborted) { setPin(""); setError("로그인을 완료하지 못했어요. 다시 입력해 주세요."); }
      } finally { if (!controller.signal.aborted) setBusy(false); }
    }
  }

  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] touch-manipulation flex-col bg-white px-6 pt-6 pb-[max(24px,env(safe-area-inset-bottom))] leading-[1.7]">
      <header className="flex min-h-9 items-center gap-3">
        <span className="text-[17px] font-extrabold">주행 이슈 리포트</span>
        <ShieldCheck className="ml-auto size-5 text-ink-sub" aria-hidden="true" />
      </header>

      <section className="flex flex-1 flex-col justify-center py-9">
        <div className="mb-8">
          <h1 ref={heading} tabIndex={-1} className="rounded text-[28px] leading-[1.4] font-extrabold tracking-tight focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">
            번호 4자리를<br />입력해 주세요
          </h1>
          <p className="mt-3 text-[15px] text-ink-sub">
            배정받은 개인 번호를 숫자 버튼으로 입력하면 자동으로 로그인돼요.
          </p>
        </div>

        <div className="mb-2 flex justify-center gap-5 rounded-card bg-surface py-6" role="status" aria-label={`번호 4자리 중 ${pin.length}자리 입력됨`}>
          {[0, 1, 2, 3].map((index) => <span key={index} aria-hidden="true" className={`size-4 rounded-full ${index < pin.length ? "bg-ink" : "border-2 border-ink-sub/40"}`} />)}
        </div>
        <p role={error ? "alert" : "status"} className={`mb-3 min-h-12 text-center text-[13px] leading-[1.7] ${error ? "text-[#b42318]" : "text-ink-sub"}`}>{error || (busy ? "로그인 정보를 확인하고 있어요…" : "")}</p>
        <div className="grid grid-cols-3 gap-3" aria-label="숫자 키패드">
          {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "delete"].map((digit, index) => (
            digit === "" ? <span key={`blank-${index}`} /> : (
              <button key={digit} type="button" aria-label={digit === "delete" ? "한 자리 지우기" : digit} disabled={busy || (digit === "delete" && !pin.length)} onClick={() => { if (digit === "delete") { setPin((value) => value.slice(0, -1)); setError(""); } else void enterDigit(digit); }} className={`flex h-16 items-center justify-center rounded-button text-[27px] font-bold tabular-nums transition-colors active:bg-kakao disabled:opacity-30 ${digit === "delete" ? "bg-transparent" : "bg-surface hover:bg-line"} ${focusStyle}`}>
                {digit === "delete" ? <Delete className="size-6" aria-hidden="true" /> : digit}
              </button>
            )
          ))}
        </div>
      </section>

      <footer className="border-t border-line pt-4 text-[12px] leading-[1.8] text-ink-sub">
        {getSupervisorDirectory().mode === "demo" && <p>시연용 로그인이에요. 감독관마다 번호가 달라요.</p>}
        <p>녹음은 이 기기의 같은 브라우저에만 보관돼요.</p>
      </footer>
    </main>
  );
}
