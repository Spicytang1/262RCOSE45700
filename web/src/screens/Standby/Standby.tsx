import { ChevronRight, Info, Mic, Play } from "lucide-react";
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

export default function Standby({ permissions, onStart, profile, recordingCount, session, loadState, actionState, actionError, notice, onChangeSupervisor, onStartSession, onEndSession, onOpenRecordings, onRetry }: Props) {
  const active = !!session && !session.endedAt;
  const disabled = loadState !== "ready" || actionState === "busy";
  const checkingPermissions = permissions?.microphone === "checking" || permissions?.location === "checking";
  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] flex-col bg-white px-5 pt-6 pb-8">
      <header className="flex items-center justify-between">
        <h1 className="text-[20px] font-extrabold tracking-tight">주행 이슈 리포트</h1>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-[13px] font-semibold text-ink-sub">
          <span className={`size-2 rounded-full ${active ? "bg-[#16a55c]" : "bg-ink-sub"}`} aria-hidden="true" />
          {loadState === "loading" ? "확인 중" : active ? "운행 중" : "운행 대기"}
        </span>
      </header>

      <section
        aria-label="감독관과 보관 기록"
        className="mt-5 grid grid-cols-2 divide-x divide-line overflow-hidden rounded-card bg-surface"
      >
        <div className="flex flex-col items-center gap-1 py-5">
          <span className="text-[13px] font-medium text-ink-sub">현재 감독관</span>
          <ProfileAvatar profile={profile} size="small" />
          <span className="w-full px-3 text-center text-[19px] font-extrabold [overflow-wrap:anywhere]">{profile.name}</span>
          <button type="button" onClick={onChangeSupervisor} disabled={disabled} className="min-h-11 rounded-button px-3 text-[13px] font-semibold text-ink-sub underline underline-offset-4 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2">감독관 변경</button>
        </div>
        <button type="button" onClick={onOpenRecordings} disabled={actionState === "busy"} className="flex flex-col items-center justify-center gap-1 py-5 hover:bg-kakao-soft active:bg-kakao focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ink disabled:opacity-40">
          <span className="text-[13px] font-medium text-ink-sub">이번 회차 녹음</span>
          <span aria-live="polite" className="text-[26px] font-extrabold">
            {loadState === "error" ? <span className="text-[14px] text-[#b42318]">건수 확인 불가</span> : loadState === "loading" ? <span className="text-[14px] text-ink-sub">불러오는 중…</span> : <>{recordingCount.toLocaleString("ko-KR")}<span className="ml-0.5 text-[16px] font-bold">건</span></>}
          </span>
          <span className="flex min-h-11 items-center gap-0.5 text-[12px] font-semibold text-ink-sub">녹음 목록 보기<ChevronRight className="size-3.5" aria-hidden="true" /></span>
        </button>
      </section>

      <p role="status" className={`mt-3 min-h-12 rounded-button px-3 py-2 text-center text-[13px] leading-[1.8] ${notice ? "bg-kakao-soft text-ink" : "text-ink-sub"}`}>
        {notice || (loadState === "error" ? "운행과 녹음을 읽지 못했어요." : loadState === "loading" ? "운행 정보를 확인하고 있어요…" : session ? `${session.number}회차 ${active ? "운행 중이에요. 상황이 안정된 후 녹음해 주세요." : "운행이 끝났어요. 녹음 목록에서 기록을 확인해 주세요."}` : "운행을 시작하면 이번 회차의 녹음을 남길 수 있어요.")}
      </p>
      {loadState === "error" && <button type="button" onClick={onRetry} className={`min-h-11 rounded-button bg-surface font-bold ${focusStyle}`}>다시 불러오기</button>}
      {actionError && <p role="alert" className="mt-2 text-[13px] text-[#b42318]">{actionError}</p>}

      <section aria-label="음성 기록" className="flex flex-1 flex-col items-center justify-center gap-14 py-10">
        <div className="relative flex items-center justify-center">
          {active && <span
            aria-hidden="true"
            className="absolute size-44 rounded-full bg-kakao animate-pulse-ring motion-reduce:hidden"
          />}
          <button
            type="button"
            onClick={active ? onStart : onStartSession}
            disabled={disabled || checkingPermissions}
            className={`relative flex size-44 flex-col items-center justify-center gap-2 rounded-full transition-transform active:scale-95 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-8 focus-visible:outline-ink ${active ? "bg-kakao text-ink shadow-[0_10px_30px_rgba(254,229,0,0.45)] hover:bg-kakao-press active:bg-kakao-press" : "bg-[#167347] text-white shadow-[0_10px_30px_rgba(22,115,71,0.22)] hover:bg-[#125f3b] active:bg-[#0e4c2f]"}`}
          >
            {active ? <Mic className="size-12" strokeWidth={2.2} aria-hidden="true" /> : <Play className="size-10" strokeWidth={2.2} aria-hidden="true" />}
            <span className="text-[19px] font-extrabold">{actionState === "busy" ? "처리 중…" : active ? "녹음" : "운행 시작"}</span>
          </button>
        </div>
        <div className="flex flex-col items-center gap-3"><p className="text-[15px] font-medium text-ink-sub">{active ? "버튼을 누르면 바로 녹음이 시작돼요" : "새 운행을 시작하고 녹음을 남겨 주세요"}</p>{active && <button type="button" onClick={onEndSession} disabled={disabled} className={`min-h-11 rounded-button border border-line px-6 text-[14px] font-bold text-ink-sub hover:bg-surface disabled:opacity-40 ${focusStyle}`}>운행 종료</button>}</div>
      </section>

      <p className="flex items-center justify-center gap-2 rounded-button bg-surface px-4 py-3.5 text-[14px] text-ink-sub">
        <Info className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
        <span>운행 시작 때 마이크·위치 권한을 확인해요. 위치는 녹음 시작 때 새로 받아요.</span>
      </p>
    </main>
  );
}
