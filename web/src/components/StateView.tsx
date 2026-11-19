import type { ReactNode } from "react";
import { AlertCircle, Inbox } from "lucide-react";
import Button from "@/components/Button";

type Props =
  | { kind: "loading"; message: string }
  | { kind: "error"; message: string; onRetry?: () => void; retryLabel?: string }
  | { kind: "empty"; title: string; message: string; action?: ReactNode };

export default function StateView(props: Props) {
  if (props.kind === "loading") {
    return <div role="status" className="fade-in flex flex-col items-center gap-4 py-14 text-center">
      <span aria-hidden="true" className="size-9 animate-spin rounded-full border-[3px] border-line border-t-ink motion-reduce:animate-none" />
      <p className="text-[14px] text-ink-sub">{props.message}</p>
    </div>;
  }
  if (props.kind === "error") {
    return <div role="alert" className="fade-in flex flex-col items-center gap-3 rounded-[20px] border border-line bg-white px-6 py-8 text-center shadow-card">
      <span className="flex size-12 items-center justify-center rounded-full bg-warning-soft text-warning-ink"><AlertCircle className="size-6" aria-hidden="true" /></span>
      <p className="text-[15px] font-bold">{props.message}</p>
      {props.onRetry && <Button onClick={props.onRetry} className="mt-1 h-12 px-6 text-[15px]">{props.retryLabel ?? "다시 불러오기"}</Button>}
    </div>;
  }
  return <section className="fade-in flex flex-col items-center gap-2 rounded-[20px] border border-line bg-white px-6 py-10 text-center shadow-card">
    <span className="mb-1 flex size-12 items-center justify-center rounded-full bg-surface text-ink-sub"><Inbox className="size-6" aria-hidden="true" /></span>
    <h2 className="text-[16px] font-extrabold">{props.title}</h2>
    <p className="text-[14px] text-ink-sub">{props.message}</p>
    {props.action && <div className="mt-3">{props.action}</div>}
  </section>;
}
