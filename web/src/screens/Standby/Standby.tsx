import { Info, Mic } from "lucide-react";
import type { SupervisorId } from "@/types/report";

type Props = {
  onStart: () => void;
  supervisorId: SupervisorId;
  recordingCount: number | null;
  countError: boolean;
  notice: string;
  onChangeSupervisor: () => void;
};

export default function Standby({ onStart, supervisorId, recordingCount, countError, notice, onChangeSupervisor }: Props) {
  return (
    <main className="app-frame mx-auto flex min-h-dvh w-full max-w-[430px] flex-col bg-white px-5 pt-6 pb-8">
      <header className="flex items-center justify-between">
        <h1 className="text-[22px] font-extrabold tracking-tight">주행 이슈 리포트</h1>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-[13px] font-semibold text-ink-sub">
          <span className="size-2 rounded-full bg-[#16a55c]" aria-hidden="true" />
          운행 중
        </span>
      </header>

      <section
        aria-label="감독관과 보관 기록"
        className="mt-5 grid grid-cols-2 divide-x divide-line rounded-card bg-surface py-5"
      >
        <div className="flex flex-col items-center gap-1">
          <span className="text-[13px] font-medium text-ink-sub">현재 감독관</span>
          <span className="text-[21px] font-extrabold">감독관 {supervisorId}</span>
          <button type="button" onClick={onChangeSupervisor} className="min-h-11 rounded-button px-3 text-[13px] font-semibold text-ink-sub underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2">감독관 변경</button>
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-[13px] font-medium text-ink-sub">보관한 녹음</span>
          <span aria-live="polite" className="text-[26px] font-extrabold">
            {countError ? <span className="text-[14px] text-[#b42318]">건수 확인 불가</span> : recordingCount === null ? <span className="text-[14px] text-ink-sub">불러오는 중</span> : <>{recordingCount}<span className="ml-0.5 text-[16px] font-bold">건</span></>}
          </span>
          <span className="flex min-h-11 items-center text-[12px] text-ink-sub">이 브라우저에 보관</span>
        </div>
      </section>

      <p role="status" className={`mt-3 min-h-12 rounded-button px-3 py-2 text-center text-[13px] leading-[1.8] ${notice ? "bg-kakao-soft text-ink" : "text-ink-sub"}`}>
        {notice || (countError ? "보관 건수를 읽지 못했어요. 다시 로그인해 주세요." : recordingCount === 0 ? "아직 보관한 녹음이 없어요." : "녹음을 모아 보고 수정하는 화면은 준비 중이에요.")}
      </p>

      <section aria-label="음성 기록" className="flex flex-1 flex-col items-center justify-center gap-14 py-10">
        <div className="relative flex items-center justify-center">
          <span
            aria-hidden="true"
            className="absolute size-44 rounded-full bg-kakao animate-pulse-ring motion-reduce:hidden"
          />
          <button
            type="button"
            onClick={onStart}
            className="relative flex size-44 flex-col items-center justify-center gap-2 rounded-full bg-kakao text-ink shadow-[0_10px_30px_rgba(254,229,0,0.45)] transition-transform active:scale-95 active:bg-kakao-press focus-visible:outline-2 focus-visible:outline-offset-8 focus-visible:outline-ink"
          >
            <Mic className="size-12" strokeWidth={2.2} aria-hidden="true" />
            <span className="text-[19px] font-extrabold">녹음</span>
          </button>
        </div>
        <p className="text-[15px] font-medium text-ink-sub">버튼을 누르면 바로 녹음이 시작돼요</p>
      </section>

      <p className="flex items-center justify-center gap-2 rounded-button bg-surface px-4 py-3.5 text-[14px] text-ink-sub">
        <Info className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
        상황이 안정된 후 버튼을 눌러 말씀해 주세요.
      </p>
    </main>
  );
}
