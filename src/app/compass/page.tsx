"use client";

import { useState, useCallback } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { CompassCard } from "@/components/chat/CompassCard";
import { config } from "@/config";
import { cn } from "@/lib/utils";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

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

interface CompassData {
  meta: {
    query: string;
    explained_variance_ratio: number[];
    dimensionality?: number;
    is_stable: boolean;
    warnings?: string[];
  };
  axes: { x: AxisDef; y: AxisDef };
  groups: any[];
  scatter_sample: any[];
}

const TOPICS = [
  "PNRR", "riforma sanitaria", "transizione energetica", "salario minimo",
  "conflitto in Ucraina", "riforma fiscale", "autonomia differenziata",
  "riforma della giustizia", "flussi migratori", "scuola e istruzione",
  "cambiamento climatico", "infrastrutture",
];

// ── Page ───────────────────────────────────────────────────────

export default function CompassPage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();

  const [compassData, setCompassData] = useState<CompassData | null>(null);
  const [topic, setTopic] = useState("");
  const [activeTopic, setActiveTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [computationTime, setComputationTime] = useState(0);

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
      if (!res.ok) throw new Error("Errore nel calcolo del compasso ideologico");
      const data = await res.json();
      setCompassData(data);
      setComputationTime(data.computation_time_ms || 0);
    } catch (e: any) {
      setError(e.message || "Errore sconosciuto");
      setCompassData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleTopicClick = (t: string) => {
    setTopic(t);
    fetchCompass(t);
  };

  const handleReset = () => {
    setCompassData(null);
    setActiveTopic("");
    setTopic("");
    setError("");
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
            <h1 className="text-base font-semibold whitespace-nowrap">Compasso Ideologico</h1>

            {hasResults && !loading && (
              <div className="flex items-center gap-2 ml-auto shrink-0">
                <span className="text-[11px] text-muted-foreground hidden sm:inline">
                  {compassData.groups.length} gruppi
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
                            ? "Asse secondario con rumore elevato. Consigliata analisi 1D."
                            : w}
                        </p>
                      ))}
                    </TooltipContent>
                  </Tooltip>
                )}
                <form
                  onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }}
                  className="hidden sm:flex items-center gap-1.5 ml-1"
                >
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Nuovo tema..."
                    className="h-7 w-36 text-xs border-border/50 bg-muted/30"
                  />
                  <Button type="submit" size="sm" disabled={!topic.trim()} className="h-7 px-2 text-xs">
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </form>
                <Button variant="ghost" size="sm" onClick={handleReset} className="h-7 text-xs gap-1 px-2">
                  <RotateCcw className="h-3 w-3" />
                  <span className="hidden sm:inline">Reset</span>
                </Button>
              </div>
            )}

            {activeTopic && loading && (
              <div className="flex items-center gap-2 ml-auto shrink-0">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span className="text-xs text-muted-foreground">Analisi in corso...</span>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Empty state */}
          {!hasResults && !loading && (
            <div className="flex flex-col items-center justify-center h-full px-4 pb-16 overflow-y-auto">
              <div className="text-center space-y-6 max-w-lg">
                <div className="mx-auto h-16 w-16 rounded-2xl bg-primary/8 flex items-center justify-center">
                  <Compass className="h-8 w-8 text-primary/60" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-foreground">
                    Compasso Ideologico
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
                    Inserisci un tema politico per visualizzare il posizionamento ideologico
                    di tutti i gruppi parlamentari. L&apos;analisi PCA mappa le posizioni
                    sulla base dei discorsi e degli atti in Parlamento.
                  </p>
                </div>

                {/* Search bar */}
                <div className="w-full max-w-md mx-auto pt-2">
                  <form onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }} className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <Input
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      placeholder="Cerca un tema..."
                      className="h-14 text-lg pl-12 pr-24 shadow-sm border-2 focus-visible:ring-offset-2 focus-visible:border-primary transition-all rounded-lg"
                    />
                    <Button
                      type="submit"
                      disabled={!topic.trim()}
                      className="absolute right-2 top-1/2 -translate-y-1/2 h-10 px-4"
                    >
                      Analizza
                    </Button>
                  </form>
                </div>

                {/* How it works */}
                <div className="grid grid-cols-3 gap-3 max-w-sm mx-auto pt-2">
                  <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-muted/40">
                    <Search className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">Cerca un tema</span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-muted/40">
                    <Scan className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">Analisi PCA</span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-muted/40">
                    <Map className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">Mappa ideologica</span>
                  </div>
                </div>

                {/* Topic chips */}
                <div className="pt-3">
                  <p className="text-xs font-medium text-muted-foreground mb-3">
                    Oppure prova con un tema suggerito
                  </p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {TOPICS.slice(0, 8).map((t) => (
                      <button
                        key={t}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 bg-card px-3 py-1.5 text-xs text-muted-foreground transition-all hover:border-primary/50 hover:text-foreground hover:bg-primary/5 hover:shadow-sm"
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
                <div className="h-20 w-20 rounded-2xl bg-primary/5 flex items-center justify-center">
                  <Compass className="h-10 w-10 text-primary/40 animate-spin" style={{ animationDuration: "3s" }} />
                </div>
              </div>
              <div className="text-center space-y-2">
                <p className="text-sm font-medium text-foreground">Analisi ideologica in corso...</p>
                <p className="text-xs text-muted-foreground">
                  Recupero evidenze e calcolo posizionamento PCA per &quot;{activeTopic}&quot;
                </p>
              </div>
              {/* Skeleton compass */}
              <div className="w-full max-w-lg mx-auto">
                <div className="aspect-square max-w-[400px] mx-auto rounded-xl bg-muted/30 border border-border/50 animate-pulse" />
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
              {/* Axis summary bar */}
              <div className="shrink-0 border-b border-border/40 bg-muted/20 px-4 sm:px-6 py-2.5">
                <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
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
                </div>
              </div>

              {/* Compass visualization - fills remaining space */}
              <div className="flex-1 min-h-0 p-3 sm:p-4">
                <div className="h-full w-full max-w-[min(100%,calc(100vh-12rem))] mx-auto">
                  <CompassCard data={compassData as any} />
                </div>
              </div>

              {/* Mobile search bar */}
              <div className="sm:hidden shrink-0 border-t border-border/40 px-4 py-2">
                <form
                  onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }}
                  className="flex items-center gap-2"
                >
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Nuovo tema..."
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

// ── Axis Summary (compact inline) ─────────────────────────────

function AxisSummary({ label, variancePercent, negLabel, posLabel, negKeywords, posKeywords }: {
  label: string;
  variancePercent: number;
  negLabel?: string;
  posLabel?: string;
  negKeywords?: string[];
  posKeywords?: string[];
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="font-semibold text-foreground/70">{label}</span>
      <span className="text-[10px] text-muted-foreground">{variancePercent}%</span>
      <div className="flex items-center gap-1.5">
        {negLabel && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 border border-blue-100 text-blue-700 text-[11px] font-medium cursor-help truncate max-w-[140px]">
                <span className="text-blue-400 text-[10px]">&minus;</span>
                {negLabel}
              </span>
            </TooltipTrigger>
            {negKeywords && negKeywords.length > 0 && (
              <TooltipContent side="bottom" className="text-xs">
                <p className="font-medium mb-1">Parole chiave polo (−)</p>
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
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-50 border border-rose-100 text-rose-700 text-[11px] font-medium cursor-help truncate max-w-[140px]">
                <span className="text-rose-400 text-[10px]">+</span>
                {posLabel}
              </span>
            </TooltipTrigger>
            {posKeywords && posKeywords.length > 0 && (
              <TooltipContent side="bottom" className="text-xs">
                <p className="font-medium mb-1">Parole chiave polo (+)</p>
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
