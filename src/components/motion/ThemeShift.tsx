"use client";

import { useRef, type ReactNode } from "react";
import { useMotionValueEvent, useScroll } from "motion/react";

/**
 * Turns the page dark as the section comes in: the background mixes from the
 * page colour (--page-bg, fixed on :root) to the dark --bg over the scroll
 * window start 95% → start 35%. The content is in the dark theme from the
 * start; [data-shift-reveal] children fade, rise and unblur on the same value
 * (globals.css), so light text never sits on a light ground. --shift defaults
 * to 1, so without JS or with reduced motion the section is simply dark.
 * In the dark theme --page-bg already equals --bg and nothing changes.
 */
export function ThemeShift({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 95%", "start 35%"] });
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    ref.current?.style.setProperty("--shift", v.toFixed(3));
  });
  return (
    <div ref={ref} data-theme="dark" className={`theme-shift ${className ?? ""}`}>
      {children}
    </div>
  );
}
