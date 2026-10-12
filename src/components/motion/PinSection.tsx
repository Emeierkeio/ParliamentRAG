"use client";

import { createContext, useContext, useRef, type ReactNode } from "react";
import { motion, useScroll, useTransform, type MotionValue } from "motion/react";
import { easeInOut, easeOut } from "./tokens";

const Progress = createContext<MotionValue<number> | null>(null);

/**
 * A section taller than the viewport whose content stays pinned while the
 * scroll drives one progress value from 0 to 1 (offset start start → end end).
 * `screens` is the scroll length in viewport heights. Children read the
 * progress with usePinProgress or place themselves with PinStep.
 */
export function PinSection({
  screens,
  children,
  className,
  ...rest
}: {
  screens: number;
  children: ReactNode;
  className?: string;
} & React.HTMLAttributes<HTMLElement>) {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  return (
    <section ref={ref} className={className} style={{ height: `${screens * 100}svh` }} {...rest}>
      <div className="sticky top-[var(--header-h)] h-[calc(100svh-var(--header-h))] overflow-hidden">
        <Progress.Provider value={scrollYProgress}>{children}</Progress.Provider>
      </div>
    </section>
  );
}

export function usePinProgress() {
  const p = useContext(Progress);
  if (!p) throw new Error("usePinProgress outside PinSection");
  return p;
}

/**
 * One step of a pinned scene: enters over [enter, enter + 0.07] (rise 48px,
 * unblur 10px), holds, and leaves over [exit, exit + 0.05] upward. Omit exit
 * for the last step. The hold between the two is the scene's pause: the
 * reference blocks the wheel there, we only give it scroll length.
 */
export function PinStep({
  enter,
  exit,
  children,
  className,
}: {
  enter: number;
  exit?: number;
  children: ReactNode;
  className?: string;
}) {
  const p = usePinProgress();
  const inEnd = enter + 0.07;
  const outEnd = (exit ?? 2) + 0.05;
  const range = exit === undefined ? [enter, inEnd] : [enter, inEnd, exit, outEnd];
  const opacity = useTransform(p, range, exit === undefined ? [0, 1] : [0, 1, 1, 0], { ease: [easeOut, easeOut, easeInOut] });
  const y = useTransform(p, range, exit === undefined ? [48, 0] : [48, 0, 0, -26], { ease: [easeOut, easeOut, easeInOut] });
  const blurPx = useTransform(p, range, exit === undefined ? [10, 0] : [10, 0, 0, 7]);
  const filter = useTransform(blurPx, (b) => (b < 0.05 ? "none" : `blur(${b}px)`));
  const visibility = useTransform(opacity, (o) => (o < 0.01 ? "hidden" : "visible"));
  return (
    <motion.div className={className} style={{ opacity, y, filter, visibility }}>
      {children}
    </motion.div>
  );
}
