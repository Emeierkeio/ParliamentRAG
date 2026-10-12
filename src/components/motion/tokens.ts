/*
 * Motion vocabulary of the research site, measured on the reference
 * (docs/motion-spec-goversa.md §2). Entrances decelerate hard (expo-out),
 * exits and scene changes use the symmetric in-out curve.
 */
import { cubicBezier } from "motion";

export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const EASE_IN_OUT = [0.76, 0, 0.24, 1] as const;

export const easeOut = cubicBezier(...EASE_OUT);
export const easeInOut = cubicBezier(...EASE_IN_OUT);

/** Default entrance: rise, unblur, fade. */
export const REVEAL = {
  duration: 0.62,
  y: 24,
  blur: 8,
  amount: 0.18,
  stagger: 0.08,
} as const;

/** Word-by-word headline: each word rises inside its own mask. */
export const WORDS = {
  duration: 0.82,
  stagger: 0.045,
  blur: 6,
} as const;

export function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
