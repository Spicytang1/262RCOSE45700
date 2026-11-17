import { ChevronRight, Mic, Search } from "lucide-react";
import { dateText, DEMO_ADDRESS, focusStyle, recordingSummary, recordingTitle, STATUS_LABEL, timeText } from "@/lib/recordingPresentation";
import { formatTime } from "@/lib/formatTime";
import type { DriveSession, RecordingEntry } from "@/types/report";
import StateView from "@/components/StateView";
import { RecordingFrame, RecordingHeader } from "./RecordingChrome";
import { filteredRecordings, INITIAL_LIST_OPTIONS, type ListOptions } from "@/lib/recordingList";

type Props = {
  supervisorName: string;
  recordings: RecordingEntry[];
  sessions: DriveSession[];
  currentSession: DriveSession | undefined;
  options: ListOptions;
  onOptions: (options: ListOptions) => void;
  onOpen: (id: string) => void;
  onBack: () => void;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
};

export default function RecordingList({ supervisorName, recordings, sessions, currentSession, options, onOptions, onOpen, onBack, loading, error, onRetry }: Props) {
  const list = filteredRecordings(recordings, currentSession, options);
  const shown = list.slice(0, options.limit);
  const groups = new Map<string, RecordingEntry[]>();
  shown.forEach(record => { const key = record.sessionId ?? ""; const group = groups.get(key); if (group) group.push(record); else groups.set(key, [record]); });
  const sessionById = new Map(sessions.map(session => [session.id, session]));
  const sessionGroups = [...groups].sort(([a], [b]) => {
    const left = sessionById.get(a), right = sessionById.get(b);
    if (!left || !right) return Number(!!right) - Number(!!left);
    return options.sort === "latest" ? right.number - left.number : left.number - right.number;
  });
  const change = (patch: Partial<ListOptions>) => onOptions({ ...options, ...patch, limit: 30 });
  const control = `min-h-11 rounded-button border border-line bg-white px-3 text-[14px] ${focusStyle}`;

  return <RecordingFrame>
    <RecordingHeader title="녹음 목록" backLabel="대기" onBack={onBack} />
    <div className="flex flex-col gap-3 px-5 pt-4">
      <p className="text-[14px] text-ink-sub [overflow-wrap:anywhere]">{supervisorName}의 녹음이에요. 정차 후 확인해 주세요.</p>
      <div role="group" aria-label="녹음 범위" className="grid grid-cols-2 gap-1 rounded-button bg-line p-1">
        {([['all', '전체 녹음'], ['session', '이번 회차']] as const).map(([value, label]) => <button type="button" key={value} aria-pressed={options.scope === value} onClick={() => change({ scope: value })} className={`min-h-11 rounded-[9px] text-[14px] font-bold ${focusStyle} ${options.scope === value ? "bg-white text-ink shadow-sm" : "text-ink-sub"}`}>{label}</button>)}
      </div>
      <div>
        <label htmlFor="recording-search" className="sr-only">녹음 검색</label>
        <div className="relative"><Search className="absolute top-3.5 left-3 size-5 text-ink-sub" aria-hidden="true" /><input id="recording-search" name="recording-search" type="search" value={options.query} onChange={event => change({ query: event.target.value })} placeholder="전사·정리 항목·주소 등으로 검색" className={`${control} w-full pr-3 pl-10`} /></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label htmlFor="recording-status" className="sr-only">검토 상태</label><select id="recording-status" value={options.status} onChange={event => change({ status: event.target.value as ListOptions['status'] })} className={`${control} w-full`}><option value="all">전체 상태</option>{Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div><label htmlFor="recording-sort" className="sr-only">정렬</label><select id="recording-sort" value={options.sort} onChange={event => change({ sort: event.target.value as ListOptions['sort'] })} className={`${control} w-full`}><option value="latest">최신순</option><option value="oldest">오래된순</option></select></div>
      </div>
      {loading ? <StateView kind="loading" message="녹음을 불러오는 중이에요…" /> : error ? <StateView kind="error" message="녹음을 읽지 못했어요. 다시 시도해 주세요." onRetry={onRetry} /> : <>
        <p role="status" className="text-[13px] font-semibold text-ink-sub">{options.scope === "session" ? (currentSession ? `${currentSession.number}회차` : "시작한 운행 없음") : "전체 녹음"} · {list.length.toLocaleString("ko-KR")}건</p>
        {list.length === 0 && <StateView kind="empty" title={recordings.length === 0 ? "아직 보관한 녹음이 없어요" : "조건에 맞는 녹음이 없어요"} message={recordings.length === 0 ? "대기 화면에서 운행을 시작하고 첫 녹음을 남겨 주세요." : "전체 녹음을 선택하거나 검색·필터 조건을 바꿔 주세요."} action={<button type="button" onClick={() => onOptions({ ...INITIAL_LIST_OPTIONS, scope: "all" })} className={`min-h-11 rounded-button bg-surface px-4 text-[14px] font-bold ${focusStyle}`}>전체 녹음 보기</button>} />}
        {sessionGroups.map(([sessionId, records]) => {
          const groupSession = sessionById.get(sessionId);
          const label = groupSession ? `${groupSession.number}회차` : sessionId ? "회차 정보 없음" : "이전 녹음 · 회차 미지정";
          return <section key={sessionId} aria-label={label}><h2 className="mb-3 text-[15px] font-extrabold text-ink">{label}</h2><div className="flex flex-col gap-3">{records.map(record => {
          const session = record.sessionId ? sessionById.get(record.sessionId) : undefined;
          const status = record.review?.status ?? "new";
          return <button key={record.id} type="button" onClick={() => onOpen(record.id)} className={`relative flex w-full flex-col gap-2 rounded-[20px] border border-line bg-white p-4 pr-10 text-left shadow-card transition-[background-color,scale] duration-150 hover:border-ink-sub active:scale-[0.99] active:bg-kakao-soft ${focusStyle}`}>
            <span className="flex w-full min-w-0 items-center gap-3">
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[12px] font-bold ${status === "reviewed" ? "bg-ok-soft text-ok-ink" : status === "flagged" ? "bg-warning-soft text-warning-ink" : "bg-surface text-ink-sub"}`}>{STATUS_LABEL[status]}</span>
              {/* TODO(backend): 저장된 녹음 위치의 좌표를 주소로 변환한 서버 응답으로 교체한다. 현재는 위치 유무와 관계없는 표시용 예시이며 원본에 저장하지 않는다. */}
              <span className="shrink-0 whitespace-nowrap text-[13px] font-bold text-ink">{DEMO_ADDRESS} <span className="text-[10px] font-normal text-ink-sub">(임시 주소)</span></span>
            </span>
            <span title={recordingTitle(record)} className="w-full truncate text-[13px] font-medium text-ink-sub">{recordingTitle(record)}</span>
            <span className="text-[18px] leading-[1.7] font-extrabold [overflow-wrap:anywhere]">{recordingSummary(record)}</span>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ink-sub"><span>{dateText(record.recordedAt)} {timeText(record.recordedAt)}</span><span className="inline-flex items-center gap-1 tabular-nums"><Mic className="size-3.5" aria-hidden="true" />{formatTime(record.durationSec)}</span><span>{session ? `${session.number}회차` : "회차 미지정"}</span></span>
            <ChevronRight className="absolute top-1/2 right-3 size-5 -translate-y-1/2 text-ink-sub" aria-hidden="true" />
          </button>;
        })}</div></section>;
        })}
        {list.length > options.limit && <button type="button" onClick={() => onOptions({ ...options, limit: options.limit + 30 })} className={`${control} font-bold`}>녹음 더 보기</button>}
      </>}
      <p className="py-2 text-[12px] text-ink-sub">녹음은 이 기기의 같은 브라우저에만 보관돼요.</p>
    </div>
  </RecordingFrame>;
}
