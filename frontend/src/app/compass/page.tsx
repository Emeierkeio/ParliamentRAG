"use client";

import { useState, useCallback } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { useLocalHistory } from "@/hooks/use-local-history";
import { CompassCard } from "@/components/chat/CompassCard";
import type { CompassData } from "@/components/chat/CompassCard";
import { config } from "@/config";
import { cn } from "@/lib/utils";
import { TOPICS } from "@/lib/constants";
import {
  Compass,
  Search,
  ChevronRight,
  RotateCcw,
  Loader2,
  Scan,
  Map,
  Info,
  ArrowRight,
  AlertTriangle,
  History,
  Clock,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useTranslations } from "next-intl";
import { getVoteCompass } from "@/lib/votes-api";
import type { VoteCompassData, VoteCompassParty } from "@/types/votes";

// ── Types ──────────────────────────────────────────────────────

interface AxisSide {
  label: string;
  explanation: string;
  keywords?: string[];
}

interface AxisDef {
  positive_side?: AxisSide;
  negative_side?: AxisSide;
}


// ── Page ───────────────────────────────────────────────────────

export default function CompassPage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const compassHistory = useLocalHistory<{ compassData: CompassData; computationTime: number }>(
    "parliamentrag-compass-history"
  );

  const [compassData, setCompassData] = useState<CompassData | null>(null);
  const [topic, setTopic] = useState("");
  const [activeTopic, setActiveTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [computationTime, setComputationTime] = useState(0);

  // Vote compass state
  const [axisMode, setAxisMode] = useState<"text" | "vote">("text");
  const [voteCompass, setVoteCompass] = useState<VoteCompassData | null>(null);
  const [voteCompassLoading, setVoteCompassLoading] = useState(false);

  const t = useTranslations("CompassPage");
  const tvc = useTranslations("VoteCompass");

  const fetchCompass = useCallback(async (topicText: string) => {
    if (!topicText.trim()) return;
    setLoading(true);
    setError("");
    setActiveTopic(topicText);

    try {
      const res = await fetch(`${config.api.baseUrl}/compass`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: topicText }),
      });
      if (!res.ok) throw new Error(t("errorFetch"));
      const data = await res.json();
      const ct = data.computation_time_ms || 0;
      setCompassData(data);
      setComputationTime(ct);
      compassHistory.addEntry(topicText, { compassData: data, computationTime: ct });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("errorUnknown"));
      setCompassData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const restoreCompassEntry = useCallback(
    (entry: { topic: string; data: { compassData: CompassData; computationTime: number } }) => {
      setActiveTopic(entry.topic);
      setTopic(entry.topic);
      setCompassData(entry.data.compassData);
      setComputationTime(entry.data.computationTime);
      setError("");
      setAxisMode("text");
    },
    []
  );

  const handleTopicClick = (t: string) => {
    setTopic(t);
    fetchCompass(t);
  };

  const handleAxisModeChange = useCallback(async (mode: "text" | "vote") => {
    setAxisMode(mode);
    if (mode === "vote" && voteCompass === null && !voteCompassLoading) {
      setVoteCompassLoading(true);
      try {
        const data = await getVoteCompass(19, "camera");
        setVoteCompass(data);
      } catch {
        setVoteCompass({ available: false, reason: "fetch_error" });
      } finally {
        setVoteCompassLoading(false);
      }
    }
  }, [voteCompass, voteCompassLoading]);

  const handleReset = () => {
    setCompassData(null);
    setActiveTopic("");
    setTopic("");
    setError("");
    setAxisMode("text");
  };

  const hasResults = compassData !== null;
  const dimensionality = compassData?.meta?.dimensionality ?? 2;

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
            <h1 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight whitespace-nowrap">{t("pageTitle")}</h1>

            <div className="flex items-center gap-2 ml-auto shrink-0">
              {hasResults && !loading && (
                <>
                  <span className="text-[11px] text-muted-foreground hidden sm:inline">
                    {t("groupsCount", { count: compassData.groups.length })}
                    {computationTime > 0 && ` · ${(computationTime / 1000).toFixed(1)}s`}
                  </span>
                  <Badge variant="secondary" className="max-w-[180px] truncate text-xs">
                    {activeTopic}
                  </Badge>
                  {compassData.meta.warnings && compassData.meta.warnings.length > 0 && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-100 text-amber-600">
                          <AlertTriangle className="h-3 w-3" />
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" className="max-w-xs text-xs">
                        {compassData.meta.warnings.map((w, i) => (
                          <p key={i}>
                            {w.includes("WEAK_ALIGNMENT")
                              ? t("warningWeakAlignment")
                              : w}
                          </p>
                        ))}
                      </TooltipContent>
                    </Tooltip>
                  )}
                  <form
                    onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }}
                    className="hidden sm:flex items-center gap-1.5 ml-2"
                  >
                    <div className="relative">
                      <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        placeholder={t("placeholderNew")}
                        className="h-8 w-44 text-xs pl-7 pr-2 border-border bg-background"
                      />
                    </div>
                    <Button type="submit" size="sm" disabled={!topic.trim()} className="h-8 px-3 text-xs gap-1">
                      {t("buttonAnalyze")}
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                  </form>
                  <Button variant="ghost" size="sm" onClick={handleReset} className="h-7 text-xs gap-1 px-2">
                    <RotateCcw className="h-3 w-3" />
                    <span className="hidden sm:inline">Reset</span>
                  </Button>
                </>
              )}

              {activeTopic && loading && (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  <span className="text-xs text-muted-foreground">{t("analyzingHeader")}</span>
                </>
              )}

              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" title={t("historyTitle")}>
                    <History className="h-4 w-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-72 p-2" align="end">
                  <p className="text-[11px] uppercase tracking-[0.2em] px-2 py-1 text-muted-foreground mb-1">{t("historyHeading")}</p>
                  {compassHistory.entries.length === 0 ? (
                    <p className="text-xs text-center py-4 text-muted-foreground">{t("historyEmpty")}</p>
                  ) : (
                    <div className="space-y-0.5">
                      {compassHistory.entries.map((entry) => (
                        <div key={entry.id} className="flex items-center gap-1 group rounded-md hover:bg-muted/60">
                          <button
                            className="flex-1 flex items-center gap-2 px-2 py-1.5 text-left min-w-0"
                            onClick={() => restoreCompassEntry(entry)}
                          >
                            <Clock className="h-3 w-3 shrink-0 text-muted-foreground/60" />
                            <span className="text-xs font-medium truncate">{entry.topic}</span>
                          </button>
                          <button
                            className="shrink-0 p-1.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                            onClick={() => compassHistory.removeEntry(entry.id)}
                            title={t("historyRemove")}
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </PopoverContent>
              </Popover>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Empty state */}
          {!hasResults && !loading && (
            <div className="flex flex-col items-center justify-center h-full px-4 pb-16 overflow-y-auto">
              <div className="text-center space-y-6 max-w-lg">
                <div className="mx-auto h-14 w-14 rounded-full border border-border flex items-center justify-center">
                  <Compass className="h-6 w-6 text-primary/60" />
                </div>
                <div className="space-y-2">
                  <h2 className="[font-family:var(--font-display)] text-2xl sm:text-3xl font-medium tracking-tight text-foreground">
                    {t("pageTitle")}
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
                    {t("emptyDescription")}
                  </p>
                </div>

                {/* Search bar */}
                <div className="w-full max-w-md mx-auto pt-2">
                  <form onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }} className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <Input
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder={t("placeholderSearch")}
                      className="h-14 text-lg pl-12 pr-24 rounded-md"
                    />
                    <Button
                      type="submit"
                      disabled={!topic.trim()}
                      className="absolute right-2 top-1/2 -translate-y-1/2 h-10 px-4"
                    >
                      {t("buttonAnalyze")}
                    </Button>
                  </form>
                </div>

                {/* How it works */}
                <div className="grid grid-cols-3 gap-3 max-w-sm mx-auto pt-2">
                  <div className="flex flex-col items-center gap-1.5 p-3 border-t border-border">
                    <Search className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">{t("howStep1")}</span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 p-3 border-t border-border">
                    <Scan className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">{t("howStep2")}</span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 p-3 border-t border-border">
                    <Map className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">{t("howStep3")}</span>
                  </div>
                </div>

                {/* Topic chips */}
                <div className="pt-3">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-3">
                    {t("suggestedTopicsLabel")}
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {TOPICS.slice(0, 8).map((t) => (
                      <button
                        key={t}
                        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
                        onClick={() => handleTopicClick(t)}
                      >
                        <span className="capitalize">{t}</span>
                        <ChevronRight className="w-3 h-3 opacity-40" />
                      </button>
                    ))}
                  </div>
                </div>

                {error && (
                  <div className="mt-4 text-red-500 text-sm bg-red-50 rounded-lg px-4 py-3 border border-red-200">
                    {error}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex flex-col items-center justify-center h-full px-4 gap-6">
              <div className="relative">
                <div className="h-16 w-16 rounded-full border border-border flex items-center justify-center">
                  <Compass className="h-8 w-8 text-primary/40 animate-spin" style={{ animationDuration: "3s" }} />
                </div>
              </div>
              <div className="text-center space-y-2">
                <p className="text-sm font-medium text-foreground">{t("loadingHeading")}</p>
                <p className="text-xs text-muted-foreground">
                  {t("loadingSubtext", { topic: activeTopic })}
                </p>
              </div>
              {/* Skeleton compass */}
              <div className="w-full max-w-lg mx-auto">
                <div className="aspect-square max-w-[400px] mx-auto bg-muted/30 border border-border animate-pulse" />
                <div className="flex justify-center gap-4 mt-4">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <div className="h-3 w-3 rounded-full bg-muted animate-pulse" />
                      <div className="h-3 w-8 bg-muted/60 rounded animate-pulse" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Results - full screen layout */}
          {hasResults && !loading && (
            <div className="flex-1 flex flex-col overflow-hidden animate-in fade-in duration-500">
              {/* Controls bar: mode toggle + axis info */}
              <div className="shrink-0 border-b border-border/40 bg-muted/20 px-4 sm:px-6 py-2.5">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                  {/* Segmented mode toggle */}
                  <div className="flex rounded-lg border border-border overflow-hidden text-xs font-medium shrink-0">
                    <button
                      onClick={() => handleAxisModeChange("text")}
                      className={cn(
                        "px-3 py-1.5 transition-colors",
                        axisMode === "text"
                          ? "bg-primary text-primary-foreground"
                          : "bg-background hover:bg-muted text-muted-foreground"
                      )}
                    >
                      {tvc("toggleText")}
                    </button>
                    <button
                      onClick={() => handleAxisModeChange("vote")}
                      className={cn(
                        "px-3 py-1.5 transition-colors",
                        axisMode === "vote"
                          ? "bg-primary text-primary-foreground"
                          : "bg-background hover:bg-muted text-muted-foreground"
                      )}
                    >
                      {tvc("toggleVote")}
                    </button>
                  </div>

                  {/* Thesis tooltip */}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="cursor-help shrink-0">
                        <Info className="h-3.5 w-3.5 text-muted-foreground/50" />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs text-xs">
                      {tvc("tooltip")}
                    </TooltipContent>
                  </Tooltip>

                  {/* Text mode: axis summaries */}
                  {axisMode === "text" && (
                    <>
                      <div className="hidden sm:block w-px h-5 bg-border/60 shrink-0" />
                      {/* PC1 */}
                      {compassData.axes.x && (compassData.axes.x.negative_side || compassData.axes.x.positive_side) && (
                        <AxisSummary
                          label="PC1"
                          variancePercent={Math.round((compassData.meta.explained_variance_ratio?.[0] || 0) * 100)}
                          negLabel={compassData.axes.x.negative_side?.label}
                          posLabel={compassData.axes.x.positive_side?.label}
                          negKeywords={compassData.axes.x.negative_side?.keywords}
                          posKeywords={compassData.axes.x.positive_side?.keywords}
                        />
                      )}
                      {/* PC2 */}
                      {dimensionality !== 1 && compassData.axes.y && (compassData.axes.y.negative_side || compassData.axes.y.positive_side) && (
                        <>
                          <div className="hidden sm:block w-px h-5 bg-border/60" />
                          <AxisSummary
                            label="PC2"
                            variancePercent={Math.round((compassData.meta.explained_variance_ratio?.[1] || 0) * 100)}
                            negLabel={compassData.axes.y.negative_side?.label}
                            posLabel={compassData.axes.y.positive_side?.label}
                            negKeywords={compassData.axes.y.negative_side?.keywords}
                            posKeywords={compassData.axes.y.positive_side?.keywords}
                          />
                        </>
                      )}
                      {/* Dimensionality badge */}
                      <Badge variant="outline" className="text-[10px] ml-auto hidden sm:inline-flex">
                        {dimensionality === 1 ? "1D Spectrum" : "2D PCA"}
                      </Badge>
                    </>
                  )}

                  {/* Vote mode: variance explained */}
                  {axisMode === "vote" && voteCompass?.available && voteCompass.variance_explained && voteCompass.variance_explained.length >= 2 && (
                    <span className="text-[11px] text-muted-foreground">
                      {tvc("variance")}: PC1 {(voteCompass.variance_explained[0] * 100).toFixed(0)}% · PC2 {(voteCompass.variance_explained[1] * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>

              {/* Compass visualization - fills remaining space */}
              {axisMode === "text" ? (
                <div className="flex-1 min-h-0 p-3 sm:p-4">
                  <div className="h-full w-full mx-auto">
                    <CompassCard data={compassData} />
                  </div>
                </div>
              ) : (
                <div className="flex-1 min-h-0 p-3 sm:p-4 flex flex-col items-center justify-center">
                  {voteCompassLoading ? (
                    <Loader2 className="h-8 w-8 animate-spin text-primary/40" />
                  ) : voteCompass?.available && voteCompass.parties && voteCompass.parties.length > 0 ? (
                    <VoteCompassScatter parties={voteCompass.parties} varianceExplained={voteCompass.variance_explained} />
                  ) : (
                    <div className="flex flex-col items-center gap-3 text-center">
                      <Info className="h-8 w-8 text-muted-foreground/30" />
                      <p className="text-sm text-muted-foreground">{tvc("unavailable")}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Mobile search bar */}
              <div className="sm:hidden shrink-0 border-t border-border/40 px-4 py-2">
                <form
                  onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }}
                  className="flex items-center gap-2"
                >
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder={t("placeholderNew")}
                    className="h-8 text-xs flex-1"
                  />
                  <Button type="submit" size="sm" disabled={!topic.trim()} className="h-8 px-3 text-xs">
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleReset} className="h-8 px-2">
                    <RotateCcw className="h-3 w-3" />
                  </Button>
                </form>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Vote Compass Scatter ───────────────────────────────────────

function VoteCompassScatter({ parties, varianceExplained }: {
  parties: VoteCompassParty[];
  varianceExplained?: number[];
}) {
  const tvc = useTranslations("VoteCompass");
  const SVG_SIZE = 480;
  const MARGIN = 64;
  const INNER = SVG_SIZE - 2 * MARGIN;

  const xs = parties.map((p) => p.x);
  const ys = parties.map((p) => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xPad = (xMax - xMin || 2) * 0.2;
  const yPad = (yMax - yMin || 2) * 0.2;
  const xLo = xMin - xPad;
  const xHi = xMax + xPad;
  const yLo = yMin - yPad;
  const yHi = yMax + yPad;

  const toX = (x: number) => MARGIN + ((x - xLo) / (xHi - xLo)) * INNER;
  const toY = (y: number) => SVG_SIZE - MARGIN - ((y - yLo) / (yHi - yLo)) * INNER;

  // Center lines at origin (x=0, y=0) if within view
  const cx0 = toX(0);
  const cy0 = toY(0);
  const showXAxis = cx0 >= MARGIN && cx0 <= SVG_SIZE - MARGIN;
  const showYAxis = cy0 >= MARGIN && cy0 <= SVG_SIZE - MARGIN;

  return (
    <div className="h-full w-full flex flex-col items-center overflow-hidden">
      <svg
        viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
        className="flex-1 w-full max-w-[560px] max-h-[calc(100%-28px)]"
      >
        {/* Plot area border */}
        <rect
          x={MARGIN}
          y={MARGIN}
          width={INNER}
          height={INNER}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.07}
          strokeWidth={1}
        />

        {/* Origin lines */}
        {showXAxis && (
          <line
            x1={cx0}
            y1={MARGIN}
            x2={cx0}
            y2={SVG_SIZE - MARGIN}
            stroke="currentColor"
            strokeOpacity={0.13}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        )}
        {showYAxis && (
          <line
            x1={MARGIN}
            y1={cy0}
            x2={SVG_SIZE - MARGIN}
            y2={cy0}
            stroke="currentColor"
            strokeOpacity={0.13}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
        )}

        {/* Axis labels */}
        <text
          x={SVG_SIZE / 2}
          y={SVG_SIZE - MARGIN / 3.5}
          textAnchor="middle"
          fontSize={9}
          fill="currentColor"
          fillOpacity={0.35}
        >
          PC1
        </text>
        <text
          x={MARGIN / 3.5}
          y={SVG_SIZE / 2}
          textAnchor="middle"
          fontSize={9}
          fill="currentColor"
          fillOpacity={0.35}
          transform={`rotate(-90, ${MARGIN / 3.5}, ${SVG_SIZE / 2})`}
        >
          PC2
        </text>

        {/* Party points and labels */}
        {parties.map((p) => {
          const px = toX(p.x);
          const py = toY(p.y);
          const groupConfig = config.politicalGroups[p.party as keyof typeof config.politicalGroups];
          const color = groupConfig?.color || "#6366f1";
          const shortLabel = p.party.length > 24 ? p.party.substring(0, 24) + "…" : p.party;
          return (
            <g key={p.party}>
              <circle cx={px} cy={py} r={5.5} fill={color} fillOpacity={0.8} />
              <text
                x={px}
                y={py - 9}
                textAnchor="middle"
                fontSize={9.5}
                fill="currentColor"
                fillOpacity={0.82}
              >
                {shortLabel}
              </text>
            </g>
          );
        })}
      </svg>

      {varianceExplained && varianceExplained.length >= 2 && (
        <p className="text-[10px] text-muted-foreground shrink-0 pb-1 mt-1">
          {tvc("variance")}: PC1 {(varianceExplained[0] * 100).toFixed(0)}% · PC2 {(varianceExplained[1] * 100).toFixed(0)}%
        </p>
      )}
    </div>
  );
}

// ── Axis Summary (compact inline) ─────────────────────────────

function AxisSummary({ label, variancePercent, negLabel, posLabel, negKeywords, posKeywords }: {
  label: string;
  variancePercent: number;
  negLabel?: string;
  posLabel?: string;
  negKeywords?: string[];
  posKeywords?: string[];
}) {
  const t = useTranslations("CompassPage");
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="[font-family:var(--font-display)] font-medium text-foreground">{label}</span>
      <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/70">({label === "PC1" ? t("axisX") : t("axisY")})</span>
      <span className="text-[10px] text-muted-foreground">{variancePercent}%</span>
      <div className="flex items-center gap-1.5">
        {negLabel && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 border border-blue-100 text-blue-700 text-[11px] font-medium cursor-help max-w-[280px]">
                <span className="text-blue-400 text-[10px]">&minus;</span>
                {negLabel}
              </span>
            </TooltipTrigger>
            {negKeywords && negKeywords.length > 0 && (
              <TooltipContent side="bottom" className="text-xs">
                <p className="font-medium mb-1">{t("keywordsNeg")}</p>
                <div className="flex flex-wrap gap-1">
                  {negKeywords.slice(0, 6).map((kw, i) => (
                    <span key={i} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px]">{kw}</span>
                  ))}
                </div>
              </TooltipContent>
            )}
          </Tooltip>
        )}
        <span className="text-muted-foreground/40">↔</span>
        {posLabel && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-50 border border-rose-100 text-rose-700 text-[11px] font-medium cursor-help max-w-[280px]">
                <span className="text-rose-400 text-[10px]">+</span>
                {posLabel}
              </span>
            </TooltipTrigger>
            {posKeywords && posKeywords.length > 0 && (
              <TooltipContent side="bottom" className="text-xs">
                <p className="font-medium mb-1">{t("keywordsPos")}</p>
                <div className="flex flex-wrap gap-1">
                  {posKeywords.slice(0, 6).map((kw, i) => (
                    <span key={i} className="px-1.5 py-0.5 bg-rose-100 text-rose-700 rounded text-[10px]">{kw}</span>
                  ))}
                </div>
              </TooltipContent>
            )}
          </Tooltip>
        )}
      </div>
    </div>
  );
}
