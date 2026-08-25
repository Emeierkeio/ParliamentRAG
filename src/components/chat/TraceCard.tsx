"use client";

/**
 * TraceCard — "dietro le quinte" della pipeline, in stile trace explorer.
 *
 * Tre viste sugli stessi dati registrati dal backend:
 * - Pipeline: waterfall temporale con barre agli offset reali; le fasi con
 *   chiamate LLM si aprono e mostrano le chiamate avvenute in quella
 *   finestra
 * - Chiamate LLM: elenco cronologico completo, ogni chiamata si apre su
 *   prompt (per ruolo), risposta, token e temperatura
 * - Citazioni: il registro del CitationRegistry — stato di ogni citazione,
 *   coerenza semantica, motivi di scarto, affermazioni senza fonte
 *
 * Solo durate, contatori e anteprime troncate: il testo integrale delle
 * evidenze resta nella risposta.
 */

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronRight, Cpu, Braces } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CitationLedgerEntry, LlmCall, RetrievalSampleItem, TraceData, TraceStage } from "@/types";

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1).replace(".", ",")} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s % 60)} s`;
}

function formatTokens(n: number | null | undefined): string {
  if (n == null) return "—";
  return n >= 10000 ? `${(n / 1000).toFixed(1).replace(".", ",")}k` : n.toLocaleString("it-IT");
}

function formatCost(v: number | null | undefined): string {
  if (v == null) return "—";
  const digits = v < 0.1 ? 3 : 2;
  return `$${v.toFixed(digits).replace(".", ",")}`;
}

/** Ordine e selezione delle voci info mostrate come dettaglio per stadio */
const INFO_KEYS: Record<string, string[]> = {
  commissions: ["matched"],
  retrieval: ["dense", "graph", "selected"],
  authority: ["speakers", "experts"],
  citations_preview: ["citations"],
  compass: ["groups"],
  generation: ["chars"],
  analyst: ["claims"],
  sectional: ["sections", "citations_bound"],
  integrator: ["citations_repaired"],
  surgeon: ["citations_inserted", "citations_failed"],
  verification: ["citations_verified"],
};

interface StageRow {
  stage: TraceStage;
  start: number;
  children: { stage: TraceStage; start: number }[];
}

/** Offset reali quando presenti, cumulativi come fallback */
function layoutStages(trace: TraceData): StageRow[] {
  let cursor = 0;
  return (trace.stages ?? []).map((stage) => {
    const start = stage.at ?? cursor;
    cursor = start + (stage.ms ?? 0);
    let childCursor = start;
    const children = (stage.children ?? []).map((child) => {
      const childStart = child.at ?? childCursor;
      childCursor = childStart + (child.ms ?? 0);
      return { stage: child, start: childStart };
    });
    return { stage, start, children };
  });
}

/** Assegna ogni chiamata LLM alla fase (o sotto-fase) nella cui finestra temporale cade */
function assignCalls(rows: StageRow[], calls: LlmCall[]): Map<string, LlmCall[]> {
  const map = new Map<string, LlmCall[]>();
  const push = (key: string, call: LlmCall) => {
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(call);
  };
  for (const call of calls) {
    const t = call.t_offset_ms;

    // Il tag esplicito del backend vince: con bussola e generazione in
    // parallelo le finestre temporali si sovrappongono
    if (call.stage) {
      const row = rows.find((r) => r.stage.key === call.stage);
      let assigned = call.stage;
      if (row) {
        for (const { stage: child, start: cStart } of row.children) {
          const cEnd = cStart + (child.ms ?? 0);
          if (t >= cStart && t < cEnd) {
            assigned = child.key;
            break;
          }
        }
      }
      push(assigned, call);
      continue;
    }

    let assigned: string | null = null;
    for (const { stage, start, children } of rows) {
      const end = start + (stage.ms ?? 0);
      if (t >= start && t < end) {
        assigned = stage.key;
        for (const { stage: child, start: cStart } of children) {
          const cEnd = cStart + (child.ms ?? 0);
          if (t >= cStart && t < cEnd) {
            assigned = child.key;
            break;
          }
        }
        break;
      }
    }
    push(assigned ?? "other", call);
  }
  return map;
}

/* ------------------------------------------------------------------ */
/* Chiamata LLM: riga espandibile con prompt/risposta                  */
/* ------------------------------------------------------------------ */

function LlmCallRow({ call, index }: { call: LlmCall; index: number }) {
  const t = useTranslations("Trace");
  const [open, setOpen] = useState(false);
  const isEmb = call.endpoint === "embeddings";
  const Icon = isEmb ? Braces : Cpu;

  return (
    <div className={cn("rounded-md border border-border/50", open && "bg-muted/20")}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-2 py-1.5 text-left hover:bg-muted/40 rounded-md transition-colors"
      >
        <ChevronRight className={cn("h-3 w-3 shrink-0 text-muted-foreground/60 transition-transform", open && "rotate-90")} />
        <Icon className="h-3 w-3 shrink-0 text-primary/60" />
        <span className="text-[10px] font-mono text-foreground/80 bg-muted/70 rounded px-1 py-px shrink-0">
          {call.model ?? call.endpoint}
        </span>
        {call.error ? (
          <span className="text-[10px] text-destructive truncate">{t("callError")}</span>
        ) : (
          <span className="text-[10px] text-muted-foreground/70 truncate min-w-0">
            {isEmb
              ? `${call.inputs ?? 0} ${t("inputLabel")}`
              : `${call.messages?.length ?? 0} msg`}
          </span>
        )}
        <span className="ml-auto shrink-0 text-[10px] font-mono tabular-nums text-muted-foreground/80">
          {call.tokens?.total != null && (
            <span className="mr-2">{formatTokens(call.tokens.total)} tok</span>
          )}
          {formatMs(call.duration_ms)}
        </span>
      </button>

      {open && (
        <div className="px-2 pb-2 space-y-1.5">
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 px-1 text-[9.5px] font-mono text-muted-foreground/70">
            <span>t+{formatMs(call.t_offset_ms)}</span>
            {call.temperature != null && <span>temp {call.temperature}</span>}
            {call.tokens?.prompt != null && (
              <span>{formatTokens(call.tokens.prompt)} prompt · {formatTokens(call.tokens.completion)} completion</span>
            )}
            {call.cost_usd != null && <span>≈{formatCost(call.cost_usd)}</span>}
            {call.finish_reason && <span>{call.finish_reason}</span>}
          </div>

          {call.error && (
            <div className="rounded bg-destructive/10 border border-destructive/20 p-2 text-[10px] font-mono text-destructive whitespace-pre-wrap">
              {call.error}
            </div>
          )}

          {(call.messages ?? []).map((m, i) => (
            <div key={i} className="rounded bg-muted/50 p-2">
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-[9px] uppercase tracking-widest font-semibold text-muted-foreground/70">{m.role}</span>
                <span className="text-[9px] font-mono text-muted-foreground/50">{m.chars.toLocaleString("it-IT")} char</span>
              </div>
              <div className="text-[10px] font-mono text-foreground/70 whitespace-pre-wrap max-h-36 overflow-y-auto leading-relaxed">
                {m.preview}
              </div>
            </div>
          ))}

          {call.input_preview && (
            <div className="rounded bg-muted/50 p-2">
              <div className="text-[9px] uppercase tracking-widest font-semibold text-muted-foreground/70 mb-1">
                {t("inputLabel")} ({call.inputs})
              </div>
              <div className="text-[10px] font-mono text-foreground/70 whitespace-pre-wrap max-h-20 overflow-y-auto leading-relaxed">
                {call.input_preview}
              </div>
            </div>
          )}

          {call.response_preview != null && (
            <div className="rounded border border-primary/20 bg-primary/5 p-2">
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-[9px] uppercase tracking-widest font-semibold text-primary/70">{t("responseLabel")}</span>
                {call.response_chars != null && (
                  <span className="text-[9px] font-mono text-muted-foreground/50">{call.response_chars.toLocaleString("it-IT")} char</span>
                )}
              </div>
              <div className="text-[10px] font-mono text-foreground/70 whitespace-pre-wrap max-h-36 overflow-y-auto leading-relaxed">
                {call.response_preview}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Registro citazioni                                                  */
/* ------------------------------------------------------------------ */

const STATUS_STYLE: Record<string, string> = {
  resolved: "bg-green-600",
  in_text: "bg-primary/70",
  bound: "bg-primary/40",
  registered: "bg-muted-foreground/30",
  orphaned: "bg-amber-500",
  failed: "bg-destructive",
};

function LedgerRow({ entry }: { entry: CitationLedgerEntry }) {
  const t = useTranslations("Trace");
  let statusLabel: string;
  try {
    statusLabel = t(`status.${entry.status}` as Parameters<typeof t>[0]);
  } catch {
    statusLabel = entry.status;
  }
  return (
    <div className="flex items-start gap-2 py-1.5 border-b border-border/40 last:border-0">
      <span className={cn("mt-1 h-2 w-2 rounded-full shrink-0", STATUS_STYLE[entry.status] ?? "bg-muted-foreground/40")} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-[11px] text-foreground/85 truncate">{entry.speaker ?? "—"}</span>
          {entry.party && (
            <span className="text-[9px] uppercase tracking-wider text-muted-foreground/60 truncate">{entry.party}</span>
          )}
        </div>
        <div className="text-[9px] font-mono text-muted-foreground/50 truncate" title={entry.evidence_id}>
          {entry.evidence_id}
        </div>
        {entry.error && (
          <div className="text-[10px] text-destructive/80 mt-0.5">{entry.error}</div>
        )}
      </div>
      <div className="text-right shrink-0">
        <div className="text-[10px] font-medium text-foreground/70">{statusLabel}</div>
        {entry.coherence_score != null && (
          <div className="text-[9px] font-mono text-muted-foreground/60">
            {t("coherenceShort")} {entry.coherence_score.toFixed(2).replace(".", ",")}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* TraceCard                                                           */
/* ------------------------------------------------------------------ */

interface TraceCardProps {
  trace: TraceData;
}

export function TraceCard({ trace }: TraceCardProps) {
  const t = useTranslations("Trace");
  const [openStages, setOpenStages] = useState<Set<string>>(new Set());

  const rows = useMemo(() => layoutStages(trace), [trace]);
  const calls = trace.llm_calls ?? [];
  const callsByStage = useMemo(() => assignCalls(rows, calls), [rows, calls]);
  const report = trace.citations_report;

  const stageTokens = useMemo(() => {
    const m = new Map<string, number>();
    for (const [key, list] of callsByStage) {
      m.set(key, list.reduce((acc, c) => acc + (c.tokens?.total ?? 0), 0));
    }
    return m;
  }, [callsByStage]);
  const tokensForRow = (row: StageRow) =>
    (stageTokens.get(row.stage.key) ?? 0)
    + row.children.reduce((acc, ch) => acc + (stageTokens.get(ch.stage.key) ?? 0), 0);

  const lastEnd = rows.length
    ? Math.max(...rows.map(({ stage, start }) => start + (stage.ms ?? 0)))
    : 0;
  const axisTotal = Math.max(trace.total_ms ?? 0, lastEnd, 1);
  const pct = (ms: number) => (ms / axisTotal) * 100;
  let barIndex = 0;

  const stageLabel = (key: string): string => {
    try {
      return t(`stages.${key}` as Parameters<typeof t>[0]);
    } catch {
      return key;
    }
  };

  const stageDetail = (stage: TraceStage): string => {
    if (stage.key === "balance" && stage.info) {
      const magg = stage.info["maggioranza_pct"];
      const opp = stage.info["opposizione_pct"];
      if (magg != null && opp != null) {
        return `${magg}% ${t("maggShort")} · ${opp}% ${t("oppShort")}`;
      }
    }
    const keys = INFO_KEYS[stage.key] ?? [];
    const parts: string[] = [];
    for (const k of keys) {
      const v = stage.info?.[k];
      if (v == null) continue;
      if ((k === "citations_repaired" || k === "citations_failed") && !v) continue;
      try {
        parts.push(`${Number(v).toLocaleString("it-IT")} ${t(`info.${k}` as Parameters<typeof t>[0])}`);
      } catch {
        parts.push(`${v} ${k}`);
      }
    }
    return parts.join(" · ");
  };

  const toggleStage = (key: string) => {
    setOpenStages((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const renderBar = (stage: TraceStage, start: number, variant: "stage" | "hero" | "child") => {
    const delay = `${Math.min(barIndex++ * 60, 900)}ms`;
    return (
      <div className="relative h-[18px] flex-1 overflow-hidden rounded-[3px] bg-muted/50">
        <div
          className={cn(
            "absolute top-[3px] bottom-[3px] rounded-[2px] origin-left animate-trace-grow",
            variant === "hero" && "bg-primary",
            variant === "stage" && "bg-primary/30",
            variant === "child" && "bg-primary/55",
          )}
          style={{
            left: `${pct(start)}%`,
            width: `${Math.max(pct(stage.ms ?? 0), 0.7)}%`,
            animationDelay: delay,
          }}
        />
      </div>
    );
  };

  const renderStageCalls = (key: string) => {
    const stageCalls = callsByStage.get(key) ?? [];
    if (!openStages.has(key)) return null;
    return (
      <div className="ml-6 mr-2 my-1 space-y-1">
        {stageCalls.length === 0 ? (
          <div className="text-[10px] text-muted-foreground/50 px-2 py-1">{t("noCalls")}</div>
        ) : (
          stageCalls.map((c, i) => <LlmCallRow key={`${key}_${i}`} call={c} index={i} />)
        )}
      </div>
    );
  };

  const retrievalSample = trace.retrieval_sample ?? [];
  const partyCoverage = trace.party_coverage ?? {};
  const hasRetrieval = retrievalSample.length > 0 || Object.keys(partyCoverage).length > 0;
  const hasExplorer = calls.length > 0 || !!report || hasRetrieval;

  const header = (
    <div className="flex items-end justify-between gap-4 mb-1 px-1">
      <div>
        <div className="text-3xl leading-none text-primary [font-family:var(--font-display)]">
          {formatMs(trace.total_ms)}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground/70 mt-1.5">
          <span>{t("subtitle")}</span>
          {trace.llm && (
            <>
              <span className="text-muted-foreground/30">·</span>
              <span className="font-mono">{trace.llm.chat_calls} LLM + {trace.llm.embedding_calls} emb</span>
              <span className="text-muted-foreground/30">·</span>
              <span className="font-mono">{formatTokens(trace.llm.total_tokens)} token</span>
              {trace.llm.cost_usd != null && trace.llm.cost_usd > 0 && (
                <>
                  <span className="text-muted-foreground/30">·</span>
                  <span className="font-mono">≈{formatCost(trace.llm.cost_usd)}</span>
                </>
              )}
            </>
          )}
        </div>
      </div>
      {trace.rewritten_query && (
        <div className="text-right min-w-0 max-w-[40%]">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground/50 mb-0.5">
            {t("rewrittenLabel")}
          </div>
          <div className="text-[11px] font-mono text-muted-foreground truncate" title={trace.rewritten_query}>
            «{trace.rewritten_query}»
          </div>
        </div>
      )}
    </div>
  );

  const waterfall = (
    <div>
      {/* Asse dei tempi con tacche ai quarti */}
      <div className="flex items-center ml-[10.5rem] mr-[3.75rem] mb-1 mt-3">
        {[0, 1, 2, 3].map((q) => (
          <div key={q} className="flex-1 border-l border-border/60 pl-1 text-[9px] font-mono text-muted-foreground/50 leading-none">
            {q === 0 ? "0" : formatMs((axisTotal * q) / 4)}
          </div>
        ))}
        <div className="border-l border-border/60 pl-1 text-[9px] font-mono text-muted-foreground/50 leading-none">
          {formatMs(axisTotal)}
        </div>
      </div>

      <div className="space-y-px">
        {rows.map(({ stage, start, children }) => {
          const detail = stageDetail(stage);
          const isHero = stage.key === "generation";
          const ownCalls = (callsByStage.get(stage.key) ?? []).length;
          const clickable = ownCalls > 0;
          return (
            <div key={stage.key}>
              <div
                role={clickable ? "button" : undefined}
                onClick={clickable ? () => toggleStage(stage.key) : undefined}
                className={cn(
                  "group flex items-center gap-3 py-[3px] rounded-md transition-colors",
                  clickable ? "cursor-pointer hover:bg-muted/50" : "hover:bg-muted/30",
                )}
              >
                <div className="w-[9.75rem] shrink-0 pl-1 min-w-0">
                  <div className="flex items-center gap-1 min-w-0">
                    {clickable && (
                      <ChevronRight className={cn("h-3 w-3 shrink-0 text-muted-foreground/50 transition-transform", openStages.has(stage.key) && "rotate-90")} />
                    )}
                    <span className={cn(
                      "text-[11px] leading-tight truncate",
                      isHero ? "font-semibold text-foreground" : "text-foreground/80",
                    )}>
                      {stageLabel(stage.key)}
                    </span>
                    {ownCalls > 0 && (
                      <span className="text-[8.5px] font-mono text-primary/60 bg-primary/10 rounded-full px-1.5 shrink-0">{ownCalls}</span>
                    )}
                  </div>
                  {detail && (
                    <div className={cn("text-[10px] text-muted-foreground/60 leading-tight truncate", clickable && "pl-4")} title={detail}>
                      {detail}
                    </div>
                  )}
                </div>
                {renderBar(stage, start, isHero ? "hero" : "stage")}
                <div className="w-[3rem] shrink-0 text-right text-[10px] font-mono tabular-nums text-muted-foreground">
                  {formatMs(stage.ms)}
                  {tokensForRow({ stage, start, children }) > 0 && (
                    <div className="text-[8.5px] text-muted-foreground/50 leading-tight">
                      {formatTokens(tokensForRow({ stage, start, children }))} tok
                    </div>
                  )}
                </div>
              </div>
              {renderStageCalls(stage.key)}

              {children.length > 0 && (
                <div className="ml-2 border-l border-border/50">
                  {children.map(({ stage: child, start: childStart }) => {
                    const childDetail = stageDetail(child);
                    const childCalls = (callsByStage.get(child.key) ?? []).length;
                    const childClickable = childCalls > 0;
                    return (
                      <div key={child.key}>
                        <div
                          role={childClickable ? "button" : undefined}
                          onClick={childClickable ? () => toggleStage(child.key) : undefined}
                          className={cn(
                            "group flex items-center gap-3 py-[2px] pl-2 rounded-md transition-colors",
                            childClickable ? "cursor-pointer hover:bg-muted/50" : "hover:bg-muted/30",
                          )}
                        >
                          <div className="w-[9.1rem] shrink-0 min-w-0">
                            <div className="flex items-baseline gap-1.5 min-w-0">
                              {childClickable && (
                                <ChevronRight className={cn("h-2.5 w-2.5 shrink-0 self-center text-muted-foreground/50 transition-transform", openStages.has(child.key) && "rotate-90")} />
                              )}
                              <span className="text-[10.5px] text-foreground/70 leading-tight truncate">
                                {stageLabel(child.key)}
                              </span>
                              {child.model && (
                                <span className="text-[8.5px] font-mono text-muted-foreground/50 bg-muted/70 rounded px-1 py-px shrink-0">
                                  {child.model}
                                </span>
                              )}
                              {childCalls > 0 && (
                                <span className="text-[8.5px] font-mono text-primary/60 bg-primary/10 rounded-full px-1.5 shrink-0">{childCalls}</span>
                              )}
                            </div>
                            {childDetail && (
                              <div className="text-[10px] text-muted-foreground/60 leading-tight truncate" title={childDetail}>
                                {childDetail}
                              </div>
                            )}
                          </div>
                          {renderBar(child, childStart, "child")}
                          <div className="w-[3rem] shrink-0 text-right text-[10px] font-mono tabular-nums text-muted-foreground/80">
                            {formatMs(child.ms)}
                            {(stageTokens.get(child.key) ?? 0) > 0 && (
                              <div className="text-[8.5px] text-muted-foreground/50 leading-tight">
                                {formatTokens(stageTokens.get(child.key))} tok
                              </div>
                            )}
                          </div>
                        </div>
                        {renderStageCalls(child.key)}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {/* Chiamate fuori da ogni finestra di fase */}
        {(callsByStage.get("other") ?? []).length > 0 && (
          <div>
            <div
              role="button"
              onClick={() => toggleStage("other")}
              className="group flex items-center gap-1 py-[3px] pl-1 rounded-md cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <ChevronRight className={cn("h-3 w-3 shrink-0 text-muted-foreground/50 transition-transform", openStages.has("other") && "rotate-90")} />
              <span className="text-[11px] text-foreground/60">{t("stages.other")}</span>
              <span className="text-[8.5px] font-mono text-primary/60 bg-primary/10 rounded-full px-1.5">{(callsByStage.get("other") ?? []).length}</span>
            </div>
            {renderStageCalls("other")}
          </div>
        )}
      </div>

      {(trace.compass_meta || trace.domain) && (
        <div className="flex flex-wrap gap-1.5 mt-3 px-1">
          {trace.domain && (
            <span className={cn(
              "text-[9px] font-mono rounded-full px-2 py-0.5 border",
              trace.domain.in_domain !== false
                ? "border-green-600/20 bg-green-600/5 text-green-700"
                : "border-amber-500/30 bg-amber-500/10 text-amber-700",
            )}>
              {trace.domain.in_domain !== false ? t("domainOk") : t("domainOut")}
            </span>
          )}
          {trace.compass_meta?.method && (
            <span className="text-[9px] font-mono rounded-full px-2 py-0.5 border border-border/60 bg-muted/40 text-muted-foreground">
              {t("stages.compass")}: {trace.compass_meta.method}
              {trace.compass_meta.variance != null && ` · ${t("varianceShort")} ${Math.round(trace.compass_meta.variance * 100)}%`}
              {trace.compass_meta.stable != null && ` · ${trace.compass_meta.stable ? t("compassStable") : t("compassUnstable")}`}
            </span>
          )}
        </div>
      )}

      <p className="text-[10px] text-muted-foreground/50 leading-relaxed mt-3 px-1">
        {t("footnote")}
      </p>
    </div>
  );

  if (!hasExplorer) {
    return (
      <div className="pt-2 px-1 pb-3 w-full min-w-0">
        {header}
        {waterfall}
      </div>
    );
  }

  return (
    <div className="pt-2 px-1 pb-3 w-full min-w-0">
      {header}
      <Tabs defaultValue="pipeline" className="mt-3">
        <TabsList className="h-8">
          <TabsTrigger value="pipeline" className="text-xs">{t("tabs.pipeline")}</TabsTrigger>
          {hasRetrieval && (
            <TabsTrigger value="retrieval" className="text-xs">
              {t("tabs.retrieval")}
              {retrievalSample.length > 0 && (
                <span className="ml-1.5 text-[9px] font-mono text-muted-foreground/60">{retrievalSample.length}</span>
              )}
            </TabsTrigger>
          )}
          {calls.length > 0 && (
            <TabsTrigger value="calls" className="text-xs">
              {t("tabs.calls")}
              <span className="ml-1.5 text-[9px] font-mono text-muted-foreground/60">{calls.length}</span>
            </TabsTrigger>
          )}
          {report && (
            <TabsTrigger value="citations" className="text-xs">
              {t("tabs.citations")}
              {report.ledger && (
                <span className="ml-1.5 text-[9px] font-mono text-muted-foreground/60">{report.ledger.length}</span>
              )}
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="pipeline">{waterfall}</TabsContent>

        {hasRetrieval && (
          <TabsContent value="retrieval">
            <div className="mt-2">
              {Object.keys(partyCoverage).length > 0 && (
                <div className="mb-4">
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground/60 mb-1.5 px-1">
                    {t("coverageTitle")}
                  </div>
                  <div className="space-y-1">
                    {(() => {
                      const entries = Object.entries(partyCoverage).sort((a, b) => b[1] - a[1]);
                      const max = Math.max(...entries.map(([, n]) => n), 1);
                      return entries.map(([party, n]) => (
                        <div key={party} className="flex items-center gap-2">
                          <span className="w-[11rem] shrink-0 text-[10px] text-foreground/75 truncate" title={party}>{party}</span>
                          <div className="relative flex-1 h-[12px] rounded-[2px] bg-muted/50 overflow-hidden">
                            <div
                              className="absolute inset-y-[2px] left-0 rounded-[1px] bg-primary/45 origin-left animate-trace-grow"
                              style={{ width: `${(n / max) * 100}%` }}
                            />
                          </div>
                          <span className="w-7 shrink-0 text-right text-[10px] font-mono tabular-nums text-muted-foreground">{n}</span>
                        </div>
                      ));
                    })()}
                  </div>
                </div>
              )}

              {retrievalSample.length > 0 && (
                <div>
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground/60 mb-1 px-1">
                    {t("evidenceTitle")}
                  </div>
                  <div className="rounded-md border border-border/50 overflow-hidden">
                    <div className="flex items-center gap-2 px-2 py-1 bg-muted/40 text-[9px] uppercase tracking-wider text-muted-foreground/60">
                      <span className="flex-1 min-w-0">{t("evidenceSpeaker")}</span>
                      <span className="w-10 text-right font-mono">sim</span>
                      <span className="w-10 text-right font-mono">auth</span>
                      <span className="w-10 text-right font-mono">cit</span>
                      <span className="w-[4.5rem] text-right hidden sm:block">{t("evidenceDate")}</span>
                    </div>
                    {retrievalSample.map((ev, i) => (
                      <div key={ev.id ?? i} className="flex items-center gap-2 px-2 py-1 border-t border-border/30 hover:bg-muted/30 transition-colors">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-1.5 min-w-0">
                            <span className="text-[10.5px] text-foreground/85 truncate">{ev.speaker ?? "—"}</span>
                            <span className="text-[8.5px] uppercase tracking-wider text-muted-foreground/55 truncate">{ev.party}</span>
                          </div>
                          <div className="text-[8.5px] font-mono text-muted-foreground/40 truncate" title={ev.id}>{ev.id}</div>
                        </div>
                        <span className="w-10 text-right text-[10px] font-mono tabular-nums text-muted-foreground">
                          {ev.similarity != null ? ev.similarity.toFixed(2).replace(".", ",") : "—"}
                        </span>
                        <span className="w-10 text-right text-[10px] font-mono tabular-nums text-muted-foreground">
                          {ev.authority != null ? ev.authority.toFixed(2).replace(".", ",") : "—"}
                        </span>
                        <span className="w-10 text-right text-[10px] font-mono tabular-nums text-muted-foreground">
                          {ev.citability != null ? ev.citability.toFixed(2).replace(".", ",") : "—"}
                        </span>
                        <span className="w-[4.5rem] text-right text-[9px] font-mono text-muted-foreground/60 hidden sm:block">{ev.date}</span>
                      </div>
                    ))}
                  </div>
                  <p className="text-[9px] text-muted-foreground/50 mt-1.5 px-1">{t("evidenceNote")}</p>
                </div>
              )}
            </div>
          </TabsContent>
        )}

        {calls.length > 0 && (
          <TabsContent value="calls">
            <div className="space-y-1 mt-2">
              {calls.map((c, i) => <LlmCallRow key={i} call={c} index={i} />)}
            </div>
          </TabsContent>
        )}

        {report && (
          <TabsContent value="citations">
            <div className="mt-2">
              {/* Sintesi integrità */}
              <div className="grid grid-cols-4 gap-2 mb-3">
                {[
                  { label: t("citExpected"), value: report.expected },
                  { label: t("citResolved"), value: report.resolved },
                  { label: t("citFailed"), value: report.failed },
                  {
                    label: t("citCoherence"),
                    value: report.coherence?.average_score != null
                      ? report.coherence.average_score.toFixed(2).replace(".", ",")
                      : null,
                  },
                ].map(({ label, value }) => (
                  <div key={label} className="rounded-md bg-muted/40 px-2 py-1.5 text-center">
                    <div className="text-lg leading-none text-primary [font-family:var(--font-display)]">
                      {value ?? "—"}
                    </div>
                    <div className="text-[9px] uppercase tracking-wider text-muted-foreground/60 mt-1">{label}</div>
                  </div>
                ))}
              </div>

              {report.ledger && report.ledger.length > 0 && (
                <div className="rounded-md border border-border/50 px-2">
                  {report.ledger.map((entry, i) => <LedgerRow key={i} entry={entry} />)}
                </div>
              )}

              {(report.unsupported_claims ?? []).length > 0 && (
                <div className="mt-3">
                  <div className="text-[9px] uppercase tracking-widest text-muted-foreground/60 mb-1 px-1">
                    {t("unsupportedTitle")}
                  </div>
                  <div className="space-y-1">
                    {report.unsupported_claims!.map((claim, i) => (
                      <div key={i} className="rounded bg-amber-500/10 border border-amber-500/20 px-2 py-1 text-[10px] text-foreground/70">
                        {claim}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

/**
 * Bottone accanto a "Condividi" nell'header della domanda: apre la
 * waterfall della pipeline in un dialog. Stesso linguaggio visivo di
 * ShareButton.
 */
/** Glifo LangChain (girandola a 4 petali), monocromo in currentColor */
function LangChainGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="-0.4 -0.4 22 22" fill="currentColor" className={className} aria-hidden="true">
      <path d="M6.64803 14.103C7.89438 12.8566 8.595 11.1643 8.595 9.40177C8.595 7.63928 7.89378 5.94697 6.64803 4.70058L1.94697 0C0.701225 1.24639 0 2.9387 0 4.70119C0 6.46368 0.701225 8.15599 1.94697 9.40238L6.64742 14.103H6.64803Z" />
      <path d="M16.4845 14.5379C15.2388 13.2921 13.5459 12.5908 11.7841 12.5908C10.0222 12.5908 8.32936 13.2921 7.08301 14.5379L11.7841 19.239C13.0298 20.4848 14.7227 21.1861 16.4851 21.1861C18.2476 21.1861 19.9398 20.4848 21.1862 19.239L16.4851 14.5379H16.4845Z" />
      <path d="M1.95832 19.228C3.20468 20.4738 4.89693 21.1751 6.65938 21.1751V14.5269H0.0107422C0.0113472 16.2893 0.711968 17.9817 1.95832 19.228Z" />
      <path d="M18.2997 7.58717C17.0533 6.34138 15.3611 5.63953 13.598 5.64014C11.8356 5.64014 10.1433 6.34138 8.89697 7.58777L13.598 12.289L18.2997 7.58717Z" />
    </svg>
  );
}

export function TraceButton({ trace }: { trace?: TraceData }) {
  const t = useTranslations("MessageBubble");
  if (!trace || !trace.stages?.length) return null;
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          aria-label={t("traceTitle")}
          title={t("traceTitle")}
          className="group inline-flex items-center justify-center h-9 w-9 rounded-full transition-all shrink-0 border border-primary/20 bg-primary/[0.04] text-primary/80 hover:text-primary hover:bg-primary/10 hover:border-primary/35"
        >
          <LangChainGlyph className="h-[18px] w-[18px] transition-transform group-hover:scale-110" />
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[88vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="[font-family:var(--font-display)] text-xl">
            {t("traceTitle")}
          </DialogTitle>
          <DialogDescription className="text-xs leading-relaxed">
            {t("traceTooltip")}
          </DialogDescription>
        </DialogHeader>
        <TraceCard trace={trace} />
      </DialogContent>
    </Dialog>
  );
}
