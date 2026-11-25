import { useEffect, useRef, useState } from "react";
import { ArrowRight, Mic } from "lucide-react";
import type { Supervisor } from "@/types/report";
import { findSupervisorByCode, getSupervisorDirectory } from "@/lib/supervisorDirectory";

const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

export default function Login({ onLogin }: { onLogin: (supervisor: Supervisor, signal: AbortSignal) => void | Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => () => request.current?.abort(), []);

  async function submitCode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !code) return;
    setError("");
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    try {
      const found = await findSupervisorByCode(code);
      if (controller.signal.aborted) return;
      if (found) { await onLogin(found, controller.signal); return; }
      setError("등록되지 않은 코드예요. 다시 확인해 주세요.");
    } catch {
      if (!controller.signal.aborted) setError("로그인하지 못했어요. 다시 시도해 주세요.");
    } finally { if (!controller.signal.aborted) setBusy(false); }
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
          로그인 코드를<br />입력해 주세요
        </h1>

        <form onSubmit={event => void submitCode(event)} className="rise mt-[clamp(12px,3dvh,32px)]" style={{ "--d": "210ms" } as React.CSSProperties}>
          <label htmlFor="login-code" className="sr-only">로그인 코드</label>
          <input id="login-code" name="login-code" type="text" autoComplete="off" autoCapitalize="off" spellCheck={false} maxLength={8} value={code} disabled={busy} onChange={event => { setCode(event.target.value); setError(""); }} aria-invalid={!!error} aria-describedby="login-code-help" placeholder="로그인 코드" className={`h-[clamp(52px,8dvh,68px)] w-full rounded-[20px] bg-white/[0.09] px-5 text-[18px] font-semibold tracking-[0.08em] text-white placeholder:text-[14px] placeholder:font-normal placeholder:tracking-normal placeholder:text-white/45 ring-1 outline-none transition-[box-shadow,background-color] focus:ring-2 focus:ring-kakao ${error ? "ring-danger-soft" : "ring-white/15"}`} />
          <p id="login-code-help" role={error ? "alert" : "status"} className={`mt-2 min-h-6 text-[13px] leading-[1.7] ${error ? "text-danger-soft" : "text-white/60"}`}>{error || (busy ? "로그인 정보를 확인하고 있어요…" : "발급된 로그인 코드를 입력해 주세요.")}</p>
          <button type="submit" disabled={busy || !code} className={`mt-3 flex min-h-14 w-full items-center justify-center gap-2 rounded-[18px] bg-kakao px-5 text-[16px] font-extrabold text-ink transition-[opacity,scale] active:scale-[0.98] disabled:opacity-40 ${focusStyle}`}>
            {busy ? "확인 중…" : <>로그인 <ArrowRight className="size-5" aria-hidden="true" /></>}
          </button>
        </form>
      </section>

      <p className="rise px-6 pb-[max(20px,env(safe-area-inset-bottom))] text-center text-[12px] leading-[1.8] text-white/55 [@media(max-height:700px)]:hidden" style={{ "--d": "260ms" } as React.CSSProperties}>
        {getSupervisorDirectory().mode === "demo" ? "시연용 로그인이에요. " : ""}녹음은 이 기기에만 보관돼요.
      </p>
    </main>
  );
}
