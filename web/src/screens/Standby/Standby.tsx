import { Info, Mic } from "lucide-react";

type Props = {
  onStart: () => void;
};

// 서버 연결 전까지 사용하는 가짜 데이터
const TODAY = { driveCount: 3, issueCount: 2 };

export default function Standby({ onStart }: Props) {
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
        aria-label="오늘 운행 정보"
        className="mt-5 grid grid-cols-2 divide-x divide-line rounded-card bg-surface py-5"
      >
        <div className="flex flex-col items-center gap-1">
          <span className="text-[13px] font-medium text-ink-muted">오늘 운행</span>
          <span className="text-[26px] font-extrabold">
            {TODAY.driveCount}
            <span className="ml-0.5 text-[16px] font-bold">회차</span>
          </span>
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-[13px] font-medium text-ink-muted">기록한 이슈</span>
          <span className="text-[26px] font-extrabold">
            {TODAY.issueCount}
            <span className="ml-0.5 text-[16px] font-bold">건</span>
          </span>
        </div>
      </section>

      <section aria-label="음성 기록" className="flex flex-1 flex-col items-center justify-center gap-14 py-10">
        <div className="relative flex items-center justify-center">
          <span
            aria-hidden="true"
            className="absolute size-44 rounded-full bg-kakao animate-pulse-ring motion-reduce:hidden"
          />
          <button
            type="button"
            onClick={onStart}
            className="relative flex size-44 flex-col items-center justify-center gap-2 rounded-full bg-kakao text-ink shadow-[0_10px_30px_rgba(254,229,0,0.45)] transition-transform active:scale-95 active:bg-kakao-press"
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
