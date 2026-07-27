"use client";

import { useState, useEffect, useRef, useCallback } from 'react';
import type { TimelineSession, TimelineFilters } from '@/types/timeline';
import { getTimelineSessions } from '@/lib/timeline-api';

interface UseTimelineOptions {
  scrollContainerRef?: React.RefObject<HTMLElement | null>;
}

interface UseTimelineReturn {
  sessions: TimelineSession[];
  isLoading: boolean;
  isFetchingMore: boolean;
  hasMore: boolean;
  error: string | null;
  filters: TimelineFilters;
  setFilters: (filters: Partial<TimelineFilters>) => void;
  loadMoreRef: React.RefObject<HTMLDivElement | null>;
  resultCount: number;
  clearFilters: () => void;
  hasActiveFilters: boolean;
}

// The page opens on the last month of sessions, not the whole legislature:
// the recent ones are what people come for, and the full list stays a
// date-filter edit away. Same window (and same date math) as the "last
// month" preset chip in TimelineSearch, so that chip lights up on load.
function makeDefaultFilters(): TimelineFilters {
  const today = new Date();
  const from = new Date(today);
  from.setDate(today.getDate() - 30);
  return {
    chamber: 'both',
    search: '',
    fromDate: from.toISOString().slice(0, 10),
    toDate: today.toISOString().slice(0, 10),
  };
}

export function useTimeline(options?: UseTimelineOptions): UseTimelineReturn {
  const [sessions, setSessions] = useState<TimelineSession[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<TimelineFilters>(makeDefaultFilters);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Fetch sessions (initial or paginated)
  const fetchSessions = useCallback(
    async (currentCursor: string | null, append: boolean) => {
      if (append) setIsFetchingMore(true);
      else setIsLoading(true);

      try {
        const data = await getTimelineSessions({
          before: currentCursor ?? undefined,
          chamber: filters.chamber,
          search: filters.search || undefined,
          fromDate: filters.fromDate || undefined,
          toDate: filters.toDate || undefined,
        });
        if (append) {
          setSessions(prev => [...prev, ...data.sessions]);
        } else {
          setSessions(data.sessions);
        }
        setCursor(data.next_cursor);
        setHasMore(data.has_more);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load sessions');
      } finally {
        setIsLoading(false);
        setIsFetchingMore(false);
      }
    },
    [filters],
  );

  // Initial fetch on mount and when filters change (debounced for search)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(
      () => {
        setSessions([]);
        setCursor(null);
        setHasMore(true);
        fetchSessions(null, false);
      },
      filters.search ? 300 : 0, // 300ms debounce for search only
    );

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [filters, fetchSessions]);

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting && hasMore && !isFetchingMore && !isLoading) {
          fetchSessions(cursor, true);
        }
      },
      { threshold: 0.1, root: options?.scrollContainerRef?.current ?? null },
    );

    const el = loadMoreRef.current;
    if (el) observer.observe(el);
    return () => {
      if (el) observer.unobserve(el);
      observer.disconnect();
    };
  }, [hasMore, isFetchingMore, isLoading, cursor, fetchSessions]);

  const setFilters = useCallback((partial: Partial<TimelineFilters>) => {
    setFiltersState(prev => ({ ...prev, ...partial }));
  }, []);

  const clearFilters = useCallback(() => {
    setFiltersState(makeDefaultFilters());
  }, []);

  const defaults = makeDefaultFilters();
  const hasActiveFilters =
    filters.chamber !== defaults.chamber ||
    filters.search !== '' ||
    filters.fromDate !== defaults.fromDate ||
    filters.toDate !== defaults.toDate;

  return {
    sessions,
    isLoading,
    isFetchingMore,
    hasMore,
    error,
    filters,
    setFilters,
    loadMoreRef,
    resultCount: sessions.length,
    clearFilters,
    hasActiveFilters,
  };
}
