"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { SurveyModal } from "@/components/survey/SurveyModal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  HorizontalBarChart,
  MetricCard,
  MiniMetricBars,
  ABComparisonChart,
  WinRateChart,
} from "@/components/evaluation/EvaluationCharts";
import { getDashboardData, getExportCsvUrl } from "@/lib/evaluation-api";
import type { EvaluationDashboardData, CombinedEvaluation } from "@/types/evaluation";
import { AB_DIMENSIONS, SIMPLE_DIMENSION_LABELS } from "@/types/survey";
import type { ABRating, SimpleDimension } from "@/types/survey";
import {
  BarChart3,
  Users,
  Quote,
  Award,
  FileText,
  Download,
  ClipboardCheck,
  Loader2,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  Target,
  Trophy,
  BarChart2,
} from "lucide-react";
import { cn } from "@/lib/utils";

const DIMENSION_LABELS: Record<string, string> = {
  answer_quality: "Qualita risposta",
  answer_clarity: "Chiarezza",
  answer_completeness: "Completezza",
  citations_relevance: "Pertinenza citazioni",
  citations_accuracy: "Accuratezza citazioni",
  balance_perception: "Bilanciamento percepito",
  balance_fairness: "Equita",
};

export default function ValutazionePage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();
  const [data, setData] = useState<EvaluationDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [surveyModalOpen, setSurveyModalOpen] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await getDashboardData();
      setData(result);
    } catch (err) {
      setError("Errore nel caricamento dei dati di valutazione");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleExportCsv = () => {
    window.open(getExportCsvUrl(), "_blank");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-white dark:bg-zinc-950">
      <Sidebar isCollapsed={isCollapsed} onToggle={toggle} isMobile={isMobile} isMobileOpen={isMobileOpen} onCloseMobile={closeMobile} />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3 px-4 sm:px-6 h-14">
            <MobileMenuButton onClick={toggle} />
            <h1 className="text-base font-semibold whitespace-nowrap">Valutazione</h1>
            <div className="flex gap-1.5 md:gap-2 ml-auto shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={loadData}
                disabled={isLoading}
                className="h-8 px-2 md:px-3"
              >
                <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
                <span className="hidden md:inline ml-1">Aggiorna</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportCsv}
                disabled={!data || data.total_chats === 0}
                className="h-8 px-2 md:px-3 hidden sm:flex"
              >
                <Download className="w-4 h-4" />
                <span className="hidden md:inline ml-1">Esporta CSV</span>
              </Button>
              <Button size="sm" onClick={() => setSurveyModalOpen(true)} className="h-8 px-2 md:px-3">
                <ClipboardCheck className="w-4 h-4" />
                <span className="hidden sm:inline ml-1">Nuova Valutazione</span>
              </Button>
            </div>
          </div>
        </header>

        {/* Content */}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
              <p className="text-muted-foreground">Caricamento dati di valutazione...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-red-500">
              <AlertCircle className="w-10 h-10" />
              <p>{error}</p>
              <Button variant="outline" onClick={loadData}>
                Riprova
              </Button>
            </div>
          </div>
        ) : data && data.total_chats === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-gray-500">
              <BarChart3 className="w-12 h-12 opacity-30" />
              <p className="text-lg font-medium">Nessuna conversazione disponibile</p>
              <p className="text-sm">Inizia ad usare il sistema per generare dati di valutazione.</p>
            </div>
          </div>
        ) : data ? (
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex-1 flex flex-col min-h-0"
          >
            <TabsList className="mx-4 md:mx-8 mt-4 grid w-auto grid-cols-4 h-10 shrink-0">
              <TabsTrigger value="overview" className="text-xs md:text-sm gap-1 md:gap-1.5">
                <BarChart3 className="w-4 h-4" />
                <span className="hidden sm:inline">Panoramica</span>
              </TabsTrigger>
              <TabsTrigger value="automated" className="text-xs md:text-sm gap-1 md:gap-1.5">
                <Target className="w-4 h-4" />
                <span className="hidden sm:inline">Metriche</span>
              </TabsTrigger>
              <TabsTrigger value="human" className="text-xs md:text-sm gap-1 md:gap-1.5">
                <Users className="w-4 h-4" />
                <span className="hidden sm:inline">A/B</span>
              </TabsTrigger>
              <TabsTrigger value="details" className="text-xs md:text-sm gap-1 md:gap-1.5">
                <FileText className="w-4 h-4" />
                <span className="hidden sm:inline">Dettaglio</span>
              </TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-y-auto px-4 md:px-8 py-4 md:py-6">
              <TabsContent value="overview" className="mt-0">
                <OverviewTab data={data} />
              </TabsContent>
              <TabsContent value="automated" className="mt-0">
                <AutomatedTab data={data} />
              </TabsContent>
              <TabsContent value="human" className="mt-0">
                <HumanTab data={data} />
              </TabsContent>
              <TabsContent value="details" className="mt-0">
                <DetailsTab data={data} />
              </TabsContent>
            </div>
          </Tabs>
        ) : null}
      </main>

      <SurveyModal
        isOpen={surveyModalOpen}
        onClose={() => {
          setSurveyModalOpen(false);
          loadData();
        }}
      />
    </div>
  );
}

