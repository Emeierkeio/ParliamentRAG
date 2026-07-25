"use client";

import { useEffect, useState } from "react";

/**
 * Live knowledge-graph counts from /api/data/stats, with a static fallback
 * so the pages render meaningful numbers even when the backend is down.
 * The fallback snapshot is from the build of 2026-07-22.
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
  speeches: 45666,
  sessions: 694,
  acts: 32855,
  votes: 16787,
  individual_votes: 6305481,
  eurovoc_concepts: 1714,
  chunks: 170922,
  triples: 863834,
  last_update: null,
};

export function useKgStats(): KgStats {
  const [stats, setStats] = useState<KgStats>(KG_STATS_FALLBACK);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/data/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data?.people) return;
        setStats({
          ...KG_STATS_FALLBACK,
          ...data,
          triples: data.triples ?? KG_STATS_FALLBACK.triples,
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return stats;
}
