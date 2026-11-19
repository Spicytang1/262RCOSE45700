import { useState } from "react";
import type { ReactNode } from "react";

type Direction = "fade" | "none" | "forward" | "back";

type Mark = { key: string; depth: number; order: number; direction: Direction };

const CLASS: Record<Direction, string> = { fade: "page-fade", none: "", forward: "page-forward", back: "page-back" };

type Props = {
  pageKey: string;
  depth: number;
  order?: number;
  children: ReactNode;
};

export default function PageTransition({ pageKey, depth, order = 0, children }: Props) {
  const [mark, setMark] = useState<Mark>({ key: pageKey, depth, order, direction: "fade" });

  let direction = mark.direction;
  if (mark.key !== pageKey) {
    direction = depth > mark.depth ? "forward" : depth < mark.depth ? "back" : order >= mark.order ? "forward" : "back";
    setMark({ key: pageKey, depth, order, direction });
  }

  return <div key={pageKey} className={CLASS[direction]}>{children}</div>;
}