/* ─── Overview Tab ─── */

function OverviewTab({ data }: { data: EvaluationDashboardData }) {
  const agg = data.automated_aggregate;
  const ab = data.ab_comparison;
  const human = data.human_aggregate;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 md:gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {data.total_chats}
            </div>
            <div className="text-sm text-muted-foreground">Conversazioni totali</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-blue-600">
              {data.total_evaluated}
            </div>
            <div className="text-sm text-muted-foreground">Valutate (A/B blind)</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-purple-600">
              {data.total_simple_rated}
            </div>
            <div className="text-sm text-muted-foreground">Valutate (Likert)</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-emerald-600">
              {ab ? `${(ab.system_win_rate * 100).toFixed(0)}%` : "—"}
            </div>
            <div className="text-sm text-muted-foreground">Win rate sistema</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-amber-600">
              {human ? `${human.recommendation_rate.toFixed(0)}%` : "—"}
            </div>
            <div className="text-sm text-muted-foreground">Tasso raccomandazione</div>
          </CardContent>
        </Card>
      </div>

      {/* Automated metrics cards */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Metriche Automatiche
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 md:gap-4">
          <MetricCard
            label="Copertura Partitica"
            value={agg.avg_party_coverage}
            ci={agg.ci_party_coverage}
            icon={<Users className="w-4 h-4" />}
            description="Gruppi parlamentari citati su 10 totali"
          />
          <MetricCard
            label="Integrità Citazioni"
            value={agg.avg_citation_integrity}
            ci={agg.ci_citation_integrity}
            icon={<Quote className="w-4 h-4" />}
            description="Citazioni con testo sorgente valido"
          />
          <MetricCard
            label="Fedeltà Testuale"
            value={agg.avg_verbatim_match}
            ci={agg.ci_verbatim_match}
            icon={<BarChart2 className="w-4 h-4" />}
            description="Citazioni corrispondenti al testo originale"
          />
          <MetricCard
            label="Autorevolezza"
            value={agg.avg_authority_utilization}
            ci={agg.ci_authority_utilization}
            icon={<Award className="w-4 h-4" />}
            description="Score medio degli esperti citati"
          />
          <MetricCard
            label="Completezza"
            value={agg.avg_response_completeness}
            ci={agg.ci_response_completeness}
            icon={<FileText className="w-4 h-4" />}
            description="Gruppi menzionati nel testo della risposta"
          />
        </div>
      </div>

      {/* A/B Win Rate */}
      {ab && ab.total_evaluations > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-500" />
              Preferenza Complessiva — Valutazione Blind A/B
            </CardTitle>
          </CardHeader>
          <CardContent>
            <WinRateChart
              systemWinRate={ab.system_win_rate}
              baselineWinRate={ab.baseline_win_rate}
              tieRate={ab.tie_rate}
              totalEvaluations={ab.total_evaluations}
            />
          </CardContent>
        </Card>
      )}

      {/* A/B Comparison per dimension */}
      {ab && ab.total_evaluations > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              ParliamentRAG vs Baseline RAG — Punteggi Medi per Dimensione
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ABComparisonChart
              items={AB_DIMENSIONS.map((dim) => ({
                label: DIMENSION_LABELS[dim] || dim,
                systemValue: ab.system_avg_ratings[dim] || 0,
                baselineValue: ab.baseline_avg_ratings[dim] || 0,
              }))}
            />
          </CardContent>
        </Card>
      )}

      {/* Overall satisfaction comparison */}
      {ab && ab.total_evaluations > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardContent className="p-6 text-center">
              <div className="text-sm text-muted-foreground mb-2">Soddisfazione Media Sistema</div>
              <div className="text-4xl font-bold text-blue-600">
                {ab.system_avg_overall.toFixed(2)}
              </div>
              <div className="text-sm text-muted-foreground">/5</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-6 text-center">
              <div className="text-sm text-muted-foreground mb-2">Soddisfazione Media Baseline</div>
              <div className="text-4xl font-bold text-amber-600">
                {ab.baseline_avg_overall.toFixed(2)}
              </div>
              <div className="text-sm text-muted-foreground">/5</div>
            </CardContent>
          </Card>
        </div>
      )}

      {!ab && (
        <Card>
          <CardContent className="p-8 text-center text-gray-500">
            <Users className="w-12 h-12 opacity-30 mx-auto mb-3" />
            <p className="text-lg font-medium">Nessuna valutazione A/B disponibile</p>
            <p className="text-sm mt-1">
              Esegui query con baseline e usa &quot;Nuova Valutazione&quot; per confrontare le risposte.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ─── Automated Tab ─── */

function AutomatedTab({ data }: { data: EvaluationDashboardData }) {
  const agg = data.automated_aggregate;

  const metrics = [
    {
      label: "Copertura Partitica (Party Coverage)",
      value: agg.avg_party_coverage,
      ci: agg.ci_party_coverage,
      description:
        "Percentuale di gruppi parlamentari rappresentati nelle citazioni (target: 100%)",
      format: "percent" as const,
    },
    {
      label: "Integrita Citazioni (Citation Integrity)",
      value: agg.avg_citation_integrity,
      ci: agg.ci_citation_integrity,
      description:
        "Percentuale di citazioni con estrazione verbatim valida",
      format: "percent" as const,
    },
    {
      label: "Verbatim Match",
      value: agg.avg_verbatim_match,
      ci: agg.ci_verbatim_match,
      description:
        "Percentuale di citazioni il cui testo e presente verbatim nel chunk sorgente",
      format: "percent" as const,
    },
    {
      label: "Utilizzo Autorevolezza (Authority Utilization)",
      value: agg.avg_authority_utilization,
      ci: agg.ci_authority_utilization,
      description:
        "Media del punteggio di autorevolezza degli esperti citati",
      format: "percent" as const,
    },
    {
      label: "Discriminazione Autorevolezza (Authority Discrimination)",
      value: agg.avg_authority_discrimination,
      ci: agg.ci_authority_discrimination,
      description:
        "Deviazione standard dei punteggi di autorevolezza (valori alti = maggiore selettivita)",
      format: "decimal" as const,
    },
    {
      label: "Completezza Risposta (Response Completeness)",
      value: agg.avg_response_completeness,
      ci: agg.ci_response_completeness,
      description:
        "Percentuale di sezioni per-partito presenti nella risposta",
      format: "percent" as const,
    },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Metriche Automatiche
        </h2>
        <p className="text-sm text-muted-foreground">
          Calcolate da {agg.total_chats} conversazioni
        </p>
      </div>

      <Card>
        <CardContent className="p-6">
          <HorizontalBarChart
            items={metrics
              .filter((m) => m.format === "percent")
              .map((m) => ({
                label: m.label,
                value: m.value,
                ci: m.ci,
              }))}
          />
        </CardContent>
      </Card>

      {/* Detailed cards */}
      <div className="space-y-4">
        {metrics.map((m) => (
          <Card key={m.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">
                    {m.label}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {m.description}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold font-mono">
                    {m.format === "decimal"
                      ? m.value.toFixed(3)
                      : `${(m.value * 100).toFixed(1)}%`}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {m.format === "decimal"
                      ? `IC 95%: [${m.ci[0].toFixed(3)}, ${m.ci[1].toFixed(3)}]`
                      : `IC 95%: [${(m.ci[0] * 100).toFixed(1)}%, ${(m.ci[1] * 100).toFixed(1)}%]`}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ─── Human Tab (A/B Comparison) ─── */

function HumanTab({ data }: { data: EvaluationDashboardData }) {
  const ab = data.ab_comparison;
  const human = data.human_aggregate;

  if (!ab || ab.total_evaluations === 0) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col items-center justify-center h-60 text-gray-500">
          <Users className="w-12 h-12 opacity-30 mb-3" />
          <p className="text-lg font-medium">
            Nessuna valutazione A/B disponibile
          </p>
          <p className="text-sm mt-1">
            Usa il bottone &quot;Nuova Valutazione&quot; per iniziare.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Confronto A/B Cieco
          </h2>
          <p className="text-sm text-muted-foreground">
            {ab.total_evaluations} valutazioni blind — risultati de-blindati
          </p>
        </div>
        {human && (
          <Badge
            variant="outline"
            className={cn(
              "text-sm px-3 py-1",
              human.recommendation_rate >= 70
                ? "border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400"
                : "border-amber-300 text-amber-700 dark:border-amber-700 dark:text-amber-400"
            )}
          >
            <ThumbsUp className="w-4 h-4 mr-1" />
            {human.recommendation_rate.toFixed(0)}% raccomanderebbe
          </Badge>
        )}
      </div>

      {/* Win rate */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-500" />
            Preferenza Complessiva
          </CardTitle>
        </CardHeader>
        <CardContent>
          <WinRateChart
            systemWinRate={ab.system_win_rate}
            baselineWinRate={ab.baseline_win_rate}
            tieRate={ab.tie_rate}
            totalEvaluations={ab.total_evaluations}
          />
        </CardContent>
      </Card>

      {/* Per-dimension comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Punteggi Medi per Dimensione (1-5)</CardTitle>
        </CardHeader>
        <CardContent>
          <ABComparisonChart
            items={AB_DIMENSIONS.map((dim) => ({
              label: DIMENSION_LABELS[dim] || dim,
              systemValue: ab.system_avg_ratings[dim] || 0,
              baselineValue: ab.baseline_avg_ratings[dim] || 0,
            }))}
          />
        </CardContent>
      </Card>

      {/* Per-dimension preference breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Preferenza per Dimensione</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {AB_DIMENSIONS.map((dim) => {
            const prefs = ab.per_dimension_preference[dim];
            if (!prefs) return null;
            const total = (prefs.system || 0) + (prefs.baseline || 0) + (prefs.equal || 0);
            if (total === 0) return null;
            const sysPct = ((prefs.system || 0) / total) * 100;
            const basePct = ((prefs.baseline || 0) / total) * 100;
            const tiePct = ((prefs.equal || 0) / total) * 100;
            return (
              <div key={dim} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-700 dark:text-gray-300 font-medium">
                    {DIMENSION_LABELS[dim] || dim}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {prefs.system || 0}S / {prefs.equal || 0}= / {prefs.baseline || 0}B
                  </span>
                </div>
                <div className="flex items-center h-6 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800">
                  {sysPct > 0 && (
                    <div
                      className="h-full bg-blue-500"
                      style={{ width: `${sysPct}%` }}
                    />
                  )}
                  {tiePct > 0 && (
                    <div
                      className="h-full bg-gray-300 dark:bg-gray-600"
                      style={{ width: `${tiePct}%` }}
                    />
                  )}
                  {basePct > 0 && (
                    <div
                      className="h-full bg-amber-400"
                      style={{ width: `${basePct}%` }}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Overall satisfaction comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-6 text-center">
            <div className="text-sm text-muted-foreground mb-2">Soddisfazione Media Sistema</div>
            <div className="text-4xl font-bold text-blue-600">
              {ab.system_avg_overall.toFixed(2)}
            </div>
            <div className="text-sm text-muted-foreground">/5</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 text-center">
            <div className="text-sm text-muted-foreground mb-2">Soddisfazione Media Baseline</div>
            <div className="text-4xl font-bold text-amber-600">
              {ab.baseline_avg_overall.toFixed(2)}
            </div>
            <div className="text-sm text-muted-foreground">/5</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ─── Details Tab ─── */

function DetailsTab({ data }: { data: EvaluationDashboardData }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Dettaglio per Conversazione
        </h2>
        <p className="text-sm text-muted-foreground">
          {data.per_chat.length} conversazioni analizzate
        </p>
      </div>

      <div className="space-y-3">
        {data.per_chat.map((item) => (
          <ChatEvaluationRow
            key={item.chat_id}
            item={item}
            isExpanded={expandedId === item.chat_id}
            onToggle={() =>
              setExpandedId(
                expandedId === item.chat_id ? null : item.chat_id
              )
            }
          />
        ))}
      </div>
    </div>
  );
}

function ChatEvaluationRow({
  item,
  isExpanded,
  onToggle,
}: {
  item: CombinedEvaluation;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const m = item.automated;

  const miniMetrics = [
    { label: "Copertura", value: m.party_coverage_score, color: "bg-blue-500" },
    { label: "Citazioni", value: m.citation_integrity_score, color: "bg-emerald-500" },
    { label: "Verbatim", value: m.verbatim_match_score, color: "bg-purple-500" },
    { label: "Autorevolezza", value: m.authority_utilization, color: "bg-amber-500" },
    { label: "Completezza", value: m.response_completeness, color: "bg-indigo-500" },
  ];

  const formatDate = (ts: string) => {
    try {
      return new Date(ts).toLocaleDateString("it-IT", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return ts;
    }
  };

  return (
    <Card className="overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-900 dark:text-gray-100 line-clamp-1">
              {item.chat_query}
            </p>
            <div className="flex items-center gap-3 mt-2">
              <span className="text-xs text-muted-foreground">
                {formatDate(item.timestamp)}
              </span>
              <MiniMetricBars values={miniMetrics} />
              {item.human && (
                <Badge
                  variant="secondary"
                  className="text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                >
                  Valutata A/B
                </Badge>
              )}
              {item.human_simple && (
                <Badge
                  variant="secondary"
                  className="text-xs bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                >
                  <BarChart2 className="w-3 h-3 mr-1" />
                  Likert
                </Badge>
              )}
            </div>
          </div>
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400 shrink-0" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400 shrink-0" />
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="border-t px-3 md:px-4 py-4 bg-gray-50 dark:bg-gray-900/30">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
            {/* Automated metrics */}
            <div>
              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Metriche Automatiche
              </h4>
              <div className="space-y-2">
                {[
                  { label: "Copertura partitica", value: m.party_coverage_score, detail: `${m.parties_represented}/${m.parties_total} partiti`, format: "percent" as const },
                  { label: "Integrita citazioni", value: m.citation_integrity_score, detail: `${m.citations_valid}/${m.citations_total} valide`, format: "percent" as const },
                  { label: "Verbatim match", value: m.verbatim_match_score, detail: `${m.verbatim_match_count} corrispondenze`, format: "percent" as const },
                  { label: "Autorevolezza", value: m.authority_utilization, detail: `${m.experts_count} esperti`, format: "percent" as const },
                  { label: "Discriminazione autorevolezza", value: m.authority_discrimination, detail: "std dev", format: "decimal" as const },
                  { label: "Completezza", value: m.response_completeness, detail: "", format: "percent" as const },
                ].map((row) => (
                  <div key={row.label} className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
                    <div className="flex items-center gap-2">
                      {row.detail && (
                        <span className="text-xs text-muted-foreground">{row.detail}</span>
                      )}
                      <span className="font-mono font-medium w-16 text-right">
                        {row.format === "decimal"
                          ? row.value.toFixed(3)
                          : `${(row.value * 100).toFixed(1)}%`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Party breakdown */}
              {Object.keys(m.party_breakdown).length > 0 && (
                <div className="mt-4">
                  <h5 className="text-xs font-semibold text-gray-500 dark:text-gray-500 mb-2 uppercase">
                    Distribuzione per partito
                  </h5>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(m.party_breakdown)
                      .sort(([, a], [, b]) => b - a)
                      .map(([party, count]) => (
                        <Badge key={party} variant="outline" className="text-xs">
                          {party}: {count}
                        </Badge>
                      ))}
                  </div>
                </div>
              )}
            </div>

            {/* Human evaluation metrics */}
            <div>
              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Valutazione Umana
              </h4>
              {item.human ? (
                <div className="space-y-3">
                  <div className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase mb-1">
                    A/B Blind
                  </div>
                  {AB_DIMENSIONS.map((dim) => {
                    const rating = (item.human as any)[dim] as ABRating | undefined;
                    if (!rating) return null;
                    return (
                      <div key={dim} className="text-sm">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-gray-600 dark:text-gray-400">
                            {DIMENSION_LABELS[dim] || dim}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            Pref: {rating.preference === "A" ? "A" : rating.preference === "B" ? "B" : "="}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          <span className="w-6 text-blue-600">A:</span>
                          <div className="flex gap-0.5">
                            {Array.from({ length: 5 }, (_, i) => (
                              <div
                                key={i}
                                className={cn(
                                  "w-2 h-2 rounded-full",
                                  i < rating.rating_a
                                    ? "bg-blue-400"
                                    : "bg-gray-200 dark:bg-gray-700"
                                )}
                              />
                            ))}
                          </div>
                          <span className="font-mono">{rating.rating_a}/5</span>
                          <span className="mx-1 text-gray-300">|</span>
                          <span className="w-6 text-amber-600">B:</span>
                          <div className="flex gap-0.5">
                            {Array.from({ length: 5 }, (_, i) => (
                              <div
                                key={i}
                                className={cn(
                                  "w-2 h-2 rounded-full",
                                  i < rating.rating_b
                                    ? "bg-amber-400"
                                    : "bg-gray-200 dark:bg-gray-700"
                                )}
                              />
                            ))}
                          </div>
                          <span className="font-mono">{rating.rating_b}/5</span>
                        </div>
                      </div>
                    );
                  })}

                  <div className="mt-2 pt-2 border-t text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Soddisfazione A</span>
                      <span className="font-mono">{item.human.overall_satisfaction_a}/5</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Soddisfazione B</span>
                      <span className="font-mono">{item.human.overall_satisfaction_b}/5</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Preferenza</span>
                      <span className="font-semibold">{item.human.overall_preference}</span>
                    </div>
                  </div>

                  {item.human.would_recommend && (
                    <div className="mt-2 flex items-center gap-1 text-emerald-600 text-sm">
                      <ThumbsUp className="w-3 h-3" />
                      <span>Raccomanderebbe il sistema</span>
                    </div>
                  )}

                  {item.human.feedback_positive && (
                    <div className="mt-3 p-2 bg-emerald-50 dark:bg-emerald-950/30 rounded text-sm text-emerald-800 dark:text-emerald-300">
                      <span className="font-medium">Positivo: </span>
                      {item.human.feedback_positive}
                    </div>
                  )}
                  {item.human.feedback_improvement && (
                    <div className="mt-2 p-2 bg-amber-50 dark:bg-amber-950/30 rounded text-sm text-amber-800 dark:text-amber-300">
                      <span className="font-medium">Da migliorare: </span>
                      {item.human.feedback_improvement}
                    </div>
                  )}
                </div>
              ) : item.human_simple ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-purple-600 dark:text-purple-400 uppercase mb-1">
                    <BarChart2 className="w-3 h-3" />
                    Likert 1-5
                  </div>
                  {(Object.keys(SIMPLE_DIMENSION_LABELS) as SimpleDimension[]).map((dim) => {
                    const score = item.human_simple![dim] as number;
                    return (
                      <div key={dim} className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">
                          {SIMPLE_DIMENSION_LABELS[dim]}
                        </span>
                        <div className="flex items-center gap-2">
                          <div className="flex gap-0.5">
                            {Array.from({ length: 5 }, (_, i) => (
                              <div
                                key={i}
                                className={cn(
                                  "w-2 h-2 rounded-full",
                                  i < score
                                    ? "bg-purple-400"
                                    : "bg-gray-200 dark:bg-gray-700"
                                )}
                              />
                            ))}
                          </div>
                          <span className="font-mono text-xs w-6 text-right">{score}/5</span>
                        </div>
                      </div>
                    );
                  })}
                  {item.human_simple.feedback && (
                    <div className="mt-2 p-2 bg-purple-50 dark:bg-purple-950/30 rounded text-sm text-purple-800 dark:text-purple-300">
                      <span className="font-medium">Feedback: </span>
                      {item.human_simple.feedback}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-32 text-gray-400">
                  <CheckCircle2 className="w-8 h-8 opacity-30 mb-2" />
                  <p className="text-sm">Non ancora valutata</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
