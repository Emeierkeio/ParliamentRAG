/*
 * Entrance animations driven by data attributes, so any section can opt in
 * without wrapping its markup in motion components:
 *
 *   data-reveal                  fade, rise and unblur the element
 *   data-reveal="words"          animate its .rv-word children (see SplitWords)
 *   data-reveal="group"          animate its [data-reveal-item] children in turn
 *   data-reveal-delay="0.2"      seconds
 *   data-reveal-y="28"           rise distance in px
 *   data-reveal-blur="10"        starting blur in px, 0 for none
 *   data-reveal-amount="0.3"     share of the element in view before it starts
 *
 * The content is in the HTML at its final state. The hidden starting state
 * lives in globals.css under html.motion-ready, a class set before first paint
 * by MOTION_READY_SCRIPT (ready-script.ts); without JS, or with reduced motion, nothing is hidden.
 */
import { animate, stagger, type AnimationPlaybackControls } from "motion";
import { EASE_OUT, REVEAL, WORDS, prefersReducedMotion } from "./tokens";

function num(el: HTMLElement, key: string, fallback: number) {
  const v = el.dataset[key];
  return v === undefined || v === "" ? fallback : Number(v);
}

function play(el: HTMLElement): AnimationPlaybackControls {
  const kind = el.dataset.reveal;
  const delay = num(el, "revealDelay", 0);
  const blur = num(el, "revealBlur", kind === "words" ? WORDS.blur : REVEAL.blur);
  const done = () => {
    el.dataset.revealed = "";
  };

  if (kind === "words") {
    const words = el.querySelectorAll<HTMLElement>(".rv-word");
    const controls = animate(
      words,
      { y: ["115%", "0%"], opacity: [0, 1], filter: [`blur(${blur}px)`, "blur(0px)"] },
      { duration: WORDS.duration, delay: stagger(WORDS.stagger, { startDelay: delay }), ease: EASE_OUT },
    );
    controls.then(done);
    return controls;
  }

  const y = num(el, "revealY", REVEAL.y);
  const keyframes = { opacity: [0, 1], y: [y, 0], filter: [`blur(${blur}px)`, "blur(0px)"] };
  if (kind === "group") {
    const items = el.querySelectorAll<HTMLElement>("[data-reveal-item]");
    const controls = animate(items, keyframes, {
      duration: REVEAL.duration,
      delay: stagger(REVEAL.stagger, { startDelay: delay }),
      ease: EASE_OUT,
    });
    controls.then(done);
    return controls;
  }
  const controls = animate(el, keyframes, { duration: REVEAL.duration, delay, ease: EASE_OUT });
  controls.then(done);
  return controls;
}

/**
 * Observes every [data-reveal] under root and plays each once on entry.
 * Returns the cleanup for unmount or route change.
 */
export function startReveals(root: ParentNode = document): () => void {
  (window as unknown as { __revealStarted?: boolean }).__revealStarted = true;
  const pending = () => Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]:not([data-revealed]):not([data-reveal-watched])"));
  if (prefersReducedMotion()) {
    pending().forEach((el) => (el.dataset.revealed = ""));
    return () => {};
  }

  const running: AnimationPlaybackControls[] = [];
  // One observer per threshold in use.
  const observers = new Map<number, IntersectionObserver>();
  const watch = (el: HTMLElement) => {
    el.dataset.revealWatched = "";
    const amount = num(el, "revealAmount", REVEAL.amount);
    let io = observers.get(amount);
    if (!io) {
      io = new IntersectionObserver(
        (entries, obs) => {
          for (const e of entries) {
            if (!e.isIntersecting) continue;
            obs.unobserve(e.target);
            running.push(play(e.target as HTMLElement));
          }
        },
        { threshold: amount },
      );
      observers.set(amount, io);
    }
    io.observe(el);
  };
  pending().forEach(watch);
  // Sections mounted later (the wide-screen scenes) bring their own targets.
  const mo = new MutationObserver(() => pending().forEach(watch));
  mo.observe(root, { childList: true, subtree: true });
  return () => {
    mo.disconnect();
    root.querySelectorAll<HTMLElement>("[data-reveal-watched]").forEach((el) => delete el.dataset.revealWatched);
    observers.forEach((io) => io.disconnect());
    running.forEach((c) => c.stop());
  };
}
