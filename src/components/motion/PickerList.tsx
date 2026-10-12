"use client";

import { useRef, type ReactNode } from "react";
import { motion, useMotionValueEvent, useScroll, useTransform } from "motion/react";

const STEP_PX = 150;

/**
 * A list read like a picker wheel: the section pins for (n − 1) × 150px of
 * scroll, the list slides so one row at a time sits on the centre line, and
 * the others fade (1 − 0.25 per row, floor 0.07) and shrink (1 − 0.018 per
 * row, floor 0.92). `aside` stays still on the left. Rows are plain DOM
 * content: without the scene (phones, reduced motion) they render as a list.
 */
export function PickerList({
  rows,
  aside,
  rowHeight = 76,
  className,
  ...rest
}: {
  rows: ReactNode[];
  aside: ReactNode;
  rowHeight?: number;
  className?: string;
} & React.HTMLAttributes<HTMLElement>) {
  const ref = useRef<HTMLElement>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const n = rows.length;
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const index = useTransform(scrollYProgress, [0, 1], [0, n - 1]);
  const y = useTransform(index, (i) => -(i + 0.5) * rowHeight);

  useMotionValueEvent(index, "change", (active) => {
    const items = listRef.current?.children;
    if (!items) return;
    for (let k = 0; k < items.length; k++) {
      const d = Math.abs(k - active);
      const el = items[k] as HTMLElement;
      el.style.opacity = String(Math.max(0.07, 1 - d * 0.25));
      el.style.transform = `scale(${Math.max(0.92, 1 - d * 0.018)})`;
    }
  });

  return (
    <section ref={ref} className={className} style={{ height: `calc(100svh + ${(n - 1) * STEP_PX}px)` }} {...rest}>
      <div className="container-page sticky top-[var(--header-h)] grid h-[calc(100svh-var(--header-h))] grid-cols-12 items-center gap-12">
        <div className="col-span-5">{aside}</div>
        <div className="relative col-span-7 h-full overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_22%,black_78%,transparent)]">
          <motion.ol ref={listRef} className="absolute inset-x-0 top-1/2" style={{ y }}>
            {rows.map((r, k) => (
              <li key={k} className="flex origin-left items-center will-change-transform" style={{ height: rowHeight, opacity: k === 0 ? 1 : 0.07 }}>
                {r}
              </li>
            ))}
          </motion.ol>
        </div>
      </div>
    </section>
  );
}
