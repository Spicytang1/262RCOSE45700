import type { ButtonHTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";

type Variant = "primary" | "secondary" | "ghost" | "ghostDark";

const VARIANT_CLASS: Record<Variant, string> = {
  // 카카오 옐로 + 검정 글씨 (카카오 버튼 기본 조합)
  primary:
    "bg-kakao text-ink/90 active:bg-kakao-press",
  secondary: "bg-surface text-ink-sub active:bg-line",
  ghost: "bg-transparent text-ink-muted active:bg-surface",
  ghostDark: "bg-transparent text-white/60 active:bg-white/10",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
};

// 비활성 색은 화면 배경(밝음/어두움)에 따라 달라서 사용하는 쪽에서 disabled: 클래스로 지정한다

export default function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={twMerge(
        "inline-flex h-14 items-center justify-center gap-2 rounded-button px-5 text-[17px] font-bold transition-colors active:scale-[0.99] disabled:cursor-not-allowed",
        VARIANT_CLASS[variant],
        className,
      )}
      {...rest}
    />
  );
}
