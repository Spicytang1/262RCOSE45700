import { useEffect, useState } from "react";
import { ChevronRight, Info, Mic, Play, Square } from "lucide-react";
import type { DriveSession, Supervisor } from "@/types/report";
import ProfileAvatar from "@/components/ProfileAvatar";
import { focusStyle } from "@/lib/recordingPresentation";
import type { DrivePermissions } from "@/lib/drivePermissions";

type Props = {
  permissions: DrivePermissions | null;
  onStart: () => void;
  profile: Supervisor;
  recordingCount: number;
  session: DriveSession | undefined;
  loadState: "loading" | "error" | "ready";
  actionState: "idle" | "busy";
  actionError: string;
  notice: string;
  onChangeSupervisor: () => void;
  onStartSession: () => void;
  onEndSession: () => void;
  onOpenRecordings: () => void;
  onRetry: () => void;
};

function clock(totalSeconds: number) {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const h = String(Math.floor(safe / 3600)).padStart(2, "0");
  const m = String(Math.floor((safe % 3600) / 60)).padStart(2, "0");
  const s = String(safe % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

const rise = (delay: number) => ({ "--d": `${delay}ms` }) as React.CSSProperties;

export default function Standby({ permissions, onStart, profile, recordingCount, session, loadState, actionState, actionError, notice, onChangeSupervisor, onStartSession, onEndSession, onOpenRecordings, onRetry }: Props) {
  const active = !!session && !session.endedAt;
  const disabled = loadState !== "ready" || actionState === "busy";
  const checkingPermissions = permissions?.microphone === "checking" || permissions?.location === "checking";
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);

  const elapsed = active && session ? (now - new Date(session.startedAt).getTime()) / 1000 : 0;
  const stateText = loadState === "loading" ? "확인 중" : active ? "운행 중" : "운행 대기";
  const message = notice || (loadState === "error" ? "운행과 녹음을 불러오지 못했어요." : loadState === "loading" ? "운행 정보를 불러오고 있어요." : session && active ? "안전한 상황에서 녹음해 주세요." : "");

  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] touch-manipulation flex-col overflow-x-clip bg-surface leading-[1.7]">
      <header className="rise flex items-center justify-between px-5 pt-5">
        <h1 className="text-[18px] font-extrabold tracking-tight">주행 이슈 리포트</h1>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[13px] font-bold shadow-card">
          <span className={`size-2 rounded-full ${active ? "bg-ok" : "bg-ink-muted"}`} aria-hidden="true" />
          {stateText}
        </span>
      </header>

      <section aria-label="감독관과 운행 상태" className={`rise mx-5 mt-4 rounded-[28px] p-1.5 transition-colors duration-300 ${active ? "bg-ink/10" : "bg-white/60"}`} style={rise(60)}>
        <div className={`rounded-[22px] p-4 transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] ${active ? "bg-ink text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.14)]" : "bg-white text-ink shadow-card"}`}>
          <div className="flex items-center gap-3">
            <ProfileAvatar profile={profile} size="small" />
            <p className="min-w-0 flex-1 text-[16px] leading-tight font-extrabold [overflow-wrap:anywhere]">{profile.name}</p>
            <button type="button" onClick={onChangeSupervisor} disabled={disabled} className={`min-h-11 shrink-0 rounded-full px-4 text-[13px] font-bold transition-[background-color,scale] duration-150 active:scale-[0.96] disabled:opacity-40 ${active ? "bg-white/10 text-white hover:bg-white/15" : "bg-surface text-ink-sub hover:bg-line"} ${focusStyle}`}>감독관 변경</button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className={`rounded-[16px] px-3.5 py-3 ${active ? "bg-white/10" : "bg-surface"}`}>
              <p className={`text-[11px] font-semibold ${active ? "text-white/60" : "text-ink-muted"}`}>{active ? `${session?.number}회차 운행 시간` : session ? `${session.number}회차 종료` : "운행"}</p>
              <p className="mt-0.5 text-[22px] leading-tight font-extrabold tracking-tight tabular-nums">{active ? clock(elapsed) : loadState === "loading" ? "..." : "대기"}</p>
            </div>
            <button type="button" onClick={onOpenRecordings} disabled={actionState === "busy"} className={`rounded-[16px] px-3.5 py-3 text-left transition-[background-color,scale] duration-150 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.97] disabled:opacity-40 ${active ? "bg-white/10 hover:bg-white/15" : "bg-surface hover:bg-line"} ${focusStyle}`}>
              <span className={`block text-[11px] font-semibold ${active ? "text-white/60" : "text-ink-muted"}`}>이번 회차 녹음</span>
              <span className="flex items-baseline justify-between gap-1">
                <span aria-live="polite" className="text-[22px] leading-tight font-extrabold tabular-nums">
                  {loadState === "error" ? <span className="text-[13px] text-danger-soft">확인 불가</span> : loadState === "loading" ? <span className="text-[13px] opacity-70">불러오는 중</span> : <>{recordingCount.toLocaleString("ko-KR")}<span className="ml-0.5 text-[13px] font-bold">건</span></>}
                </span>
                <ChevronRight className={`size-4 shrink-0 self-center ${active ? "text-kakao" : "text-ink-sub"}`} strokeWidth={2} aria-label="목록 보기" />
              </span>
            </button>
          </div>
        </div>
      </section>

      <div className="rise mx-5 mt-2" style={rise(120)}>
        {message && <p role="status" className={`rounded-[14px] px-4 py-2 text-center text-[13px] leading-[1.6] ${notice ? "bg-kakao-soft text-ink" : "text-ink-sub"}`}>{message}</p>}
        {loadState === "error" && <button type="button" onClick={onRetry} className={`mt-2 min-h-11 w-full rounded-button bg-white font-bold shadow-card ${focusStyle}`}>다시 불러오기</button>}
        {actionError && <p role="alert" className="mt-2 text-[13px] text-danger-ink">{actionError}</p>}
      </div>

      <section aria-label="음성 기록" className="rise flex flex-1 flex-col px-5 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]" style={rise(180)}>
        <div className="relative flex min-h-[clamp(150px,34dvh,420px)] flex-1 items-center justify-center">
          <button
            type="button"
            onClick={active ? onStart : onStartSession}
            disabled={disabled || checkingPermissions}
            className={`relative flex size-[clamp(150px,min(38dvh,78vw),300px)] flex-col items-center justify-center gap-[clamp(6px,2dvh,16px)] rounded-full font-extrabold tracking-tight leading-none transition-[scale,background-color] duration-150 ease-[cubic-bezier(0.32,0.72,0,1)] active:scale-[0.98] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink ${active ? "bg-kakao text-[clamp(26px,4.6dvh,38px)] text-ink shadow-[0_18px_40px_rgba(254,229,0,0.45)] ring-[10px] ring-kakao/30 hover:bg-kakao-press active:bg-kakao-press" : "bg-ink text-[clamp(22px,4dvh,32px)] text-white shadow-[0_18px_40px_rgba(25,25,25,0.26)] ring-[10px] ring-ink/10 hover:bg-ink-sub active:bg-ink-sub"}`}
          >
            <span className={`flex items-center justify-center rounded-full ${active ? "size-[clamp(48px,11dvh,104px)] bg-ink/10" : "size-[clamp(44px,9dvh,88px)] bg-white/10"}`}>
              {active ? <Mic className="size-[52%]" strokeWidth={2.2} aria-hidden="true" /> : <Play className="size-[46%] fill-kakao text-kakao" strokeWidth={2.2} aria-hidden="true" />}
            </span>
            {actionState === "busy" ? "처리 중" : active ? "녹음" : "운행 시작"}
          </button>
        </div>
        {active && <button type="button" onClick={onEndSession} disabled={disabled} className={`mt-3 flex h-14 w-full items-center justify-center gap-2 rounded-[20px] border-2 border-ink/25 bg-white text-[16px] font-bold text-ink shadow-card transition-[background-color,scale,border-color] duration-150 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-ink/50 active:scale-[0.98] active:bg-line disabled:opacity-40 ${focusStyle}`}><Square className="size-4 fill-current" aria-hidden="true" />운행 종료</button>}
        <p className="mt-3 flex items-start justify-center gap-2 text-[12px] leading-[1.7] text-ink-muted [@media(max-height:700px)]:hidden">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>운행을 시작할 때 마이크와 위치 권한을 확인해요. 위치는 녹음할 때마다 새로 받아요.</span>
        </p>
      </section>
    </main>
  );
}
