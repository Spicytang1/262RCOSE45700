import { ChevronLeft, ChevronRight } from "lucide-react";
import Button from "@/components/Button";
import { dateText, DEMO_TRANSCRIPT, DEMO_VEHICLE_DATA, FIELD_CONFIG, focusStyle, recordingTitle, STATUS_LABEL, timeText } from "@/lib/recordingPresentation";
import useReviewAutosave from "@/lib/useReviewAutosave";
import { formatTime } from "@/lib/formatTime";
import type { DriveSession, RecordingEntry, RecordingStatus, StructuredFieldKey } from "@/types/report";
import { RecordingFrame, RecordingHeader, RecordingPanel } from "./RecordingChrome";
import RecordingPlayer from "./RecordingPlayer";
import RecordingLocationMap from "./RecordingLocationMap";
import RecordingVideo from "./RecordingVideo";

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

/** 녹음 시작 방식 표시 문구. 시작 방식이 저장되지 않은 이전 녹음은 "시작 방식 기록 없음"으로 보여준다. */
const START_TRIGGER_LABEL = { button: "직접 녹음", intervention: "수동 개입 자동 시작" } as const;

export default function RecordingDetail({ supervisorName, recording, session, position, total, previousId, nextId, onOpen, onBack, onSaved }: Props) {
  const { draft, phase, change, flush, leave } = useReviewAutosave(recording, onSaved);

  const control = `w-full rounded-button border border-line bg-white px-3 py-3 text-[15px] ${focusStyle}`;
  const sessionLabel = session ? `${session.number}회차 · ${session.endedAt ? "운행 종료" : "운행 중"}` : "이전 녹음 · 회차 미지정";
  const triggerLabel = recording.startTrigger ? START_TRIGGER_LABEL[recording.startTrigger] : "시작 방식 기록 없음";

  return <RecordingFrame>
    <RecordingHeader title="녹음 상세" backLabel="목록" onBack={() => void leave(onBack)} />
    <nav aria-label="녹음 이동" className="flex items-center justify-between border-b border-line bg-white px-4 py-2">
      <button type="button" disabled={!previousId} onClick={() => previousId && void leave(() => onOpen(previousId))} className={`flex min-h-11 items-center rounded-button px-2 text-[13px] font-bold disabled:opacity-30 ${focusStyle}`}><ChevronLeft className="size-4" aria-hidden="true" />이전</button>
      <span className="text-[13px] font-semibold tabular-nums">{position} / {total}</span>
      <button type="button" disabled={!nextId} onClick={() => nextId && void leave(() => onOpen(nextId))} className={`flex min-h-11 items-center rounded-button px-2 text-[13px] font-bold disabled:opacity-30 ${focusStyle}`}>다음<ChevronRight className="size-4" aria-hidden="true" /></button>
    </nav>
    <div className="flex flex-col gap-3 px-5 pt-4">
      <section className="rounded-[20px] bg-ink p-5 text-white">
        <p className="text-[12px] font-bold text-kakao" data-start-trigger={recording.startTrigger ?? "none"}>{sessionLabel} · {triggerLabel}</p>
        <h2 className="mt-2 text-[20px] font-extrabold break-words">{recordingTitle({ ...recording, review: draft })}</h2>
        <p className="mt-3 text-[13px] text-white/85">{dateText(recording.recordedAt)} {timeText(recording.recordedAt)}</p>
        {/* TODO(backend): 녹음 좌표를 주소로 변환한 응답으로 교체한다. XX동 XX로는 표시용 임시 주소이며 원본에 저장하지 않는다. */}
        <p title="임시 주소예요. 실제 위치와 연결되지 않았어요." aria-label="XX동 XX로 (임시 주소)" className="mt-2 text-[20px] font-extrabold break-words">XX동 XX로</p>
        <p className="mt-1 text-[13px] text-white/85 [overflow-wrap:anywhere]">{supervisorName} · 녹음 {formatTime(recording.durationSec)}</p>
      </section>
      <div className="rounded-card border border-line bg-white px-4 py-3">
        <p role="status" className="text-[13px] font-semibold text-ink-sub">{phase === "saved" ? "변경 내용을 자동 저장했어요." : phase === "error" ? "자동 저장을 완료하지 못했어요." : phase === "saving" ? "자동 저장 중이에요…" : "변경 내용을 반영하고 있어요…"}</p>
        {phase === "error" && <><p role="alert" className="mt-2 text-[13px] text-danger-ink">입력 내용은 유지하고 있어요. 저장 공간을 확인한 뒤 다시 시도해 주세요. 저장 전에는 이 화면을 닫지 마세요.</p><Button onClick={() => void flush()} className={`mt-3 w-full ${focusStyle}`}>저장 다시 시도</Button></>}
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
      {/* TODO(backend): DEMO_TRANSCRIPT 대신 녹음별 전사 응답을 표시하고 처리 중·실패·미연결 상태를 구분한다. */}
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
              change(current => {
                const previous = current.fields[key] ?? "";
                const wasOther = current.otherFields?.includes(key) || !config.options.includes(previous);
                // 이전 형식의 기타 값도 첫 전환 시 보존한다. 빈 문자열은 사용자가 지운 값이므로 그대로 유지한다.
                const otherFieldValues = { ...current.otherFieldValues, ...(wasOther ? { [key]: previous } : {}) };
                return {
                  ...current,
                  fields: { ...current.fields, [key]: selection === "__other__" ? otherFieldValues[key] ?? "" : selection },
                  otherFields: selection === "__other__" ? [...(current.otherFields ?? []).filter(field => field !== key), key] : (current.otherFields ?? []).filter(field => field !== key),
                  otherFieldValues,
                };
              });
            }} className={control}>
              {config.options.map(option => <option key={option} value={option}>{option}</option>)}<option value="__other__">기타</option>
            </select>
            {isOther && <div className="mt-3"><label htmlFor={`other-${key}`} className="mb-2 block text-[13px] font-semibold">{config.label} 기타 내용</label><input id={`other-${key}`} name={`other-${key}`} value={value} maxLength={500} onChange={event => { const text = event.target.value; change(current => ({ ...current, fields: { ...current.fields, [key]: text }, otherFieldValues: { ...current.otherFieldValues, [key]: text } })); }} placeholder="기타 내용을 입력해 주세요" className={control} /></div>}
          </div>;
        })}</fieldset>
      </RecordingPanel>
      <RecordingLocationMap location={recording.location} />
      <RecordingVideo durationSec={recording.durationSec} />
      {/* TODO(backend): 녹음 시각·회차와 연결된 차량 로그(이전 동작·속도·차선·저크 등)를 서버에서 조회해 표시한다. 기기 위치를 차량 GPS로 대체 사용하지 않는다. */}
      <RecordingPanel title="차량 데이터">
        <span className="mb-3 inline-block rounded-full bg-kakao-soft px-3 py-1 text-[12px] font-bold">임시 데이터</span>
        <h3 className="text-[14px] font-bold">차량에서 수집할 수 있는 항목</h3>
        <p className="mt-2 text-[13px] text-ink-sub">모든 녹음에 동일한 예시를 표시해요. 실제 차량과는 연결되지 않았으며, 위 지도에 표시하는 기기 위치와도 별개예요.</p>
        <dl className="mt-3 divide-y divide-line">
          {DEMO_VEHICLE_DATA.map(({ label, value }) => <div key={label} className="flex items-start justify-between gap-3 py-3">
            <dt className="shrink-0 text-[13px] text-ink-sub">{label}</dt>
            <dd className="min-w-0 text-right text-[14px] font-bold tabular-nums [overflow-wrap:anywhere]"><span className="mr-1 text-[11px] font-normal text-ink-sub">예시</span>{value}</dd>
          </div>)}
        </dl>
      </RecordingPanel>
      <RecordingPanel title="메모"><label htmlFor="recording-note" className="mb-2 block text-[13px] text-ink-sub">사건 맥락이나 확인할 내용을 남겨 주세요.</label><textarea id="recording-note" name="recording-note" value={draft.note} onChange={event => { const note = event.target.value; change(current => ({ ...current, note })); }} rows={4} maxLength={5000} className={`${control} resize-y`} /></RecordingPanel>
      <p className="px-1 py-2 text-[12px] text-ink-sub">수정 내용은 이 브라우저에 자동 저장돼요. 원본 음성은 바꾸지 않아요.</p>
    </div>
  </RecordingFrame>;
}
