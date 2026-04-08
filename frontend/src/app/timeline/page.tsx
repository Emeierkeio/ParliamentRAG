"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Loader2, ArrowUp, CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { ChamberSelector } from "@/components/chat/ChamberSelector";
import { SessionCard } from "@/components/timeline/SessionCard";
import { TimelineSearch } from "@/components/timeline/TimelineSearch";
import { TimelineSkeleton } from "@/components/timeline/TimelineSkeleton";
import { useTimeline } from "@/hooks/use-timeline";

export default function TimelinePage() {
  const t = useTranslations("Timeline");
  const {
    sessions,
    isLoading,
    isFetchingMore,
    hasMore,
    error,
    filters,
    setFilters,
    loadMoreRef,
    resultCount,
    clearFilters,
    hasActiveFilters,
  } = useTimeline();

  // Back to top button visibility
  const [showBackToTop, setShowBackToTop] = useState(false);
  useEffect(() => {
    const handleScroll = () => setShowBackToTop(window.scrollY > 400);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="flex-1 min-h-screen bg-background">
      {/* Sticky top bar */}
      <div className="sticky top-0 z-10 bg-background border-b px-6 py-4 space-y-3">
        <h1 className="text-xl font-semibold">{t("pageTitle")}</h1>
        <div className="flex flex-wrap items-center gap-4">
          <ChamberSelector
            value={filters.chamber as "camera" | "senato" | "both"}
            onChange={(v) => setFilters({ chamber: v })}
          />
        </div>
        <TimelineSearch
          filters={filters}
          onFiltersChange={setFilters}
          onClear={clearFilters}
          hasActiveFilters={hasActiveFilters}
        />
      </div>

      {/* Explainer text */}
      <p className="text-sm text-muted-foreground px-6 py-2">
        {t("browseDescription")}
      </p>

      {/* Session list */}
      <div className="px-6 py-4 space-y-8">
        {isLoading ? (
          <TimelineSkeleton />
        ) : error ? (
          <Alert variant="destructive">
            <AlertTitle>{t("errorHeading")}</AlertTitle>
            <AlertDescription>{t("errorBody")}</AlertDescription>
          </Alert>
        ) : !isLoading && sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
            <CalendarDays className="h-10 w-10 text-muted-foreground" />
            <h2 className="text-base font-semibold">{t("noSessionsFound")}</h2>
            <p className="text-sm text-muted-foreground">{t("noSessionsBody")}</p>
            <Button variant="outline" size="sm" onClick={clearFilters}>
              {t("clearFilters")}
            </Button>
          </div>
        ) : (
          <>
            {sessions.map((session, index) => (
              <div key={session.id}>
                <SessionCard session={session} searchTerm={filters.search} />
                {index < sessions.length - 1 && <Separator className="mt-8" />}
              </div>
            ))}
          </>
        )}

        {/* Infinite scroll sentinel */}
        <div ref={loadMoreRef} className="h-4" />

        {/* Loading more indicator */}
        {isFetchingMore && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            <span className="text-sm text-muted-foreground">{t("loadingMore")}</span>
          </div>
        )}

        {/* Accessibility live region */}
        <div aria-live="polite" className="sr-only">
          {isLoading
            ? t("loadingMore")
            : sessions.length > 0
              ? `${resultCount} sessions`
              : t("noSessionsFound")}
        </div>
      </div>

      {/* Back to top button */}
      <Button
        variant="secondary"
        size="icon"
        className={`fixed bottom-4 right-4 transition-opacity duration-200 ${
          showBackToTop ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        aria-label={t("backToTop")}
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
    </div>
  );
}
