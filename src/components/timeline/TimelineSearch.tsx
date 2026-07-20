"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Search, X, Calendar } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { TimelineFilters } from "@/types/timeline";

interface TimelineSearchProps {
  filters: TimelineFilters;
  onFiltersChange: (partial: Partial<TimelineFilters>) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
}

type Preset = "week" | "month" | "3months" | null;

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function TimelineSearch({
  filters,
  onFiltersChange,
  onClear,
  hasActiveFilters,
}: TimelineSearchProps) {
  const t = useTranslations("Timeline");
  const [activePreset, setActivePreset] = useState<Preset>(null);

  const applyPreset = useCallback(
    (preset: Preset, days: number) => {
      const today = new Date();
      const from = new Date(today);
      from.setDate(today.getDate() - days);
      setActivePreset(preset);
      onFiltersChange({ fromDate: toISODate(from), toDate: toISODate(today) });
    },
    [onFiltersChange],
  );

  const handleFromDate = useCallback(
    (value: string) => {
      setActivePreset(null);
      onFiltersChange({ fromDate: value });
    },
    [onFiltersChange],
  );

  const handleToDate = useCallback(
    (value: string) => {
      setActivePreset(null);
      onFiltersChange({ toDate: value });
    },
    [onFiltersChange],
  );

  const handleClear = useCallback(() => {
    setActivePreset(null);
    onClear();
  }, [onClear]);

  const presets: { key: Preset; days: number; label: string }[] = [
    { key: "week", days: 7, label: t("lastWeek") },
    { key: "month", days: 30, label: t("lastMonth") },
    { key: "3months", days: 90, label: t("last3Months") },
  ];

  return (
    <div className="space-y-2.5" role="search" aria-label={t("pageTitle")}>
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60 pointer-events-none" />
        <Input
          type="text"
          placeholder={t("searchPlaceholder")}
          value={filters.search}
          onChange={(e) => onFiltersChange({ search: e.target.value })}
          className="pl-9 pr-9 h-10"
          aria-label={t("searchPlaceholder")}
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onFiltersChange({ search: "" })}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Presets + date range in a single row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Preset segmented control */}
        <div className="inline-flex rounded-lg border p-0.5 bg-card shadow-sm">
          {presets.map(({ key, days, label }) => (
            <button
              key={key}
              onClick={() => applyPreset(key, days)}
              aria-pressed={activePreset === key}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                activePreset === key
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Separator */}
        <div className="w-px h-5 bg-border mx-1 hidden sm:block" />

        {/* Compact date range */}
        <div className="flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5 text-muted-foreground/60 shrink-0 hidden sm:block" />
          <input
            type="date"
            value={filters.fromDate}
            onChange={(e) => handleFromDate(e.target.value)}
            className="h-8 rounded-md border border-border bg-background px-2.5 text-xs text-foreground focus:ring-1 focus:ring-ring/50 transition-colors outline-none"
            aria-label={t("dateFrom")}
          />
          <span className="text-[10px] text-muted-foreground/50">—</span>
          <input
            type="date"
            value={filters.toDate}
            onChange={(e) => handleToDate(e.target.value)}
            className="h-8 rounded-md border border-border bg-background px-2.5 text-xs text-foreground focus:ring-1 focus:ring-ring/50 transition-colors outline-none"
            aria-label={t("dateTo")}
          />
        </div>

        {/* Clear all */}
        {hasActiveFilters && (
          <button
            onClick={handleClear}
            className="h-8 px-3 rounded-md text-xs font-medium text-destructive/80 hover:text-destructive hover:bg-destructive/10 transition-colors ml-auto"
          >
            {t("clearFilters")}
          </button>
        )}
      </div>

      <div aria-live="polite" className="sr-only" />
    </div>
  );
}
