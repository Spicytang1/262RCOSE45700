import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Delete, ShieldCheck } from "lucide-react";
import type { Supervisor } from "@/types/report";
import useSupervisors from "@/lib/useSupervisors";
import { authenticateSupervisor } from "@/lib/sessionProfiles";
import { getSupervisorDirectory, supervisorKey } from "@/lib/supervisorDirectory";
import ProfileAvatar from "@/components/ProfileAvatar";

const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

export default function Login({ onLogin }: { onLogin: (supervisor: Supervisor, signal: AbortSignal) => void | Promise<void> }) {
  const { supervisors, status, reload } = useSupervisors();
  const [selected, setSelected] = useState<Supervisor | null>(null);
  const [busy, setBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => { heading.current?.focus(); }, [selected]);
  useEffect(() => () => request.current?.abort(), []);

  async function enterDigit(digit: string) {
    if (selected === null || pin.length >= 4 || busy) return;
    setError("");
    const next = pin + digit;
    setPin(next);
    if (next.length === 4) {
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      try {
        const allowed = await authenticateSupervisor(selected.id, next, controller.signal);
        if (controller.signal.aborted) return;
        if (allowed) { await onLogin(selected, controller.signal); return; }
        setPin(""); setError("비밀번호가 맞지 않거나 선택한 감독관을 사용할 수 없어요. 다시 확인해 주세요.");
      } catch {
        if (!controller.signal.aborted) { setPin(""); setError("로그인 또는 이전 운행 종료를 완료하지 못했어요. 다시 입력하거나 목록을 새로 불러와 주세요."); }
      } finally { if (!controller.signal.aborted) setBusy(false); }
    }
  }

  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] touch-manipulation flex-col bg-white px-6 pt-6 pb-[max(24px,env(safe-area-inset-bottom))] leading-[1.7]">
      <header className="flex min-h-9 items-center gap-3">
        {selected !== null && (
          <button type="button" aria-label="감독관 다시 선택" className={`flex size-11 items-center justify-center rounded-button bg-surface ${focusStyle}`} onClick={() => { request.current?.abort(); setBusy(false); setSelected(null); setPin(""); setError(""); void reload(); }}>
            <ArrowLeft className="size-5" aria-hidden="true" />
          </button>
        )}
        <span className="text-[17px] font-extrabold">주행 이슈 리포트</span>
        <ShieldCheck className="ml-auto size-5 text-ink-sub" aria-hidden="true" />
      </header>

      <section className="flex flex-1 flex-col justify-center py-9">
        <div className="mb-8">
          <h1 ref={heading} tabIndex={-1} className="rounded text-[28px] leading-[1.4] font-extrabold tracking-tight focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">
            {selected === null ? <>기록할 감독관을<br />선택해 주세요</> : <span className="break-words [overflow-wrap:anywhere]">{selected.name}</span>}
          </h1>
          <p className="mt-3 text-[15px] text-ink-sub">
            {selected === null ? "선택한 감독관의 이름으로 녹음을 보관해요." : "숫자 버튼으로 비밀번호 4자리를 입력해 주세요."}
          </p>
        </div>

        {selected === null ? (
          status === "loading" ? <p role="status">감독관 목록을 불러오는 중이에요…</p> : status === "error" ? <div role="alert"><p>감독관 목록을 불러오지 못했어요.</p><button type="button" onClick={() => void reload()} className={`mt-4 min-h-11 rounded-button bg-kakao px-4 font-bold ${focusStyle}`}>다시 불러오기</button></div> : supervisors.length === 0 ? <div><p role="status">등록된 감독관이 없어요. 관리자에게 문의해 주세요.</p><button type="button" onClick={() => void reload()} className={`mt-4 min-h-11 rounded-button bg-surface px-4 font-bold ${focusStyle}`}>목록 새로고침</button></div> : <div className="grid grid-cols-2 gap-3" aria-label="감독관 선택">
            {supervisors.map((supervisor) => (
              <button key={supervisorKey(supervisor.id)} type="button" aria-label={supervisor.name} onClick={() => setSelected(supervisor)} className={`flex min-h-32 min-w-0 flex-col items-start justify-center gap-4 rounded-card border border-line bg-surface p-5 text-left transition-colors hover:border-ink-sub active:bg-kakao-soft ${focusStyle}`}>
                <ProfileAvatar profile={supervisor} />
                <span className="w-full text-[17px] font-bold [overflow-wrap:anywhere]">{supervisor.name}</span>
              </button>
            ))}
          </div>
        ) : (
          <>
            <div className="mb-2 flex justify-center gap-5 rounded-card bg-surface py-6" role="status" aria-label={`비밀번호 4자리 중 ${pin.length}자리 입력됨`}>
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
          </>
        )}
      </section>

      <footer className="border-t border-line pt-4 text-[12px] leading-[1.8] text-ink-sub">
        {getSupervisorDirectory().mode === "demo" && <p>시연용 로그인이에요. 초기 비밀번호는 모두 1234예요.</p>}
        <p>녹음은 이 기기의 같은 브라우저에만 보관돼요.</p>
      </footer>
    </main>
  );
}
