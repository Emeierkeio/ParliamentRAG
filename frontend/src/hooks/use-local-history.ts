"use client";

import { useState, useEffect, useCallback } from "react";

export interface LocalHistoryEntry<T> {
  id: string;
  topic: string;
  data: T;
  timestamp: number;
}

export function useLocalHistory<T>(storageKey: string, maxEntries = 15) {
  const [entries, setEntries] = useState<LocalHistoryEntry<T>[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        setEntries(JSON.parse(raw));
      }
    } catch {
      // localStorage unavailable or data corrupted — start fresh
    }
  }, [storageKey]);

  const persist = useCallback(
    (next: LocalHistoryEntry<T>[]) => {
      setEntries(next);
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // Quota exceeded or unavailable — ignore
      }
    },
    [storageKey]
  );

  const addEntry = useCallback(
    (topic: string, data: T) => {
      setEntries((prev) => {
        // Replace existing entry with same topic (case-insensitive)
        const filtered = prev.filter(
          (e) => e.topic.toLowerCase() !== topic.toLowerCase()
        );
        const next: LocalHistoryEntry<T>[] = [
          { id: crypto.randomUUID(), topic, data, timestamp: Date.now() },
          ...filtered,
        ].slice(0, maxEntries);
        try {
          localStorage.setItem(storageKey, JSON.stringify(next));
        } catch {
          // Ignore
        }
        return next;
      });
    },
    [storageKey, maxEntries]
  );

  const removeEntry = useCallback(
    (id: string) => {
      setEntries((prev) => {
        const next = prev.filter((e) => e.id !== id);
        persist(next);
        return next;
      });
    },
    [persist]
  );

  return { entries, addEntry, removeEntry };
}
