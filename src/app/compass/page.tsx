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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

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

            {activeTopic && !loading && (
              <div className="flex items-center gap-2 ml-auto shrink-0">
                <Badge variant="secondary" className="max-w-[180px] truncate text-xs">
                  {activeTopic}
                </Badge>
                <Button variant="ghost" size="icon-xs" onClick={handleReset} className="h-6 w-6">
                  <RotateCcw className="h-3 w-3" />
                </Button>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Empty state */}
          {!hasResults && !loading && (
            <div className="flex flex-col items-center justify-center h-full px-4 pb-16">
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

          {/* Results */}
          {hasResults && !loading && (
            <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto w-full space-y-6 animate-in fade-in duration-500">
              {/* Results info bar */}
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  {compassData.groups.length} gruppi parlamentari analizzati
                  {computationTime > 0 && ` · ${(computationTime / 1000).toFixed(1)}s`}
                </p>
                <Button variant="ghost" size="sm" onClick={handleReset} className="h-7 text-xs gap-1.5">
                  <RotateCcw className="h-3 w-3" />
                  Nuova analisi
                </Button>
              </div>

              {/* Compass visualization card */}
              <div className="rounded-2xl border border-border/60 bg-card/80 backdrop-blur-sm shadow-sm p-5 sm:p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Compass className="h-5 w-5 text-primary" />
                  <h3 className="text-sm font-semibold text-foreground">Mappa dei posizionamenti</h3>
                  <Badge variant="secondary" className="ml-auto text-[10px]">
                    {compassData.meta.dimensionality === 1 ? "1D Spectrum" : "2D PCA"}
                  </Badge>
                </div>
                <CompassCard data={compassData as any} />
              </div>

              {/* Axis details cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* X axis */}
                {compassData.axes.x && (
                  <AxisDetailCard
                    axisLabel="Asse X (PC1)"
                    axis={compassData.axes.x}
                    variancePercent={Math.round((compassData.meta.explained_variance_ratio?.[0] || 0) * 100)}
                  />
                )}
                {/* Y axis */}
                {compassData.meta.dimensionality !== 1 && compassData.axes.y && (
                  <AxisDetailCard
                    axisLabel="Asse Y (PC2)"
                    axis={compassData.axes.y}
                    variancePercent={Math.round((compassData.meta.explained_variance_ratio?.[1] || 0) * 100)}
                  />
                )}
              </div>

              {/* Warnings */}
              {compassData.meta.warnings && compassData.meta.warnings.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <Info className="h-4 w-4 text-amber-600" />
                    <span className="text-xs font-medium text-amber-800">Note sull&apos;analisi</span>
                  </div>
                  <ul className="space-y-1">
                    {compassData.meta.warnings.map((w, i) => (
                      <li key={i} className="text-xs text-amber-700 pl-6">
                        {w.includes("WEAK_ALIGNMENT")
                          ? "L'asse secondario presenta rumore elevato. Si consiglia l'analisi 1D."
                          : w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Search again inline */}
              <div className="rounded-xl border border-border/50 bg-muted/20 p-4">
                <form
                  onSubmit={(e) => { e.preventDefault(); fetchCompass(topic); }}
                  className="flex items-center gap-3"
                >
                  <Search className="h-4 w-4 text-muted-foreground shrink-0" />
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Analizza un altro tema..."
                    className="h-9 text-sm flex-1 border-0 bg-transparent shadow-none focus-visible:ring-0 px-0"
                  />
                  <Button type="submit" size="sm" disabled={!topic.trim()} className="h-8 px-3 text-xs gap-1">
                    Analizza
                    <ArrowRight className="h-3 w-3" />
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

// ── Axis Detail Card ──────────────────────────────────────────

function AxisDetailCard({ axisLabel, axis, variancePercent }: {
  axisLabel: string;
  axis: AxisDef;
  variancePercent: number;
}) {
  const pos = axis.positive_side;
  const neg = axis.negative_side;

  if (!pos && !neg) return null;

  return (
    <div className="rounded-xl border border-border/50 bg-card/60 backdrop-blur-sm p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">{axisLabel}</span>
        <Badge variant="outline" className="text-[10px]">{variancePercent}% varianza</Badge>
      </div>

      {/* Poles visualization */}
      <div className="flex items-stretch gap-2">
        {/* Negative pole */}
        {neg && (
          <div className="flex-1 rounded-lg bg-blue-50 border border-blue-100 p-2.5 space-y-1">
            <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wide">Polo (−)</span>
            <p className="text-xs font-medium text-blue-900">{neg.label}</p>
            <p className="text-[10px] text-blue-700/80 leading-relaxed">{neg.explanation}</p>
            {neg.keywords && neg.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {neg.keywords.slice(0, 4).map((kw, i) => (
                  <span key={i} className="px-1.5 py-0.5 text-[9px] bg-blue-100 text-blue-700 rounded">
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Positive pole */}
        {pos && (
          <div className="flex-1 rounded-lg bg-rose-50 border border-rose-100 p-2.5 space-y-1">
            <span className="text-[10px] font-bold text-rose-700 uppercase tracking-wide">Polo (+)</span>
            <p className="text-xs font-medium text-rose-900">{pos.label}</p>
            <p className="text-[10px] text-rose-700/80 leading-relaxed">{pos.explanation}</p>
            {pos.keywords && pos.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {pos.keywords.slice(0, 4).map((kw, i) => (
                  <span key={i} className="px-1.5 py-0.5 text-[9px] bg-rose-100 text-rose-700 rounded">
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
