"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { searchVotes } from "@/lib/votes-api";
import type { VoteExplorerEntry } from "@/types";
import { cn } from "@/lib/utils";
import { Loader2, Vote } from "lucide-react";
import { Button } from "@/components/ui/button";

const PAGE_LIMIT = 50;

export default function VotesPage() {
  const t = useTranslations("Votes");
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();

  // Filter state
  const [chamber, setChamber] = useState<string>("both");
  const [legislature, setLegislature] = useState<number>(19);
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");
  const [outcome, setOutcome] = useState<string>("");
  const [minMargin, setMinMargin] = useState<number | "">("");

  // Pagination + data state
  const [rows, setRows] = useState<VoteExplorerEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);
  const [hasMore, setHasMore] = useState(false);
  const [count, setCount] = useState(0);

  const buildParams = useCallback(() => ({
    chamber: chamber === "both" ? "both" : chamber,
    legislature,
    ...(fromDate ? { from_date: fromDate } : {}),
    ...(toDate ? { to_date: toDate } : {}),
    ...(outcome ? { outcome } : {}),
    ...(minMargin !== "" ? { min_margin: Number(minMargin) } : {}),
    limit: PAGE_LIMIT,
    offset: 0,
  }), [chamber, legislature, fromDate, toDate, outcome, minMargin]);

  const fetchVotes = useCallback(async () => {
    setLoading(true);
    setError("");
    setOffset(0);
    try {
      const data = await searchVotes(buildParams());
      setRows(data.votes);
      setCount(data.count);
      setHasMore(data.offset + data.votes.length < data.count);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  const loadMore = useCallback(async () => {
    const nextOffset = offset + PAGE_LIMIT;
    setLoadingMore(true);
    try {
      const data = await searchVotes({ ...buildParams(), offset: nextOffset });
      setRows(prev => [...prev, ...data.votes]);
      setOffset(nextOffset);
      setHasMore(nextOffset + data.votes.length < data.count);
    } catch {
      // silently ignore pagination errors
    } finally {
      setLoadingMore(false);
    }
  }, [buildParams, offset]);

  // Fetch on filter change
  useEffect(() => {
    fetchVotes();
  }, [chamber, legislature, fromDate, toDate, outcome, minMargin]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRowClick = (entry: VoteExplorerEntry) => {
    if (entry.debate_id) {
      window.location.href = `/transcript/${entry.debate_id}`;
    } else {
      window.location.href = "/timeline";
    }
  };

  const formatOutcome = (o: string) => {
    if (o === "approved") return t("outcomeApproved");
    if (o === "rejected") return t("outcomeRejected");
    return o;
  };

  const formatChamber = (c: string) => {
    if (c === "camera") return "Camera";
    if (c === "senato") return "Senato";
    return c;
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={toggle}
        isMobile={isMobile}
        isMobileOpen={isMobileOpen}
        onCloseMobile={closeMobile}
      />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3 px-4 sm:px-6 h-14">
            <MobileMenuButton onClick={toggle} />
            <h1 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight whitespace-nowrap">
              {t("title")}
            </h1>
          </div>
        </header>

        {/* Filter bar */}
        <div className="border-b border-border/50 bg-muted/30 px-4 sm:px-6 py-3 shrink-0">
          <div className="flex flex-wrap items-end gap-3 max-w-6xl">
            {/* Chamber */}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("filterChamber")}
              <select
                value={chamber}
                onChange={e => setChamber(e.target.value)}
                className="h-8 text-xs rounded-md border border-border bg-background px-2 text-foreground"
              >
                <option value="both">Entrambe</option>
                <option value="camera">Camera</option>
                <option value="senato">Senato</option>
              </select>
            </label>

            {/* Legislature */}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("filterLegislature")}
              <select
                value={legislature}
                onChange={e => setLegislature(Number(e.target.value))}
                className="h-8 text-xs rounded-md border border-border bg-background px-2 text-foreground"
              >
                <option value={19}>XIX</option>
                <option value={18}>XVIII</option>
              </select>
            </label>

            {/* Date from */}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("dateFrom")}
              <input
                type="date"
                value={fromDate}
                onChange={e => setFromDate(e.target.value)}
                className="h-8 text-xs rounded-md border border-border bg-background px-2 text-foreground"
              />
            </label>

            {/* Date to */}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("dateTo")}
              <input
                type="date"
                value={toDate}
                onChange={e => setToDate(e.target.value)}
                className="h-8 text-xs rounded-md border border-border bg-background px-2 text-foreground"
              />
            </label>

            {/* Outcome */}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("outcome")}
              <select
                value={outcome}
                onChange={e => setOutcome(e.target.value)}
                className="h-8 text-xs rounded-md border border-border bg-background px-2 text-foreground"
              >
                <option value="">Tutti</option>
                <option value="approved">{t("outcomeApproved")}</option>
                <option value="rejected">{t("outcomeRejected")}</option>
              </select>
            </label>

            {/* Min margin */}
            <label className="flex flex-col gap-1 text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              {t("minMargin")}
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={minMargin}
                onChange={e => setMinMargin(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="0"
                className="h-8 w-24 text-xs rounded-md border border-border bg-background px-2 text-foreground"
              />
            </label>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 text-primary/40 animate-spin" />
            </div>
          )}

          {!loading && error && (
            <div className="px-4 sm:px-6 py-8 text-sm text-destructive">{error}</div>
          )}

          {!loading && !error && rows.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full px-4 pb-16 gap-4">
              <div className="h-14 w-14 rounded-full border border-border flex items-center justify-center">
                <Vote className="h-6 w-6 text-primary/60" />
              </div>
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            </div>
          )}

          {!loading && !error && rows.length > 0 && (
            <div className="px-4 sm:px-6 py-4 max-w-7xl mx-auto w-full">
              {/* Results count */}
              <p className="text-[11px] text-muted-foreground mb-3">
                {rows.length} / {count}
              </p>

              {/* Table header */}
              <div className="hidden sm:grid grid-cols-[7rem_4rem_1fr_6rem_5rem_5rem_6rem] gap-3 px-4 py-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground border-b border-border">
                <span>{t("colDate")}</span>
                <span>{t("colChamber")}</span>
                <span>{t("colLabel")}</span>
                <span>{t("colOutcome")}</span>
                <span className="text-right">{t("colFavor")}</span>
                <span className="text-right">{t("colAgainst")}</span>
                <span className="text-right">{t("colMargin")}</span>
              </div>

              {/* Rows */}
              <div className="divide-y divide-border">
                {rows.map(entry => (
                  <VoteRow
                    key={entry.vote_id}
                    entry={entry}
                    onClick={() => handleRowClick(entry)}
                    formatOutcome={formatOutcome}
                    formatChamber={formatChamber}
                  />
                ))}
              </div>

              {/* Load more */}
              {hasMore && (
                <div className="flex justify-center pt-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="text-xs gap-2"
                  >
                    {loadingMore && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    {t("loadMore")}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Vote Row ──────────────────────────────────────────────────────

interface VoteRowProps {
  entry: VoteExplorerEntry;
  onClick: () => void;
  formatOutcome: (o: string) => string;
  formatChamber: (c: string) => string;
}

function VoteRow({ entry, onClick, formatOutcome, formatChamber }: VoteRowProps) {
  const total = entry.in_favor + entry.against + entry.abstained || 1;
  const favorPct = Math.round((entry.in_favor / total) * 100);
  const againstPct = Math.round((entry.against / total) * 100);
  const marginPct = Math.round(Math.abs(entry.margin) * 100);
  const approved = entry.outcome === "approved";

  return (
    <>
      {/* Desktop row */}
      <div
        className="hidden sm:grid grid-cols-[7rem_4rem_1fr_6rem_5rem_5rem_6rem] gap-3 items-center px-4 py-2.5 hover:bg-muted/40 transition-colors cursor-pointer"
        onClick={onClick}
      >
        <span className="[font-family:var(--font-display)] text-[13px] tabular-nums text-muted-foreground shrink-0">
          {entry.date}
        </span>
        <span className="text-[11px] text-muted-foreground truncate">
          {formatChamber(entry.chamber)}
        </span>
        <span className="text-[13px] text-foreground truncate leading-snug">
          {entry.label}
        </span>
        <span
          className={cn(
            "text-[11px] font-medium truncate",
            approved ? "text-green-600" : "text-red-500"
          )}
        >
          {formatOutcome(entry.outcome)}
        </span>
        <span className="[font-family:var(--font-display)] text-[13px] tabular-nums text-right text-foreground">
          {favorPct}%
        </span>
        <span className="[font-family:var(--font-display)] text-[13px] tabular-nums text-right text-foreground">
          {againstPct}%
        </span>
        <div className="flex items-center justify-end gap-1.5">
          <div className="w-10 h-1 rounded-full bg-muted overflow-hidden">
            <div
              className={cn("h-full rounded-full", approved ? "bg-green-500" : "bg-red-400")}
              style={{ width: `${Math.min(marginPct, 100)}%` }}
            />
          </div>
          <span className="[font-family:var(--font-display)] text-[13px] tabular-nums text-foreground min-w-[28px] text-right">
            {marginPct}%
          </span>
        </div>
      </div>

      {/* Mobile row */}
      <div
        className="sm:hidden flex flex-col gap-0.5 px-4 py-3 active:bg-muted/40 transition-colors cursor-pointer"
        onClick={onClick}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] text-muted-foreground">{entry.date} · {formatChamber(entry.chamber)}</span>
          <span className={cn("text-[11px] font-medium", approved ? "text-green-600" : "text-red-500")}>
            {formatOutcome(entry.outcome)}
          </span>
        </div>
        <p className="text-[13px] text-foreground leading-snug line-clamp-2">{entry.label}</p>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-0.5">
          <span className="[font-family:var(--font-display)] tabular-nums">{favorPct}% — {againstPct}%</span>
          <span>Margine: <span className="[font-family:var(--font-display)] tabular-nums">{marginPct}%</span></span>
        </div>
      </div>
    </>
  );
}
