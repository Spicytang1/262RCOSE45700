import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Delete, ShieldCheck, UserRound } from "lucide-react";
import type { SupervisorId } from "@/types/report";

const SUPERVISORS: SupervisorId[] = [1, 2, 3, 4, 5, 6];
// 사용자가 지정한 시연용 PIN. 실제 접근 보호를 위한 인증이 아니다.
const DEMO_PIN = "1234";
const focusStyle = "focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

export default function Login({ onLogin }: { onLogin: (id: SupervisorId) => void }) {
  const [selected, setSelected] = useState<SupervisorId | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => { heading.current?.focus(); }, [selected]);

  function enterDigit(digit: string) {
    if (selected === null || pin.length >= 4) return;
    setError("");
    const next = pin + digit;
    if (next.length === 4) {
      if (next === DEMO_PIN) { onLogin(selected); return; }
      setPin("");
      setError("비밀번호가 맞지 않아요. 다시 입력해 주세요.");
      return;
    }
    setPin(next);
  }

  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] touch-manipulation flex-col bg-white px-6 pt-6 pb-[max(24px,env(safe-area-inset-bottom))] leading-[1.7]">
      <header className="flex min-h-9 items-center gap-3">
        {selected !== null && (
          <button type="button" aria-label="감독관 다시 선택" className={`flex size-10 items-center justify-center rounded-button bg-surface ${focusStyle}`} onClick={() => { setSelected(null); setPin(""); setError(""); }}>
            <ArrowLeft className="size-5" aria-hidden="true" />
          </button>
        )}
        <span className="text-[17px] font-extrabold">주행 이슈 리포트</span>
        <ShieldCheck className="ml-auto size-5 text-ink-sub" aria-hidden="true" />
      </header>

      <section className="flex flex-1 flex-col justify-center py-9">
        <div className="mb-8">
          <h1 ref={heading} tabIndex={-1} className="rounded text-[28px] leading-[1.4] font-extrabold tracking-tight focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">
            {selected === null ? <>기록할 감독관을<br />선택해 주세요</> : `감독관 ${selected}`}
          </h1>
          <p className="mt-3 text-[15px] text-ink-sub">
            {selected === null ? "선택한 감독관의 이름으로 녹음을 보관해요." : "숫자 버튼으로 비밀번호 4자리를 입력해 주세요."}
          </p>
        </div>

        {selected === null ? (
          <div className="grid grid-cols-2 gap-3" aria-label="감독관 선택">
            {SUPERVISORS.map((id) => (
              <button key={id} type="button" onClick={() => setSelected(id)} className={`flex min-h-32 flex-col items-start justify-center gap-4 rounded-card border border-line bg-surface p-5 text-left transition-colors hover:border-ink-sub active:bg-kakao-soft ${focusStyle}`}>
                <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-xl bg-kakao"><UserRound className="size-6" /></span>
                <span className="text-[17px] font-bold">감독관 {id}</span>
              </button>
            ))}
          </div>
        ) : (
          <>
            <div className="mb-2 flex justify-center gap-5 rounded-card bg-surface py-6" role="status" aria-label={`비밀번호 4자리 중 ${pin.length}자리 입력됨`}>
              {[0, 1, 2, 3].map((index) => <span key={index} aria-hidden="true" className={`size-4 rounded-full ${index < pin.length ? "bg-ink" : "border-2 border-ink-sub/40"}`} />)}
            </div>
            <p role="alert" className="mb-3 min-h-12 text-center text-[13px] leading-[1.7] text-[#b42318]">{error}</p>
            <div className="grid grid-cols-3 gap-3" aria-label="숫자 키패드">
              {["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "delete"].map((digit, index) => (
                digit === "" ? <span key={`blank-${index}`} /> : (
                  <button key={digit} type="button" aria-label={digit === "delete" ? "한 자리 지우기" : digit} disabled={digit === "delete" && !pin.length} onClick={() => { if (digit === "delete") { setPin((value) => value.slice(0, -1)); setError(""); } else enterDigit(digit); }} className={`flex h-16 items-center justify-center rounded-button text-[27px] font-bold tabular-nums transition-colors active:bg-kakao disabled:opacity-30 ${digit === "delete" ? "bg-transparent" : "bg-surface hover:bg-line"} ${focusStyle}`}>
                    {digit === "delete" ? <Delete className="size-6" aria-hidden="true" /> : digit}
                  </button>
                )
              ))}
            </div>
          </>
        )}
      </section>

      <footer className="border-t border-line pt-4 text-[12px] leading-[1.8] text-ink-sub">
        <p>시연용 로그인이에요. 초기 비밀번호는 모두 1234예요.</p>
        <p>녹음은 이 기기의 같은 브라우저에만 보관돼요.</p>
      </footer>
    </main>
  );
}
