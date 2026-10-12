import { useSyncExternalStore } from "react";

/** False on the server and on the first client render, then the live match. */
export function useMediaQuery(query: string) {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** Scroll-linked scenes run only on wide screens with motion allowed. */
export const SCENE_QUERY = "(min-width: 64rem) and (prefers-reduced-motion: no-preference)";
