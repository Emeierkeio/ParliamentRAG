"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Image from "next/image";
import { useTranslations } from "next-intl";

/* The backend sleeps on Railway when idle (deploy.sleepApplication): the
   first request after a pause holds until the container is back up, which
   can take several seconds. This gate probes /api/health on document load
   and covers the app with a splash-style screen — same cream background
   and emiciclo logo as the iOS startup images — until the backend answers.

   Routes that render without backend data are never gated. An awake
   backend answers the probe within the grace window, so the overlay
   never flashes on regular visits. */

const EXCLUDED_ROUTES = ["/", "/privacy"];

/** An awake backend answers well within this: show nothing until it expires. */
const GRACE_MS = 700;
/** Fail open: never brick the app if the probe keeps failing. */
const MAX_WAIT_MS = 90_000;
const RETRY_MS = 2_500;
const FADE_MS = 500;

export function BackendWakeGate() {
  const pathname = usePathname();
  const t = useTranslations("WakeGate");
  const [phase, setPhase] = useState<"probing" | "waking" | "done">("probing");
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (EXCLUDED_ROUTES.includes(pathname)) {
      setPhase("done");
      return;
    }
    let cancelled = false;
    const start = Date.now();
    const graceTimer = setTimeout(
      () => setPhase((p) => (p === "probing" ? "waking" : p)),
      GRACE_MS
    );

    const probe = async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        return res.ok;
      } catch {
        return false;
      }
    };

    (async () => {
      while (!cancelled) {
        if (await probe()) break;
        if (Date.now() - start > MAX_WAIT_MS) break;
        await new Promise((r) => setTimeout(r, RETRY_MS));
      }
      if (cancelled) return;
      clearTimeout(graceTimer);
      setLeaving(true);
      setTimeout(() => setPhase("done"), FADE_MS);
    })();

    return () => {
      cancelled = true;
      clearTimeout(graceTimer);
    };
    // Probe once per document load: client-side navigations keep this
    // mounted, and traffic from an open tab keeps the backend awake.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (phase !== "waking") return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-0 z-[999] flex flex-col items-center justify-center gap-10 bg-background transition-opacity duration-500 ${
        leaving ? "opacity-0" : "opacity-100"
      }`}
    >
      {/* Same indeterminate top line as the landing CTA, slowed to match
          a cold start that can take up to ~15s */}
      <div className="fixed inset-x-0 top-0 h-0.5" aria-hidden>
        <div className="h-full w-full bg-primary origin-left motion-safe:animate-[nav-progress_14s_cubic-bezier(0.15,0.6,0.3,1)_forwards]" />
      </div>

      <Image
        src="/logo-blue.svg"
        alt=""
        width={118}
        height={82}
        priority
        className="motion-safe:animate-[pulse_2.2s_ease-in-out_infinite]"
      />

      <div className="flex flex-col items-center gap-2 px-8 text-center">
        <span className="[font-family:var(--font-display)] text-xl font-semibold tracking-tight">
          ParliamentRAG
        </span>
        <p className="text-sm text-muted-foreground">{t("waking")}</p>
        <p className="text-xs text-muted-foreground/60">{t("hint")}</p>
      </div>
    </div>
  );
}
