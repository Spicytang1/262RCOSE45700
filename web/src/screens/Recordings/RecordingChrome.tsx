import type { ReactNode } from "react";
import { ChevronLeft, Minus, Plus } from "lucide-react";
import { focusStyle } from "@/lib/recordingPresentation";

export function RecordingFrame({ children, tone = "surface" }: { children: ReactNode; tone?: "surface" | "white" }) {
  return <main className={`app-frame mx-auto min-h-dvh w-full max-w-[430px] touch-manipulation pb-[max(24px,env(safe-area-inset-bottom))] leading-[1.7] ${tone === "white" ? "bg-white" : "bg-surface"}`}>{children}</main>;
}

export function RecordingHeader({ title, backLabel, onBack }: { title: string; backLabel: string; onBack: () => void }) {
  return <header className="flex items-center gap-3 border-b border-line bg-white px-4 py-4">
    <button type="button" onClick={onBack} aria-label={backLabel} className={`flex min-h-11 shrink-0 items-center rounded-button bg-surface pr-3 pl-1 text-[13px] font-bold ${focusStyle}`}><ChevronLeft className="size-5" aria-hidden="true" />{backLabel}</button>
    <h1 className="text-[21px] font-extrabold tracking-tight">{title}</h1>
  </header>;
}

export function RecordingPanel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-[20px] border border-line bg-white p-5"><h2 className="mb-3 text-[16px] font-extrabold">{title}</h2>{children}</section>;
}

export function RecordingFold({ title, badge, onOpen, children }: { title: string; badge?: string; onOpen?: () => void; children: ReactNode }) {
  return <details onToggle={event => { if (event.currentTarget.open) onOpen?.(); }} className="group">
    <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 py-3 [&::-webkit-details-marker]:hidden focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-ink">
      <span className="flex min-w-0 items-center gap-2 text-[16px] font-extrabold">{title}{badge && <span className="shrink-0 rounded-full bg-kakao-soft px-2.5 py-0.5 text-[12px] font-bold">{badge}</span>}</span>
      <Plus className="size-5 shrink-0 text-ink-sub group-open:hidden" strokeWidth={2} aria-hidden="true" />
      <Minus className="hidden size-5 shrink-0 text-ink-sub group-open:block" strokeWidth={2} aria-hidden="true" />
    </summary>
    <div className="pb-5">{children}</div>
  </details>;
}
