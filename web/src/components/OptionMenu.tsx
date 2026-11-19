import { useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";
import { Check } from "lucide-react";

type Option = { value: string; label: string };

type Props = {
  label: string;
  options: Option[];
  value: string;
  placement: "up" | "down";
  maxHeight: number;
  onSelect: (value: string) => void;
  onClose: () => void;
};

export default function OptionMenu({ label, options, value, placement, maxHeight, onSelect, onClose }: Props) {
  const selectedRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef(onClose);

  useEffect(() => { closeRef.current = onClose; });

  useEffect(() => {
    selectedRef.current?.focus();
    const onKey = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") closeRef.current(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function moveFocus(event: KeyboardEvent<HTMLUListElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
    const index = items.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "ArrowDown" ? (index + 1) % items.length : (index - 1 + items.length) % items.length;
    items[next]?.focus();
  }

  return <ul role="menu" aria-label={label} onKeyDown={moveFocus} style={{ maxHeight }} className={`menu-in absolute right-0 z-30 w-max min-w-[9rem] max-w-[calc(100vw-2.5rem)] overflow-y-auto rounded-[12px] border border-line bg-white p-1 shadow-menu ${placement === "down" ? "top-full mt-1 origin-top-right" : "bottom-full mb-1 origin-bottom-right"}`}>
    {options.map(option => {
      const selected = option.value === value;
      return <li key={option.value} role="none">
        <button type="button" role="menuitemradio" aria-checked={selected} ref={selected ? selectedRef : undefined} onClick={() => onSelect(option.value)} className={`flex min-h-12 w-full items-center justify-between gap-6 rounded-[8px] px-3 text-left text-[16px] whitespace-nowrap transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink ${selected ? "bg-kakao-soft font-extrabold" : "font-semibold active:bg-surface"}`}>
          <span>{option.label}</span>
          {selected ? <Check className="size-4 shrink-0" strokeWidth={2.6} aria-hidden="true" /> : <span className="size-4 shrink-0" aria-hidden="true" />}
        </button>
      </li>;
    })}
  </ul>;
}
