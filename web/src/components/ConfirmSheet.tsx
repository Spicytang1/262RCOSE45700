import { useEffect, useRef } from "react";
import Button from "@/components/Button";

type Props = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmSheet({ title, message, confirmLabel, cancelLabel = "취소", onConfirm, onCancel }: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmRef.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/45 sm:items-center" onClick={onCancel}>
    <div role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-message" onClick={event => event.stopPropagation()} className="w-full max-w-[430px] rounded-t-[28px] bg-white px-5 pt-6 pb-[max(20px,env(safe-area-inset-bottom))] shadow-float sm:rounded-[28px]">
      <h2 id="confirm-title" className="text-[20px] font-extrabold tracking-tight">{title}</h2>
      <p id="confirm-message" className="mt-2 text-[15px] text-ink-sub">{message}</p>
      <div className="mt-6 grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={onCancel}>{cancelLabel}</Button>
        <Button ref={confirmRef} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </div>
  </div>;
}
