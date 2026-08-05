"use client";

import { useEffect, useLayoutEffect, useState } from "react";

/**
 * Date of the last `make update-data` run, from /api/config/last-update
 * (SchemaMeta.updated_at in Neo4j).
 *
 * Render order: static fallback (first-ever visit only) -> localStorage cache
 * of the last fetched value (seeded pre-paint, shared across tabs and
 * sessions) -> live fetch. The cache is read in useLayoutEffect rather than
 * in the useState initializer to avoid an SSR hydration mismatch.
 * The fallback snapshot is from the build of 2026-08-04.
 */
const LAST_UPDATE_FALLBACK = "2026-08-04";
const CACHE_KEY = "lastUpdateIso";

export function useLastUpdate(): string {
  const [iso, setIso] = useState<string>(LAST_UPDATE_FALLBACK);

  useLayoutEffect(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) setIso(cached);
    } catch {}
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/config/last-update")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        const fresh: string | undefined = data?.last_update;
        if (cancelled || !fresh) return;
        try {
          localStorage.setItem(CACHE_KEY, fresh);
        } catch {}
        setIso((prev) => (prev === fresh ? prev : fresh));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return iso;
}

/** DD/MM/YYYY, the compact format used by the sidebar/nav footers. */
export function formatLastUpdateShort(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}
