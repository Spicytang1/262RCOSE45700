import { useState } from "react";
import { ArrowLeft, ChevronDown, ChevronLeft, ChevronRight, MapPin, Pencil, Route, Timer, UserRound } from "lucide-react";
import Button from "@/components/Button";
import OptionMenu from "@/components/OptionMenu";
import { dateText, DEMO_TRANSCRIPT, DEMO_VEHICLE_DATA, FIELD_CONFIG, focusStyle, recordingTitle, STATUS_LABEL, timeText } from "@/lib/recordingPresentation";
import useReviewAutosave from "@/lib/useReviewAutosave";
import { formatTime } from "@/lib/formatTime";
import type { DriveSession, RecordingEntry, RecordingStatus, StructuredFieldKey } from "@/types/report";
import { RecordingFold, RecordingFrame } from "./RecordingChrome";
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

const STATUS_DOT: Record<RecordingStatus, string> = { new: "bg-ink-muted", reviewed: "bg-ok", flagged: "bg-warning" };

const TITLE_SUGGESTION_KEYS: StructuredFieldKey[] = ["roadType", "targetType", "reaction"];

const rise = (delay: number) => ({ "--d": `${delay}ms` }) as React.CSSProperties;

export default function RecordingDetail({ supervisorName, recording, session, position, total, previousId, nextId, onOpen, onBack, onSaved }: Props) {
  const { draft, phase, change, flush, leave } = useReviewAutosave(recording, onSaved);
  const [menu, setMenu] = useState<{ key: StructuredFieldKey; placement: "up" | "down"; maxHeight: number } | null>(null);

  const control = `w-full rounded-button border border-line bg-white px-4 py-3.5 text-[16px] font-semibold placeholder:font-medium placeholder:text-ink-muted ${focusStyle}`;
  const sessionLabel = session ? `${session.number}회차` : "회차 없음";
  const defaultTitle = recordingTitle({ ...recording, review: undefined });
  const hasCustomTitle = draft.title.trim().length > 0;
  const suggestedTitle = TITLE_SUGGESTION_KEYS.map(key => draft.fields[key]?.trim()).filter(Boolean).join(" ");
  const fieldEntries = Object.entries(FIELD_CONFIG) as [StructuredFieldKey, (typeof FIELD_CONFIG)[StructuredFieldKey]][];
  const otherKeys = fieldEntries.filter(([key, config]) => draft.otherFields?.includes(key) || !config.options.includes(draft.fields[key] ?? ""));

  function openMenu(trigger: HTMLElement, key: StructuredFieldKey, count: number) {
    const rect = trigger.getBoundingClientRect();
    const needed = count * 48 + 12;
    const below = window.innerHeight - rect.bottom - 96;
    const above = rect.top - 56;
    const placement = below >= needed || below >= above ? "down" : "up";
    setMenu({ key, placement, maxHeight: Math.max(160, Math.min(needed, placement === "down" ? below : above)) });
  }

  function closeMenu(focusKey: StructuredFieldKey | null) {
    setMenu(null);
    if (focusKey) setTimeout(() => document.getElementById(`field-button-${focusKey}`)?.focus(), 0);
  }

  function pickOption(key: StructuredFieldKey, options: readonly string[], selection: string) {
    change(current => {
      const previous = current.fields[key] ?? "";
      const wasOther = current.otherFields?.includes(key) || !options.includes(previous);
      // 이전 형식의 기타 값도 첫 전환 시 보존한다. 빈 문자열은 사용자가 지운 값이므로 그대로 유지한다.
      const otherFieldValues = { ...current.otherFieldValues, ...(wasOther ? { [key]: previous } : {}) };
      return {
        ...current,
        fields: { ...current.fields, [key]: selection === "__other__" ? otherFieldValues[key] ?? "" : selection },
        otherFields: selection === "__other__" ? [...(current.otherFields ?? []).filter(field => field !== key), key] : (current.otherFields ?? []).filter(field => field !== key),
        otherFieldValues,
      };
    });
    closeMenu(key);
  }

  return <RecordingFrame tone="white">
    <div className="sticky top-0 z-10 border-b border-line bg-white/90 backdrop-blur">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center pr-2 pl-3">
        <button type="button" onClick={() => void leave(onBack)} aria-label="뒤로가기" className={`flex min-h-11 items-center gap-1.5 justify-self-start rounded-button pr-2 text-[14px] font-bold ${focusStyle}`}><ArrowLeft className="size-5" strokeWidth={2} aria-hidden="true" />뒤로가기</button>
        <h1 className="text-[16px] font-extrabold tracking-tight">녹음 상세</h1>
        <nav aria-label="녹음 이동" className="flex items-center justify-self-end">
          <button type="button" disabled={!previousId} aria-label="이전 녹음" onClick={() => previousId && void leave(() => onOpen(previousId))} className={`flex size-11 items-center justify-center rounded-button disabled:opacity-30 ${focusStyle}`}><ChevronLeft className="size-5" aria-hidden="true" /></button>
          <span className="text-[13px] font-semibold tabular-nums">{position} / {total}</span>
          <button type="button" disabled={!nextId} aria-label="다음 녹음" onClick={() => nextId && void leave(() => onOpen(nextId))} className={`flex size-11 items-center justify-center rounded-button disabled:opacity-30 ${focusStyle}`}><ChevronRight className="size-5" aria-hidden="true" /></button>
        </nav>
      </div>
      <span role="status" className="sr-only">{phase === "saved" ? "자동 저장됨" : phase === "saving" ? "저장 중" : ""}</span>
      {phase === "error" && <div className="fade-in px-5 pb-3"><p role="alert" className="text-[13px] text-danger-ink">입력한 내용은 그대로 있어요. 저장 공간을 확인하고 다시 시도해 주세요. 저장될 때까지 이 화면을 닫지 마세요.</p><Button onClick={() => void flush()} className={`mt-3 w-full ${focusStyle}`}>저장 다시 시도</Button></div>}
    </div>

    <section className="rise border-b-2 border-line bg-surface px-5 pt-6 pb-5" style={rise(0)}>
      <p className="text-[16px] font-bold text-ink-sub tabular-nums" data-start-trigger={recording.startTrigger ?? "none"}>{dateText(recording.recordedAt)} {timeText(recording.recordedAt)}</p>
      <label htmlFor="recording-title" className="sr-only">녹음 제목</label>
      <div className="mt-1 flex items-start gap-2 border-b-2 border-ink/15 pb-2 transition-colors duration-200 focus-within:border-ink">
        <input id="recording-title" name="recording-title" value={draft.title} onChange={event => { const title = event.target.value; change(current => ({ ...current, title })); }} maxLength={120} placeholder={defaultTitle} className="min-w-0 flex-1 bg-transparent text-[34px] leading-[1.2] font-extrabold tracking-tight text-ink outline-none placeholder:text-ink-sub focus-visible:outline-none" />
        <Pencil className="mt-3 size-5 shrink-0 text-ink-muted" strokeWidth={2} aria-hidden="true" />
      </div>
      {!hasCustomTitle && suggestedTitle && <button type="button" onClick={() => change(current => ({ ...current, title: suggestedTitle }))} className={`fade-in mt-3 flex min-h-11 items-center gap-2 rounded-button border border-line bg-white px-3.5 text-left text-[14px] transition-[background-color,scale] duration-150 active:scale-[0.98] active:bg-surface ${focusStyle}`}><span className="shrink-0 font-semibold text-ink-muted">이슈 제목 제안</span><span className="min-w-0 truncate font-extrabold">{suggestedTitle}</span></button>}
      <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-[13px] text-ink-sub">
        {/* TODO(backend): 녹음 좌표를 주소로 변환한 응답으로 교체한다. XX동 XX로는 표시용 임시 주소이며 원본에 저장하지 않는다. */}
        <li title="임시 주소예요. 실제 위치와 연결되지 않았어요." aria-label="주소 XX동 XX로 (임시 주소)" className="flex items-center gap-1.5"><MapPin className="size-3.5 shrink-0" strokeWidth={2} aria-hidden="true" />XX동 XX로</li>
        <li aria-label={`녹음 길이 ${formatTime(recording.durationSec)}`} className="flex items-center gap-1.5 tabular-nums"><Timer className="size-3.5 shrink-0" strokeWidth={2} aria-hidden="true" />{formatTime(recording.durationSec)}</li>
        <li aria-label={`운행 ${sessionLabel}`} className="flex items-center gap-1.5"><Route className="size-3.5 shrink-0" strokeWidth={2} aria-hidden="true" />{sessionLabel}</li>
        <li aria-label={`감독관 ${supervisorName}`} className="flex min-w-0 items-center gap-1.5"><UserRound className="size-3.5 shrink-0" strokeWidth={2} aria-hidden="true" /><span className="truncate">{supervisorName}</span></li>
      </ul>
    </section>

    <div className="flex flex-col gap-9 px-5 pt-8 pb-8">
      <fieldset className="rise" style={rise(60)}>
        <legend className="mb-3 text-[15px] font-extrabold">검토 상태</legend>
        <div className="grid grid-cols-3 gap-2">
          {(Object.entries(STATUS_LABEL) as [RecordingStatus, string][]).map(([value, label]) => <label key={value} className={`relative flex min-h-12 cursor-pointer items-center justify-center gap-1.5 rounded-[8px] border px-1 text-[14px] font-bold transition-[background-color,color,border-color] duration-200 ease-[cubic-bezier(0.32,0.72,0,1)] focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ink ${draft.status === value ? "border-ink bg-ink text-white" : "border-line text-ink-sub"}`}>
            <input type="radio" name="review-status" value={value} checked={draft.status === value} onChange={() => change(current => ({ ...current, status: value }))} className="sr-only" />
            <span aria-hidden="true" className={`size-2 rounded-full ${STATUS_DOT[value]}`} />{label}
          </label>)}
        </div>
      </fieldset>

      <section className={`rise relative ${menu ? "z-30" : ""}`} style={rise(110)}>
        <h2 className="mb-2 flex items-center gap-2 text-[15px] font-extrabold">정리 항목<span className="rounded-full bg-kakao-soft px-2.5 py-0.5 text-[12px] font-bold">시연용 예시</span></h2>
        <fieldset>
          <legend className="sr-only">정리 항목 선택</legend>
          <div className="divide-y divide-line border-y border-line">
            {fieldEntries.map(([key, config]) => {
              const value = draft.fields[key] ?? "";
              const isOther = draft.otherFields?.includes(key) || !config.options.includes(value);
              return <div key={key} className="relative flex min-h-16 items-center justify-between gap-3 py-3 transition-colors duration-150 active:bg-surface">
                <div className="min-w-0">
                  <span className="block text-[14px] font-bold">{config.label}</span>
                  <p id={`hint-${key}`} className="sr-only">{config.description}{key === "previousAction" ? " · 차량 데이터 수집을 가정한 예시" : ""}</p>
                </div>
                <p className="flex shrink-0 items-center gap-1 text-[18px] font-extrabold tracking-tight">
                  <span key={isOther ? "other" : value} className="fade-in max-w-[9em] break-words text-right">{isOther ? (value || "기타") : value}</span>
                  <ChevronDown className={`size-4 shrink-0 text-ink-muted transition-transform duration-150 ${menu?.key === key ? "rotate-180" : ""}`} strokeWidth={2} aria-hidden="true" />
                </p>
                <button type="button" id={`field-button-${key}`} aria-haspopup="menu" aria-expanded={menu?.key === key} aria-label={`${config.label} ${isOther ? (value || "기타") : value}, 변경`} aria-describedby={`hint-${key}`} onClick={event => menu?.key === key ? closeMenu(key) : openMenu(event.currentTarget, key, config.options.length + 1)} className="absolute inset-0 size-full cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink" />
                {menu?.key === key && <OptionMenu label={config.label} options={[...config.options.map(option => ({ value: option, label: option })), { value: "__other__", label: "기타 (직접 입력)" }]} value={isOther ? "__other__" : value} placement={menu.placement} maxHeight={menu.maxHeight} onSelect={selection => pickOption(key, config.options, selection)} onClose={() => closeMenu(key)} />}
              </div>;
            })}
          </div>
          {otherKeys.length > 0 && <div className="mt-4 flex flex-col gap-3">
            {otherKeys.map(([key, config]) => <div key={key}><label htmlFor={`other-${key}`} className="mb-2 block text-[13px] font-bold">{config.label} 기타 내용</label><input id={`other-${key}`} name={`other-${key}`} value={draft.fields[key] ?? ""} maxLength={500} onChange={event => { const text = event.target.value; change(current => ({ ...current, fields: { ...current.fields, [key]: text }, otherFieldValues: { ...current.otherFieldValues, [key]: text } })); }} placeholder="기타 내용을 입력해 주세요" className={control} /></div>)}
          </div>}
        </fieldset>
      </section>

      <section className="rise" style={rise(160)}>
        <label htmlFor="recording-note" className="mb-2 block text-[15px] font-extrabold">메모</label>
        <textarea id="recording-note" name="recording-note" value={draft.note} onChange={event => { const note = event.target.value; change(current => ({ ...current, note })); }} rows={3} maxLength={5000} placeholder="사건 상황이나 확인할 내용을 적어 주세요." className={`${control} resize-y`} />
      </section>

      <div className="rise divide-y divide-line border-y border-line" style={rise(210)}>
        {/* TODO(backend): DEMO_TRANSCRIPT 대신 녹음별 전사 응답을 표시하고 처리 중·실패·미연결 상태를 구분한다. */}
        <RecordingFold title="전사" badge="시연용 예시"><p className="text-[15px]">{DEMO_TRANSCRIPT}</p></RecordingFold>
        <RecordingLocationMap location={recording.location} />
        <RecordingVideo durationSec={recording.durationSec} />
        {/* TODO(backend): 녹음 시각·회차와 연결된 차량 로그(이전 동작·속도·차선·저크 등)를 서버에서 조회해 표시한다. 기기 위치를 차량 GPS로 대체 사용하지 않는다. */}
        <RecordingFold title="차량 데이터" badge="임시 데이터">
          <dl className="divide-y divide-line">
            {DEMO_VEHICLE_DATA.map(({ label, value }) => <div key={label} className="flex items-start justify-between gap-3 py-3">
              <dt className="shrink-0 text-[13px] text-ink-sub">{label}</dt>
              <dd className="min-w-0 text-right text-[14px] font-bold tabular-nums [overflow-wrap:anywhere]"><span className="mr-1 text-[12px] font-normal text-ink-sub">예시</span>{value}</dd>
            </div>)}
          </dl>
        </RecordingFold>
      </div>
    </div>

    <div className="sticky bottom-0 z-10 -mb-[max(24px,env(safe-area-inset-bottom))] border-t-2 border-ink/15 bg-white shadow-dock px-5 pt-2 pb-[max(12px,env(safe-area-inset-bottom))] backdrop-blur">
      <RecordingPlayer compact audio={recording.audio} durationSec={recording.durationSec} />
    </div>
    {menu && <button type="button" tabIndex={-1} aria-hidden="true" onClick={() => closeMenu(menu.key)} className="fixed inset-0 z-20 cursor-default" />}
  </RecordingFrame>;
}
