"use client";

import { useEffect, useLayoutEffect, useState } from "react";

/**
 * Live knowledge-graph counts from /api/data/stats.
 *
 * Render order: static fallback (first-ever visit only) -> localStorage cache
 * of the last fetched values (seeded pre-paint, so refreshes don't flash a
 * stale number) -> live fetch. The cache is read in useLayoutEffect rather
 * than in the useState initializer to avoid an SSR hydration mismatch.
 * The fallback snapshot is from the build of 2026-07-26.
 */
export type KgStats = {
  people: number;
  speeches: number;
  sessions: number;
  acts: number;
  votes: number;
  individual_votes: number;
  eurovoc_concepts: number;
  chunks: number;
  triples: number | null;
  last_update: string | null;
};

export const KG_STATS_FALLBACK: KgStats = {
  people: 455,
  speeches: 45907,
  sessions: 697,
  acts: 32976,
  votes: 16787,
  individual_votes: 6305481,
  eurovoc_concepts: 1716,
  chunks: 171624,
  triples: 863834,
  last_update: null,
};

const CACHE_KEY = "kgStatsCache";

export function useKgStats(): KgStats {
  const [stats, setStats] = useState<KgStats>(KG_STATS_FALLBACK);

  useLayoutEffect(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) setStats({ ...KG_STATS_FALLBACK, ...JSON.parse(cached) });
    } catch {}
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/data/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data?.people) return;
        const fresh = {
          ...KG_STATS_FALLBACK,
          ...data,
          triples: data.triples ?? KG_STATS_FALLBACK.triples,
        };
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify(fresh));
        } catch {}
        setStats(fresh);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return stats;
}
