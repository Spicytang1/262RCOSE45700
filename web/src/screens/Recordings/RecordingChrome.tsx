import type { ReactNode } from "react";
import { ChevronLeft } from "lucide-react";
import { focusStyle } from "@/lib/recordingPresentation";

export function RecordingFrame({ children }: { children: ReactNode }) {
  return <main className="app-frame mx-auto min-h-dvh w-full max-w-[430px] touch-manipulation bg-surface pb-[max(24px,env(safe-area-inset-bottom))] leading-[1.7]">{children}</main>;
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
