import { useEffect, useRef, useState } from "react";
import { Delete, Mic } from "lucide-react";
import type { Supervisor } from "@/types/report";
import { findSupervisorByPin, getSupervisorDirectory } from "@/lib/supervisorDirectory";

const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

export default function Login({ onLogin }: { onLogin: (supervisor: Supervisor, signal: AbortSignal) => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");

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
        setPin(""); setError("등록되지 않은 번호예요. 다시 입력해 주세요.");
      } catch {
        if (!controller.signal.aborted) { setPin(""); setError("로그인하지 못했어요. 다시 입력해 주세요."); }
      } finally { if (!controller.signal.aborted) setBusy(false); }
    }
  }

  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] touch-manipulation flex-col bg-ink leading-[1.7] text-white">
      <header className="rise flex items-center gap-2.5 px-6 pt-[clamp(14px,3dvh,24px)]">
        <span className="flex size-9 items-center justify-center rounded-xl bg-kakao text-ink"><Mic className="size-[18px]" strokeWidth={2.2} aria-hidden="true" /></span>
        <span className="text-[16px] font-extrabold tracking-tight">주행 이슈 리포트</span>
      </header>

      <section className="flex flex-1 flex-col justify-center px-6 pt-[clamp(8px,3dvh,32px)] pb-[clamp(8px,2.5dvh,24px)]">
        <p className="rise inline-flex w-fit items-center rounded-full bg-white/10 px-3 py-1 text-[12px] font-bold tracking-wide text-kakao" style={{ "--d": "60ms" } as React.CSSProperties}>감독관 로그인</p>
        <h1 className="rise mt-[clamp(8px,1.6dvh,16px)] text-[clamp(26px,4.2dvh,34px)] leading-[1.25] font-extrabold tracking-tight" style={{ "--d": "110ms" } as React.CSSProperties}>
          번호 4자리를<br />입력해 주세요
        </h1>

        <div className={`rise mt-[clamp(12px,3dvh,32px)] flex gap-3 ${error ? "animate-shake motion-reduce:animate-none" : ""}`} style={{ "--d": "210ms" } as React.CSSProperties} role="status" aria-label={`번호 4자리 중 ${pin.length}자리 입력됨`}>
          {[0, 1, 2, 3].map((index) => (
            <span key={index} aria-hidden="true" className={`flex h-[clamp(48px,7.6dvh,64px)] flex-1 items-center justify-center rounded-[20px] bg-white/[0.07] ring-1 transition-[box-shadow,background-color] duration-200 ${index === pin.length ? "ring-kakao/70" : "ring-white/10"} ${index < pin.length ? "bg-white/[0.12]" : ""}`}>
              <span className={`size-[18px] rounded-full bg-kakao transition-[transform,opacity] duration-200 ease-[cubic-bezier(0.32,0.72,0,1)] ${index < pin.length ? "scale-100 opacity-100" : "scale-50 opacity-0"}`} />
            </span>
          ))}
        </div>
        <p role={error ? "alert" : "status"} className={`mt-2 min-h-6 text-[13px] leading-[1.7] ${error ? "text-danger-soft" : "text-white/60"}`}>{error || (busy ? "로그인 정보를 확인하고 있어요…" : "")}</p>
      </section>

      <div className="rise rounded-t-[40px] bg-white/10 p-1.5 pb-0" style={{ "--d": "260ms" } as React.CSSProperties}>
        <div className="rounded-t-[34px] bg-white px-5 pt-[clamp(14px,2.8dvh,24px)] pb-[max(16px,env(safe-area-inset-bottom))] text-ink">
          <div className="grid grid-cols-3 gap-3" aria-label="숫자 키패드">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "delete"].map((digit, index) => (
              digit === "" ? <span key={`blank-${index}`} /> : (
                <button key={digit} type="button" aria-label={digit === "delete" ? "한 자리 지우기" : digit} disabled={busy || (digit === "delete" && !pin.length)} onClick={() => { if (digit === "delete") { setPin((value) => value.slice(0, -1)); setError(""); } else void enterDigit(digit); }} className={`flex h-[clamp(50px,8.2dvh,68px)] items-center justify-center rounded-[22px] text-[28px] font-bold tabular-nums transition-[background-color,scale] duration-150 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.96] active:bg-kakao disabled:opacity-30 ${digit === "delete" ? "bg-transparent text-ink-sub" : "bg-surface hover:bg-line"} ${focusStyle}`}>
                  {digit === "delete" ? <Delete className="size-6" strokeWidth={1.75} aria-hidden="true" /> : digit}
                </button>
              )
            ))}
          </div>
          <p className="mt-5 text-center text-[12px] leading-[1.8] text-ink-muted [@media(max-height:700px)]:hidden">
            {getSupervisorDirectory().mode === "demo" ? "시연용 로그인이에요. " : ""}녹음은 이 기기에만 보관돼요.
          </p>
        </div>
      </div>
    </main>
  );
}
