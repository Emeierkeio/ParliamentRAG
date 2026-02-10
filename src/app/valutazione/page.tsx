"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { SurveyModal } from "@/components/survey/SurveyModal";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  RadarChart,
  HorizontalBarChart,
  ScoreDistribution,
  MetricCard,
  MiniMetricBars,
} from "@/components/evaluation/EvaluationCharts";
import { getDashboardData, getExportCsvUrl } from "@/lib/evaluation-api";
import type { EvaluationDashboardData, CombinedEvaluation } from "@/types/evaluation";
import { SURVEY_QUESTIONS } from "@/types/survey";
import {
  BarChart3,
  Users,
  Quote,
  Scale,
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
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function ValutazionePage() {
  const { isCollapsed, toggle } = useSidebar();
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
      <Sidebar isCollapsed={isCollapsed} onToggle={toggle} />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <div className="border-b px-8 py-5 bg-background flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <ClipboardCheck className="w-6 h-6 text-blue-600" />
              Valutazione Sistema
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Framework di valutazione scientifica — metriche automatiche e umane
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={isLoading}
            >
              <RefreshCw className={cn("w-4 h-4 mr-1", isLoading && "animate-spin")} />
              Aggiorna
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCsv}
              disabled={!data || data.total_chats === 0}
            >
              <Download className="w-4 h-4 mr-1" />
              Esporta CSV
            </Button>
            <Button size="sm" onClick={() => setSurveyModalOpen(true)}>
              <ClipboardCheck className="w-4 h-4 mr-1" />
              Nuova Valutazione
            </Button>
          </div>
        </div>

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
            <TabsList className="mx-8 mt-4 grid w-auto grid-cols-4 h-10 shrink-0">
              <TabsTrigger value="overview" className="text-sm gap-1.5">
                <BarChart3 className="w-4 h-4" />
                Panoramica
              </TabsTrigger>
              <TabsTrigger value="automated" className="text-sm gap-1.5">
                <Target className="w-4 h-4" />
                Metriche Automatiche
              </TabsTrigger>
              <TabsTrigger value="human" className="text-sm gap-1.5">
                <Users className="w-4 h-4" />
                Valutazioni Umane
              </TabsTrigger>
              <TabsTrigger value="details" className="text-sm gap-1.5">
                <FileText className="w-4 h-4" />
                Dettaglio Chat
              </TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-y-auto px-8 py-6">
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
  const human = data.human_aggregate;
  const bl = data.baseline;

  // Radar metrics: full system (0-1 scale)
  const radarMetrics = [
    agg.avg_party_coverage,
    agg.avg_citation_integrity,
    agg.avg_balance_score,
    agg.avg_authority_utilization,
    agg.avg_response_completeness,
  ];
  const radarLabels = [
    "Copertura",
    "Citazioni",
    "Bilanciamento",
    "Autorevolezza",
    "Completezza",
  ];

  // Baseline metrics for radar comparison
  const baselineRadar = [
    bl.party_coverage,
    bl.citation_integrity,
    bl.balance_score,
    bl.authority_utilization,
    bl.response_completeness,
  ];

  // Improvement deltas
  const deltas = [
    { label: "Copertura", system: agg.avg_party_coverage, baseline: bl.party_coverage },
    { label: "Citazioni", system: agg.avg_citation_integrity, baseline: bl.citation_integrity },
    { label: "Bilanciamento", system: agg.avg_balance_score, baseline: bl.balance_score },
    { label: "Autorevolezza", system: agg.avg_authority_utilization, baseline: bl.authority_utilization },
    { label: "Completezza", system: agg.avg_response_completeness, baseline: bl.response_completeness },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
            <div className="text-sm text-muted-foreground">Valutate (umane)</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-emerald-600">
              {human ? `${human.recommendation_rate.toFixed(0)}%` : "—"}
            </div>
            <div className="text-sm text-muted-foreground">Tasso raccomandazione</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-amber-600">
              {human ? human.avg_overall_satisfaction.toFixed(2) : "—"}
            </div>
            <div className="text-sm text-muted-foreground">Soddisfazione media</div>
          </CardContent>
        </Card>
      </div>

      {/* Automated metrics cards */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Metriche Automatiche
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <MetricCard
            label="Copertura Partitica"
            value={agg.avg_party_coverage}
            ci={agg.ci_party_coverage}
            icon={<Users className="w-4 h-4" />}
          />
          <MetricCard
            label="Integrità Citazioni"
            value={agg.avg_citation_integrity}
            ci={agg.ci_citation_integrity}
            icon={<Quote className="w-4 h-4" />}
          />
          <MetricCard
            label="Bilanciamento"
            value={agg.avg_balance_score}
            ci={agg.ci_balance_score}
            icon={<Scale className="w-4 h-4" />}
          />
          <MetricCard
            label="Autorevolezza"
            value={agg.avg_authority_utilization}
            ci={agg.ci_authority_utilization}
            icon={<Award className="w-4 h-4" />}
          />
          <MetricCard
            label="Completezza"
            value={agg.avg_response_completeness}
            ci={agg.ci_response_completeness}
            icon={<FileText className="w-4 h-4" />}
          />
        </div>
      </div>

      {/* Radar Chart: System vs Baseline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            ParliamentRAG vs Naive RAG — Profilo Multi-Dimensionale
          </CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center">
          <RadarChart
            metrics={radarMetrics}
            labels={radarLabels}
            secondaryMetrics={baselineRadar}
            secondaryLabel={bl.label}
            size={350}
          />
        </CardContent>
      </Card>

      {/* Improvement over baseline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Miglioramento rispetto alla Baseline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {deltas.map((d) => {
              const improvement = d.system - d.baseline;
              const improvementPct = d.baseline > 0
                ? ((improvement / d.baseline) * 100).toFixed(0)
                : "—";
              return (
                <div key={d.label} className="flex items-center gap-4">
                  <span className="w-28 text-sm text-gray-600 dark:text-gray-400">
                    {d.label}
                  </span>
                  <div className="flex-1 flex items-center gap-2">
                    {/* Baseline bar */}
                    <div className="flex-1 relative h-6 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="absolute h-full rounded-full bg-amber-300/50 dark:bg-amber-700/30"
                        style={{ width: `${d.baseline * 100}%` }}
                      />
                      <div
                        className="absolute h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500"
                        style={{ width: `${d.system * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="w-24 text-right">
                    <span className={cn(
                      "text-sm font-semibold",
                      improvement > 0 ? "text-emerald-600" : improvement < 0 ? "text-red-600" : "text-gray-500"
                    )}>
                      {improvement > 0 ? "+" : ""}{(improvement * 100).toFixed(1)}pp
                    </span>
                    <span className="text-xs text-muted-foreground ml-1">
                      ({improvement > 0 ? "+" : ""}{improvementPct}%)
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-4 mt-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-gradient-to-r from-blue-500 to-indigo-500" />
              ParliamentRAG (sistema completo)
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-amber-300/50 dark:bg-amber-700/30" />
              {bl.label}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Automated Tab ─── */

function AutomatedTab({ data }: { data: EvaluationDashboardData }) {
  const agg = data.automated_aggregate;
  const bl = data.baseline;

  const metrics = [
    {
      label: "Copertura Partitica (Party Coverage)",
      value: agg.avg_party_coverage,
      ci: agg.ci_party_coverage,
      baseline: bl.party_coverage,
      description:
        "Percentuale di gruppi parlamentari rappresentati nelle citazioni (target: 100%)",
    },
    {
      label: "Integrità Citazioni (Citation Integrity)",
      value: agg.avg_citation_integrity,
      ci: agg.ci_citation_integrity,
      baseline: bl.citation_integrity,
      description:
        "Percentuale di citazioni con estrazione verbatim valida",
    },
    {
      label: "Bilanciamento Politico (Balance Score)",
      value: agg.avg_balance_score,
      ci: agg.ci_balance_score,
      baseline: bl.balance_score,
      description:
        "Equilibrio tra maggioranza e opposizione (1 = perfetto bilanciamento)",
    },
    {
      label: "Utilizzo Autorevolezza (Authority Utilization)",
      value: agg.avg_authority_utilization,
      ci: agg.ci_authority_utilization,
      baseline: bl.authority_utilization,
      description:
        "Media del punteggio di autorevolezza degli esperti citati",
    },
    {
      label: "Completezza Risposta (Response Completeness)",
      value: agg.avg_response_completeness,
      ci: agg.ci_response_completeness,
      baseline: bl.response_completeness,
      description:
        "Percentuale di sezioni per-partito presenti nella risposta",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Metriche Automatiche
          </h2>
          <p className="text-sm text-muted-foreground">
            Calcolate da {agg.total_chats} conversazioni — confronto con baseline Naive RAG
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="p-6">
          <HorizontalBarChart
            items={metrics.map((m) => ({
              label: m.label,
              value: m.value,
              ci: m.ci,
            }))}
          />
        </CardContent>
      </Card>

      {/* Detailed cards with baseline comparison */}
      <div className="space-y-4">
        {metrics.map((m) => {
          const delta = m.value - m.baseline;
          const deltaPct = m.baseline > 0 ? ((delta / m.baseline) * 100).toFixed(0) : "—";
          return (
            <Card key={m.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
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
                      {(m.value * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-muted-foreground">
                      IC 95%: [{(m.ci[0] * 100).toFixed(1)}%, {(m.ci[1] * 100).toFixed(1)}%]
                    </div>
                  </div>
                </div>
                {/* Baseline comparison */}
                <div className="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                  <span className="text-xs text-muted-foreground w-20">Baseline:</span>
                  <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-400/60"
                      style={{ width: `${m.baseline * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground w-12 text-right">
                    {(m.baseline * 100).toFixed(0)}%
                  </span>
                  <span className={cn(
                    "text-xs font-semibold w-16 text-right",
                    delta > 0 ? "text-emerald-600" : delta < 0 ? "text-red-600" : "text-gray-500"
                  )}>
                    {delta > 0 ? "+" : ""}{(delta * 100).toFixed(1)}pp
                  </span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Human Tab ─── */

function HumanTab({ data }: { data: EvaluationDashboardData }) {
  const human = data.human_aggregate;

  if (!human || human.total_surveys === 0) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col items-center justify-center h-60 text-gray-500">
          <Users className="w-12 h-12 opacity-30 mb-3" />
          <p className="text-lg font-medium">
            Nessuna valutazione umana disponibile
          </p>
          <p className="text-sm mt-1">
            Usa il bottone &quot;Nuova Valutazione&quot; per iniziare.
          </p>
        </div>
      </div>
    );
  }

  // Map question IDs to their average and distribution
  const questionMetrics: {
    id: string;
    label: string;
    category: string;
    avg: number;
    distribution: Record<number, number>;
  }[] = [];

  const avgMap: Record<string, number> = {
    answer_quality: human.avg_answer_quality,
    answer_clarity: human.avg_answer_clarity,
    answer_completeness: human.avg_answer_completeness,
    citations_relevance: human.avg_citations_relevance,
    citations_accuracy: human.avg_citations_accuracy,
    balance_perception: human.avg_balance_perception,
    balance_fairness: human.avg_balance_fairness,
    compass_usefulness: human.avg_compass_usefulness,
    experts_usefulness: human.avg_experts_usefulness,
    overall_satisfaction: human.avg_overall_satisfaction,
  };

  for (const q of SURVEY_QUESTIONS) {
    questionMetrics.push({
      id: q.id,
      label: q.question,
      category: q.category,
      avg: avgMap[q.id] || 0,
      distribution: human.scores_distribution[q.id] || { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 },
    });
  }

  // Group by category
  const categories = questionMetrics.reduce(
    (acc, q) => {
      if (!acc[q.category]) acc[q.category] = [];
      acc[q.category].push(q);
      return acc;
    },
    {} as Record<string, typeof questionMetrics>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Valutazioni Umane
          </h2>
          <p className="text-sm text-muted-foreground">
            {human.total_surveys} valutazioni raccolte — Tasso raccomandazione:{" "}
            {human.recommendation_rate.toFixed(0)}%
          </p>
        </div>
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
      </div>

      {/* Average scores as horizontal bars */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Punteggi Medi per Domanda</CardTitle>
        </CardHeader>
        <CardContent>
          <HorizontalBarChart
            items={questionMetrics.map((q) => ({
              label: q.label.length > 50 ? q.label.slice(0, 47) + "..." : q.label,
              value: q.avg / 5,
              max: 1,
            }))}
            colorClass="from-amber-400 to-amber-600"
          />
        </CardContent>
      </Card>

      {/* Distributions by category */}
      {Object.entries(categories).map(([category, questions]) => (
        <Card key={category}>
          <CardHeader>
            <CardTitle className="text-base">{category}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {questions.map((q) => (
              <ScoreDistribution
                key={q.id}
                label={q.label}
                distribution={q.distribution}
                average={q.avg}
              />
            ))}
          </CardContent>
        </Card>
      ))}
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
    { label: "Bilanciam.", value: m.balance_score, color: "bg-purple-500" },
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
                  className="text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                >
                  Valutata: {item.human.overall_satisfaction}/5
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
        <div className="border-t px-4 py-4 bg-gray-50 dark:bg-gray-900/30">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Automated metrics */}
            <div>
              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Metriche Automatiche
              </h4>
              <div className="space-y-2">
                {[
                  { label: "Copertura partitica", value: m.party_coverage_score, detail: `${m.parties_represented}/${m.parties_total} partiti` },
                  { label: "Integrità citazioni", value: m.citation_integrity_score, detail: `${m.citations_valid}/${m.citations_total} valide` },
                  { label: "Bilanciamento", value: m.balance_score, detail: `Magg. ${m.maggioranza_pct.toFixed(0)}% / Opp. ${m.opposizione_pct.toFixed(0)}%` },
                  { label: "Autorevolezza", value: m.authority_utilization, detail: `${m.experts_count} esperti` },
                  { label: "Completezza", value: m.response_completeness, detail: "" },
                ].map((row) => (
                  <div key={row.label} className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
                    <div className="flex items-center gap-2">
                      {row.detail && (
                        <span className="text-xs text-muted-foreground">{row.detail}</span>
                      )}
                      <span className="font-mono font-medium w-16 text-right">
                        {(row.value * 100).toFixed(1)}%
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

            {/* Human metrics */}
            <div>
              <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Valutazione Umana
              </h4>
              {item.human ? (
                <div className="space-y-2">
                  {[
                    { label: "Qualità risposta", value: item.human.answer_quality },
                    { label: "Chiarezza", value: item.human.answer_clarity },
                    { label: "Completezza", value: item.human.answer_completeness },
                    { label: "Pertinenza citazioni", value: item.human.citations_relevance },
                    { label: "Accuratezza citazioni", value: item.human.citations_accuracy },
                    { label: "Bilanciamento percepito", value: item.human.balance_perception },
                    { label: "Equità", value: item.human.balance_fairness },
                    { label: "Utilità bussola", value: item.human.compass_usefulness },
                    { label: "Utilità esperti", value: item.human.experts_usefulness },
                    { label: "Soddisfazione", value: item.human.overall_satisfaction },
                  ].map((row) => (
                    <div key={row.label} className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
                      <div className="flex items-center gap-1">
                        {Array.from({ length: 5 }, (_, i) => (
                          <div
                            key={i}
                            className={cn(
                              "w-2 h-2 rounded-full",
                              i < row.value
                                ? "bg-amber-400"
                                : "bg-gray-200 dark:bg-gray-700"
                            )}
                          />
                        ))}
                        <span className="ml-1 text-xs font-mono">{row.value}/5</span>
                      </div>
                    </div>
                  ))}

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
