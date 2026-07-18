"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Loader2, ArrowUp, CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { SessionCard } from "@/components/timeline/SessionCard";
import { TimelineSearch } from "@/components/timeline/TimelineSearch";
import { TimelineSkeleton } from "@/components/timeline/TimelineSkeleton";
import { useTimeline } from "@/hooks/use-timeline";

export default function TimelinePage() {
  const t = useTranslations("Timeline");
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const mainRef = useRef<HTMLElement | null>(null);
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
  } = useTimeline({ scrollContainerRef: mainRef });

  // Back to top — tracks scroll on the main container, not window
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    const handleScroll = () => setShowBackToTop(el.scrollTop > 400);
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = useCallback(() => {
    mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <div className="flex h-screen bg-background overflow-hidden pb-[calc(3.5rem+env(safe-area-inset-bottom))] md:pb-0">
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={toggle}
        isMobile={isMobile}
        isMobileOpen={isMobileOpen}
        onCloseMobile={closeMobile}
      />

      <main ref={mainRef} className="flex-1 flex flex-col min-w-0 overflow-y-auto overscroll-contain">
        {/* Sticky header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3 px-4 sm:px-6 h-14">
            <MobileMenuButton onClick={toggle} />
            <h1 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight whitespace-nowrap">{t("pageTitle")}</h1>
          </div>
          <div className="px-4 sm:px-6 pb-3">
            <TimelineSearch
              filters={filters}
              onFiltersChange={setFilters}
              onClear={clearFilters}
              hasActiveFilters={hasActiveFilters}
            />
          </div>
        </header>

        {/* Explainer text */}
        <p className="text-sm text-muted-foreground px-4 sm:px-6 py-2">
          {t("browseDescription")}
        </p>

        {/* Session list */}
        <div className="px-4 sm:px-6 py-4 flex-1">
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
              <h2 className="[font-family:var(--font-display)] text-xl font-medium tracking-tight">{t("noSessionsFound")}</h2>
              <p className="text-sm text-muted-foreground">{t("noSessionsBody")}</p>
              <Button variant="outline" size="sm" onClick={clearFilters}>
                {t("clearFilters")}
              </Button>
            </div>
          ) : (
            /* ── Timeline layout ── */
            <div className="relative">
              {/* Vertical timeline line — stops at last dot (mt-5 + half dot = ~1.5rem from last item top) */}
              <div className="absolute left-3 sm:left-5 top-0 bottom-6 w-px bg-border" />

              <div className="space-y-6">
                {sessions.map((session) => {
                  const d = new Date(session.date);
                  const day = d.getDate();
                  const month = d.toLocaleDateString(undefined, { month: "short" });
                  const year = d.getFullYear();

                  return (
                    <div key={session.id} className="relative flex gap-4 sm:gap-6">
                      {/* ── Date marker ── */}
                      <div className="relative z-10 flex flex-col items-center shrink-0 w-6 sm:w-10">
                        {/* Dot on the line */}
                        <div className="w-3 h-3 rounded-full bg-primary ring-4 ring-background mt-5" />
                        {/* Date label (desktop) */}
                        <div className="hidden sm:flex flex-col items-center mt-2">
                          <span className="[font-family:var(--font-display)] text-base font-medium text-foreground/80 tabular-nums leading-none">
                            {day}
                          </span>
                          <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground leading-tight mt-0.5">
                            {month}
                          </span>
                          <span className="text-[10px] text-muted-foreground tabular-nums leading-tight">
                            {year}
                          </span>
                        </div>
                      </div>

                      {/* ── Session card ── */}
                      <div className="flex-1 min-w-0 pb-2">
                        {/* Mobile date + chamber badge row */}
                        <div className="flex items-center gap-2 mb-1 sm:hidden">
                          <span className="text-xs font-medium text-muted-foreground">
                            {d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
                          </span>
                          <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            {session.chamber}
                          </span>
                        </div>
                        <SessionCard session={session} searchTerm={filters.search} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
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
          className={`fixed bottom-4 right-4 z-20 transition-opacity duration-200 ${
            showBackToTop ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
          onClick={scrollToTop}
          aria-label={t("backToTop")}
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </main>
    </div>
  );
}
