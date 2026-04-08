"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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

  return (
    <div className="space-y-3" role="search" aria-label={t("pageTitle")}>
      {/* Keyword search row */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <Input
          type="text"
          placeholder={t("searchPlaceholder")}
          value={filters.search}
          onChange={(e) => onFiltersChange({ search: e.target.value })}
          className="pl-9 pr-9"
          aria-label={t("searchPlaceholder")}
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onFiltersChange({ search: "" })}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Preset buttons row */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={activePreset === "week" ? "secondary" : "outline"}
          size="sm"
          onClick={() => applyPreset("week", 7)}
          aria-pressed={activePreset === "week"}
        >
          {t("lastWeek")}
        </Button>
        <Button
          variant={activePreset === "month" ? "secondary" : "outline"}
          size="sm"
          onClick={() => applyPreset("month", 30)}
          aria-pressed={activePreset === "month"}
        >
          {t("lastMonth")}
        </Button>
        <Button
          variant={activePreset === "3months" ? "secondary" : "outline"}
          size="sm"
          onClick={() => applyPreset("3months", 90)}
          aria-pressed={activePreset === "3months"}
        >
          {t("last3Months")}
        </Button>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={handleClear}>
            {t("clearFilters")}
          </Button>
        )}
      </div>

      {/* Date range row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground whitespace-nowrap">
            {t("dateFrom")}
          </label>
          <input
            type="date"
            value={filters.fromDate}
            onChange={(e) => handleFromDate(e.target.value)}
            className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:border-ring"
            aria-label={t("dateFrom")}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground whitespace-nowrap">
            {t("dateTo")}
          </label>
          <input
            type="date"
            value={filters.toDate}
            onChange={(e) => handleToDate(e.target.value)}
            className="h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:border-ring"
            aria-label={t("dateTo")}
          />
        </div>
      </div>

      {/* Screen reader announcement region */}
      <div aria-live="polite" className="sr-only" />
    </div>
  );
}
