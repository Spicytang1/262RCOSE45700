import { ChevronLeft, ChevronRight } from "lucide-react";
import Button from "@/components/Button";
import { dateText, DEMO_TRANSCRIPT, FIELD_CONFIG, focusStyle, recordingTitle, STATUS_LABEL, timeText } from "@/lib/recordingPresentation";
import useReviewAutosave from "@/lib/useReviewAutosave";
import { formatTime } from "@/lib/formatTime";
import type { DriveSession, RecordingEntry, RecordingStatus, StructuredFieldKey } from "@/types/report";
import { RecordingFrame, RecordingHeader, RecordingPanel } from "./RecordingChrome";
import RecordingPlayer from "./RecordingPlayer";
import RecordingLocationMap from "./RecordingLocationMap";

type Props = {
  supervisorName: string;
  recording: RecordingEntry;
  session: DriveSession | undefined;
  position: number;
  total: number;
  previousId?: string;
  nextId?: string;
  onOpen: (id: string) => void;
  onBack: () => void;
  onSaved: () => void;
};

export default function RecordingDetail({ supervisorName, recording, session, position, total, previousId, nextId, onOpen, onBack, onSaved }: Props) {
  const { draft, phase, change, flush, leave } = useReviewAutosave(recording, onSaved);

  const control = `w-full rounded-button border border-line bg-white px-3 py-3 text-[15px] ${focusStyle}`;

  return <RecordingFrame>
    <RecordingHeader title="녹음 상세" backLabel="목록" onBack={() => void leave(onBack)} />
    <nav aria-label="녹음 이동" className="flex items-center justify-between border-b border-line bg-white px-4 py-2">
      <button type="button" disabled={!previousId} onClick={() => previousId && void leave(() => onOpen(previousId))} className={`flex min-h-11 items-center rounded-button px-2 text-[13px] font-bold disabled:opacity-30 ${focusStyle}`}><ChevronLeft className="size-4" aria-hidden="true" />이전</button>
      <span className="text-[13px] font-semibold tabular-nums">{position} / {total}</span>
      <button type="button" disabled={!nextId} onClick={() => nextId && void leave(() => onOpen(nextId))} className={`flex min-h-11 items-center rounded-button px-2 text-[13px] font-bold disabled:opacity-30 ${focusStyle}`}>다음<ChevronRight className="size-4" aria-hidden="true" /></button>
    </nav>
    <div className="flex flex-col gap-3 px-5 pt-4">
      <section className="rounded-[20px] bg-ink p-5 text-white">
        <p className="text-[12px] font-bold text-kakao">{session ? `${session.number}회차 · ${session.endedAt ? "운행 종료" : "운행 중"}` : "이전 녹음 · 회차 미지정"}</p>
        <h2 className="mt-2 text-[20px] font-extrabold break-words">{recordingTitle({ ...recording, review: draft })}</h2>
        <p className="mt-3 text-[13px] text-white/85">{dateText(recording.recordedAt)} {timeText(recording.recordedAt)}</p>
        <p className="mt-1 text-[13px] text-white/85 [overflow-wrap:anywhere]">{supervisorName} · 녹음 {formatTime(recording.durationSec)}</p>
      </section>
      <div className="rounded-card border border-line bg-white px-4 py-3">
        <p role="status" className="text-[13px] font-semibold text-ink-sub">{phase === "saved" ? "변경 내용을 자동 저장했어요." : phase === "error" ? "자동 저장을 완료하지 못했어요." : phase === "saving" ? "자동 저장 중이에요…" : "변경 내용을 반영하고 있어요…"}</p>
        {phase === "error" && <><p role="alert" className="mt-2 text-[13px] text-[#b42318]">입력 내용은 유지하고 있어요. 저장 공간을 확인한 뒤 다시 시도해 주세요. 저장 전에는 이 화면을 닫지 마세요.</p><Button onClick={() => void flush()} className={`mt-3 w-full ${focusStyle}`}>저장 다시 시도</Button></>}
      </div>
      <fieldset className="contents">
        <legend className="sr-only">검토 상태와 녹음 제목</legend>
        <RecordingPanel title="검토 상태">
          <div className="grid grid-cols-3 gap-2">
            {(Object.entries(STATUS_LABEL) as [RecordingStatus, string][]).map(([value, label]) => <label key={value} className={`flex min-h-12 cursor-pointer items-center justify-center rounded-button px-1 text-[13px] font-bold ${draft.status === value ? "bg-ink text-white" : "bg-surface text-ink-sub"}`}><input type="radio" name="review-status" value={value} checked={draft.status === value} onChange={() => change(current => ({ ...current, status: value }))} className="mr-1.5 size-3.5 accent-kakao" />{label}</label>)}
          </div>
        </RecordingPanel>
        <RecordingPanel title="녹음 제목"><label htmlFor="recording-title" className="mb-2 block text-[13px] text-ink-sub">목록에 표시할 제목</label><input id="recording-title" name="recording-title" value={draft.title} onChange={event => { const title = event.target.value; change(current => ({ ...current, title })); }} maxLength={120} placeholder={recordingTitle({ ...recording, review: undefined })} className={control} /></RecordingPanel>
      </fieldset>
      <RecordingPanel title="원본 음성"><RecordingPlayer audio={recording.audio} durationSec={recording.durationSec} /></RecordingPanel>
      <RecordingPanel title="전사"><span className="mb-3 inline-block rounded-full bg-kakao-soft px-3 py-1 text-[12px] font-bold">시연용 예시</span><p className="text-[15px]">{DEMO_TRANSCRIPT}</p><p className="mt-3 text-[12px] text-ink-sub">모든 녹음에 동일한 예시를 표시해요. 실제 음성 인식 결과는 아니에요.</p></RecordingPanel>
      <RecordingPanel title="정리 항목">
        <p className="mb-4 text-[13px] text-ink-sub">시연용 예시로 채워 두었어요. 항목을 바꾸면 자동 저장돼요. 실제 음성·차량 데이터 분석 결과는 아니에요.</p>
        <fieldset className="flex flex-col gap-5"><legend className="sr-only">정리 항목 선택</legend>{(Object.entries(FIELD_CONFIG) as [StructuredFieldKey, (typeof FIELD_CONFIG)[StructuredFieldKey]][]).map(([key, config]) => {
          const value = draft.fields[key] ?? "";
          const isOther = draft.otherFields?.includes(key) || !config.options.includes(value);
          return <div key={key}>
            <label htmlFor={`field-${key}`} className="mb-1 block text-[14px] font-bold">{config.label}</label>
            <p id={`hint-${key}`} className="mb-2 text-[12px] text-ink-sub">{config.description}{key === "previousAction" ? " · 차량 데이터 수집을 가정한 예시" : ""}</p>
            <select id={`field-${key}`} name={`field-${key}`} aria-describedby={`hint-${key}`} value={isOther ? "__other__" : value} onChange={event => {
              const selection = event.target.value;
              change(current => ({ ...current, fields: { ...current.fields, [key]: selection === "__other__" ? "" : selection }, otherFields: selection === "__other__" ? [...(current.otherFields ?? []).filter(field => field !== key), key] : (current.otherFields ?? []).filter(field => field !== key) }));
            }} className={control}>
              {config.options.map(option => <option key={option} value={option}>{option}</option>)}<option value="__other__">기타</option>
            </select>
            {isOther && <div className="mt-3"><label htmlFor={`other-${key}`} className="mb-2 block text-[13px] font-semibold">{config.label} 기타 내용</label><input id={`other-${key}`} name={`other-${key}`} value={value} maxLength={500} onChange={event => { const text = event.target.value; change(current => ({ ...current, fields: { ...current.fields, [key]: text } })); }} placeholder="기타 내용을 입력해 주세요" className={control} /></div>}
          </div>;
        })}</fieldset>
      </RecordingPanel>
      <RecordingLocationMap location={recording.location} />
      <RecordingPanel title="차량 데이터"><p className="text-[14px] text-ink-sub">이전 동작은 차량에서 수집했다고 가정한 예시예요. 실제 차량 로그는 아직 연결되지 않았어요. 위 지도는 차량 위치가 아니라 녹음 시작 시 요청한 기기 위치예요.</p></RecordingPanel>
      <RecordingPanel title="메모"><label htmlFor="recording-note" className="mb-2 block text-[13px] text-ink-sub">사건 맥락이나 확인할 내용을 남겨 주세요.</label><textarea id="recording-note" name="recording-note" value={draft.note} onChange={event => { const note = event.target.value; change(current => ({ ...current, note })); }} rows={4} maxLength={5000} className={`${control} resize-y`} /></RecordingPanel>
      <p className="px-1 py-2 text-[12px] text-ink-sub">수정 내용은 이 브라우저에 자동 저장돼요. 원본 음성은 바꾸지 않아요.</p>
    </div>
  </RecordingFrame>;
}
