"use client";

import { useState, useMemo, useCallback } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { ExpertModal } from "@/components/chat/ExpertCard";
import { config } from "@/config";
import { cn } from "@/lib/utils";
import type { Expert } from "@/types";
import {
  Crown,
  Search,
  ArrowUpDown,
  X,
  Users,
  ChevronDown,
  Trophy,
  Medal,
  Award,
  RotateCcw,
  Landmark,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

// ── Types ──────────────────────────────────────────────────────

interface RankingDeputy extends Expert {
  committees?: string[];
  relevant_speeches_count: number;
}

type SortKey =
  | "authority_score"
  | "speeches"
  | "acts"
  | "committee"
  | "profession"
  | "education"
  | "role";

type CoalitionFilter = "all" | "maggioranza" | "opposizione";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "authority_score", label: "Authority Score" },
  { value: "speeches", label: "Interventi" },
  { value: "acts", label: "Atti" },
  { value: "committee", label: "Commissione" },
  { value: "profession", label: "Professione" },
  { value: "education", label: "Istruzione" },
  { value: "role", label: "Ruolo" },
];

const GROUPS: { value: string; label: string; shortLabel: string }[] = [
  { value: "FRATELLI D'ITALIA", label: "Fratelli d'Italia", shortLabel: "FdI" },
  { value: "LEGA - SALVINI PREMIER", label: "Lega - Salvini Premier", shortLabel: "Lega" },
  { value: "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE", label: "Forza Italia", shortLabel: "FI" },
  { value: "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC E ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE", label: "Noi Moderati", shortLabel: "NM" },
  { value: "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA", label: "PD", shortLabel: "PD" },
  { value: "MOVIMENTO 5 STELLE", label: "M5S", shortLabel: "M5S" },
  { value: "ALLEANZA VERDI E SINISTRA", label: "AVS", shortLabel: "AVS" },
  { value: "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE", label: "Azione", shortLabel: "Azione" },
  { value: "ITALIA VIVA-IL CENTRO-RENEW EUROPE", label: "Italia Viva", shortLabel: "IV" },
  { value: "MISTO", label: "Misto", shortLabel: "Misto" },
];

const TOPICS = [
  "PNRR", "riforma sanitaria", "transizione energetica", "salario minimo",
  "conflitto in Ucraina", "riforma fiscale", "autonomia differenziata",
  "riforma della giustizia", "flussi migratori", "scuola e istruzione",
  "cambiamento climatico", "infrastrutture",
];

// ── Page ───────────────────────────────────────────────────────

export default function RankingPage() {
  const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();

  // Data state
  const [deputies, setDeputies] = useState<RankingDeputy[]>([]);
  const [topic, setTopic] = useState("");
  const [activeTopic, setActiveTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [computationTime, setComputationTime] = useState(0);

  // Filter state
  const [nameSearch, setNameSearch] = useState("");
  const [coalitionFilter, setCoalitionFilter] = useState<CoalitionFilter>("all");
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const [committeeSearch, setCommitteeSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("authority_score");
  const [sortOpen, setSortOpen] = useState(false);
  const [groupsOpen, setGroupsOpen] = useState(false);
  const [groupSearch, setGroupSearch] = useState("");
  const [committeePopoverSearch, setCommitteePopoverSearch] = useState("");

  // ── Fetch ranking ──
  const fetchRanking = useCallback(async (topicText: string) => {
    if (!topicText.trim()) return;
    setLoading(true);
    setError("");
    setActiveTopic(topicText);
    setNameSearch("");
    setCoalitionFilter("all");
    setSelectedGroups([]);
    setCommitteeSearch("");
    setSortBy("authority_score");

    try {
      const res = await fetch(`${config.api.baseUrl}/authority-ranking`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topicText }),
      });
      if (!res.ok) throw new Error("Errore nel calcolo del ranking");
      const data = await res.json();
      setDeputies(
        data.deputies.map((d: any) => ({
          ...d,
          relevant_speeches_count: 0,
        }))
      );
      setComputationTime(data.computation_time_ms || 0);
    } catch (e: any) {
      setError(e.message || "Errore sconosciuto");
      setDeputies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleTopicClick = (t: string) => {
    setTopic(t);
    fetchRanking(t);
  };

  const handleReset = () => {
    setDeputies([]);
    setActiveTopic("");
    setTopic("");
    setError("");
  };

  // ── Available committees ──
  const availableCommittees = useMemo(() => {
    const set = new Set<string>();
    deputies.forEach((d) => {
      d.committees?.forEach((c) => set.add(c));
      if (d.committee) set.add(d.committee);
    });
    return Array.from(set).sort();
  }, [deputies]);

  // ── Filtered and sorted deputies ──
  const filteredDeputies = useMemo(() => {
    let list = [...deputies];

    if (coalitionFilter !== "all") {
      list = list.filter((d) => d.coalition === coalitionFilter);
    }

    if (selectedGroups.length > 0) {
      list = list.filter((d) => {
        const groupUpper = d.group.toUpperCase();
        return selectedGroups.some((g) => groupUpper === g.toUpperCase() || groupUpper.includes(g.toUpperCase()));
      });
    }

    if (nameSearch.trim()) {
      const q = nameSearch.toLowerCase();
      list = list.filter(
        (d) =>
          d.first_name.toLowerCase().includes(q) ||
          d.last_name.toLowerCase().includes(q) ||
          `${d.first_name} ${d.last_name}`.toLowerCase().includes(q)
      );
    }

    if (committeeSearch) {
      list = list.filter((d) => {
        if (d.committees?.includes(committeeSearch)) return true;
        if (d.committee === committeeSearch) return true;
        return false;
      });
    }

    list.sort((a, b) => {
      if (sortBy === "authority_score") {
        return b.authority_score - a.authority_score;
      }
      const aVal = a.score_breakdown?.[sortBy] ?? 0;
      const bVal = b.score_breakdown?.[sortBy] ?? 0;
      return bVal - aVal;
    });

    return list;
  }, [deputies, coalitionFilter, selectedGroups, nameSearch, committeeSearch, sortBy]);

  const hasResults = deputies.length > 0;
  const hasActiveFilters = coalitionFilter !== "all" || selectedGroups.length > 0 || nameSearch.trim() !== "" || committeeSearch !== "";
  const filtersEnabled = hasResults && !loading;

  const toggleGroup = (value: string) => {
    setSelectedGroups((prev) =>
      prev.includes(value) ? prev.filter((g) => g !== value) : [...prev, value]
    );
  };

  // ── Render ──
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
        {/* ── Header ── */}
        <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur-sm shrink-0">
          <div className="flex items-center gap-3 px-4 sm:px-6 h-14">
            <MobileMenuButton onClick={toggle} />
            <h1 className="text-base font-semibold whitespace-nowrap">Ranking Autorità</h1>

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

        {/* ── Barra filtri persistente (solo quando ci sono risultati) ── */}
        {filtersEnabled && <div className="sticky top-14 z-20 border-b border-border/50 bg-muted/30 backdrop-blur-sm px-4 sm:px-6 py-2.5 shrink-0">
          <div className="flex flex-wrap items-center gap-2 max-w-6xl">
            {/* Coalition toggle */}
            <div className="flex rounded-lg border border-border overflow-hidden text-xs font-medium">
              {(["all", "maggioranza", "opposizione"] as CoalitionFilter[]).map((c) => (
                <button
                  key={c}
                  onClick={() => setCoalitionFilter(c)}
                  className={cn(
                    "px-3 py-1.5 transition-colors capitalize",
                    coalitionFilter === c
                      ? "bg-primary text-primary-foreground"
                      : "bg-background hover:bg-muted text-muted-foreground"
                  )}
                >
                  {c === "all" ? "Tutti" : c === "maggioranza" ? "Maggioranza" : "Opposizione"}
                </button>
              ))}
            </div>

            {/* Name search */}
            <div className="relative flex-1 min-w-[160px] max-w-[220px]">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={nameSearch}
                onChange={(e) => setNameSearch(e.target.value)}
                placeholder="Cerca deputato..."
                className="pl-8 h-8 text-xs rounded-lg"
              />
              {nameSearch && (
                <button onClick={() => setNameSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2">
                  <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                </button>
              )}
            </div>

            {/* Group filter */}
            <Popover open={groupsOpen} onOpenChange={(open) => { setGroupsOpen(open); if (!open) setGroupSearch(""); }}>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5">
                  <Users className="h-3.5 w-3.5" />
                  Gruppo
                  {selectedGroups.length > 0 && (
                    <Badge className="ml-1 h-4 w-4 p-0 flex items-center justify-center text-[10px] bg-primary text-primary-foreground">
                      {selectedGroups.length}
                    </Badge>
                  )}
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-64 p-2" align="start">
                <div className="space-y-1">
                  {/* Search input */}
                  <div className="relative mb-2">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      value={groupSearch}
                      onChange={(e) => setGroupSearch(e.target.value)}
                      placeholder="Cerca gruppo..."
                      className="pl-8 h-7 text-xs rounded-md"
                      autoFocus
                    />
                    {groupSearch && (
                      <button onClick={() => setGroupSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2">
                        <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                      </button>
                    )}
                  </div>
                  {GROUPS.filter((g) => g.label.toLowerCase().includes(groupSearch.toLowerCase())).map((g) => {
                    const selected = selectedGroups.includes(g.value);
                    const groupConfig = config.politicalGroups[g.value as keyof typeof config.politicalGroups];
                    const color = groupConfig?.color || "#6B7280";
                    return (
                      <button
                        key={g.value}
                        onClick={() => toggleGroup(g.value)}
                        className={cn(
                          "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors text-left",
                          selected ? "bg-primary/10 text-foreground" : "hover:bg-muted text-muted-foreground"
                        )}
                      >
                        <div
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{ backgroundColor: color }}
                        />
                        <span className="truncate flex-1">{g.label}</span>
                        {selected && <span className="text-primary text-[10px] font-bold">✓</span>}
                      </button>
                    );
                  })}
                  {selectedGroups.length > 0 && (
                    <button
                      onClick={() => setSelectedGroups([])}
                      className="w-full text-center text-xs text-destructive hover:underline pt-1 border-t border-border mt-1"
                    >
                      Rimuovi filtri
                    </button>
                  )}
                </div>
              </PopoverContent>
            </Popover>

            {/* Committee filter */}
            {availableCommittees.length > 0 && (
              <Popover onOpenChange={(open) => { if (!open) setCommitteePopoverSearch(""); }}>
                <PopoverTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5">
                    <Landmark className="h-3.5 w-3.5" />
                    Commissione
                    {committeeSearch && (
                      <Badge className="ml-1 h-4 px-1 text-[10px] bg-primary text-primary-foreground">1</Badge>
                    )}
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80 p-2" align="start">
                  <div className="space-y-1">
                    {/* Search input */}
                    <div className="relative mb-2">
                      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        value={committeePopoverSearch}
                        onChange={(e) => setCommitteePopoverSearch(e.target.value)}
                        placeholder="Cerca commissione..."
                        className="pl-8 h-7 text-xs rounded-md"
                        autoFocus
                      />
                      {committeePopoverSearch && (
                        <button onClick={() => setCommitteePopoverSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2">
                          <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                        </button>
                      )}
                    </div>
                    <div className="max-h-52 overflow-y-auto space-y-1">
                      {committeeSearch && !committeePopoverSearch && (
                        <button
                          onClick={() => setCommitteeSearch("")}
                          className="w-full text-left px-2.5 py-1.5 rounded-md text-xs text-destructive hover:bg-destructive/10 transition-colors"
                        >
                          ✕ Rimuovi filtro
                        </button>
                      )}
                      {availableCommittees
                        .filter((c) => c.toLowerCase().includes(committeePopoverSearch.toLowerCase()))
                        .map((c) => (
                          <button
                            key={c}
                            onClick={() => setCommitteeSearch(committeeSearch === c ? "" : c)}
                            className={cn(
                              "w-full text-left px-2.5 py-1.5 rounded-md text-xs transition-colors",
                              committeeSearch === c
                                ? "bg-primary/10 text-foreground font-medium"
                                : "hover:bg-muted text-muted-foreground"
                            )}
                          >
                            {c}
                          </button>
                        ))}
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            )}

            {/* Sort */}
            <Popover open={sortOpen} onOpenChange={setSortOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="h-8 text-xs gap-1.5 ml-auto">
                  <ArrowUpDown className="h-3.5 w-3.5" />
                  {SORT_OPTIONS.find((s) => s.value === sortBy)?.label || "Ordina"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-48 p-2" align="end">
                <div className="space-y-1">
                  {SORT_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => { setSortBy(opt.value); setSortOpen(false); }}
                      className={cn(
                        "w-full text-left px-2.5 py-1.5 rounded-md text-xs transition-colors",
                        sortBy === opt.value
                          ? "bg-primary/10 text-foreground font-medium"
                          : "hover:bg-muted text-muted-foreground"
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </PopoverContent>
            </Popover>

            {/* Clear all filters */}
            {hasActiveFilters && (
              <button
                onClick={() => {
                  setCoalitionFilter("all");
                  setSelectedGroups([]);
                  setNameSearch("");
                  setCommitteeSearch("");
                }}
                className="text-xs text-destructive hover:underline whitespace-nowrap"
              >
                Pulisci filtri
              </button>
            )}
          </div>

          {/* Selected group badges */}
          {selectedGroups.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {selectedGroups.map((gv) => {
                const g = GROUPS.find((gr) => gr.value === gv);
                const groupConfig = config.politicalGroups[gv as keyof typeof config.politicalGroups];
                const color = groupConfig?.color || "#6B7280";
                return (
                  <Badge
                    key={gv}
                    variant="outline"
                    className="text-xs gap-1 pl-2 pr-1 py-0.5 cursor-pointer hover:bg-destructive/10"
                    style={{ borderColor: color, color }}
                    onClick={() => toggleGroup(gv)}
                  >
                    {g?.shortLabel || gv}
                    <X className="h-3 w-3" />
                  </Badge>
                );
              })}
            </div>
          )}
        </div>}

        {/* ── Content area ── */}
        <div className="flex-1 overflow-y-auto">
          {/* ── Stato vuoto — dashboard style ── */}
          {!hasResults && !loading && (
            <div className="flex flex-col items-center justify-center h-full px-4 pb-16">
              <div className="text-center space-y-6 max-w-lg">
                <div className="mx-auto h-16 w-16 rounded-2xl bg-primary/8 flex items-center justify-center">
                  <Crown className="h-8 w-8 text-primary/60" />
                </div>
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-foreground">
                    Ranking Autorità dei Deputati
                  </h2>
                  <p className="text-sm text-muted-foreground leading-relaxed max-w-md mx-auto">
                    Cerca un tema politico e scopri quali deputati sono più autorevoli in materia,
                    sulla base di interventi, atti, commissioni, professione, istruzione e ruolo istituzionale.
                  </p>
                </div>

                {/* Search bar — stile coerente con pagina Ricerca */}
                <div className="w-full max-w-md mx-auto pt-2">
                  <form onSubmit={(e) => { e.preventDefault(); fetchRanking(topic); }} className="relative">
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
                      Cerca
                    </Button>
                  </form>
                </div>

                {/* Come funziona */}
                <div className="grid grid-cols-3 gap-3 max-w-sm mx-auto pt-2">
                  <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-muted/40">
                    <Search className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">Cerca un tema</span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-muted/40">
                    <ArrowUpDown className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">Classifica generata</span>
                  </div>
                  <div className="flex flex-col items-center gap-1.5 p-3 rounded-lg bg-muted/40">
                    <Users className="h-4 w-4 text-primary/70" />
                    <span className="text-[11px] text-muted-foreground font-medium leading-tight">Filtra e esplora</span>
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

          {/* ── Loading skeleton ── */}
          {loading && (
            <div className="px-4 sm:px-6 py-4 max-w-6xl mx-auto w-full">
              {/* Skeleton header */}
              <div className="flex items-center justify-between mb-4">
                <div className="space-y-2">
                  <div className="h-5 w-48 bg-muted rounded animate-pulse" />
                  <div className="h-3 w-32 bg-muted/60 rounded animate-pulse" />
                </div>
              </div>
              {/* Skeleton table header */}
              <div className="hidden sm:grid grid-cols-[3rem_1fr_8rem_6rem_5rem] gap-3 px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50 border-b border-border/30">
                <span>#</span>
                <span>Deputato</span>
                <span>Gruppo</span>
                <span>Coalizione</span>
                <span className="text-right">Score</span>
              </div>
              {/* Skeleton rows */}
              <div className="space-y-1 mt-1">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-lg">
                    <div className="h-5 w-8 bg-muted/60 rounded animate-pulse" />
                    <div className="h-9 w-9 bg-muted rounded-full animate-pulse shrink-0" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-4 w-36 bg-muted rounded animate-pulse" />
                      <div className="h-3 w-20 bg-muted/50 rounded animate-pulse" />
                    </div>
                    <div className="hidden sm:block h-3 w-16 bg-muted/50 rounded animate-pulse" />
                    <div className="hidden sm:block h-3 w-14 bg-muted/40 rounded animate-pulse" />
                    <div className="h-5 w-10 bg-muted rounded animate-pulse" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Tabella risultati ── */}
          {hasResults && !loading && (
            <div className="px-4 sm:px-6 py-4 max-w-6xl mx-auto w-full">
              {/* Results info */}
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-muted-foreground">
                  {filteredDeputies.length === deputies.length
                    ? `${deputies.length} deputati classificati`
                    : `${filteredDeputies.length} di ${deputies.length} deputati`}
                  {computationTime > 0 && ` · ${(computationTime / 1000).toFixed(1)}s`}
                </p>
                <Button variant="ghost" size="sm" onClick={handleReset} className="h-7 text-xs gap-1.5 sm:hidden">
                  <RotateCcw className="h-3 w-3" />
                  Nuova ricerca
                </Button>
              </div>

              {/* Table header (desktop) */}
              <div className="hidden sm:grid grid-cols-[3rem_1fr_8rem_6rem_5rem] gap-3 px-4 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50 border-b border-border/30">
                <span>#</span>
                <span>Deputato</span>
                <span>Gruppo</span>
                <span>Coalizione</span>
                <span className="text-right">Score</span>
              </div>

              {/* Rows */}
              {filteredDeputies.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground">
                  <Users className="h-8 w-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Nessun deputato corrisponde ai filtri selezionati.</p>
                </div>
              ) : (
                <div className="divide-y divide-border/30">
                  {filteredDeputies.map((deputy, index) => (
                    <RankingRow
                      key={deputy.id}
                      deputy={deputy}
                      index={index}
                      sortBy={sortBy}
                      sortLabel={SORT_OPTIONS.find((s) => s.value === sortBy)?.label || ""}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Ranking Row ────────────────────────────────────────────────

interface RankingRowProps {
  deputy: RankingDeputy;
  index: number;
  sortBy: SortKey;
  sortLabel: string;
}

function RankingRow({ deputy, index, sortBy, sortLabel }: RankingRowProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const groupConfig =
    config.politicalGroups[deputy.group as keyof typeof config.politicalGroups];
  const groupColor = groupConfig?.color || "#6B7280";
  const groupLabel = groupConfig?.label || deputy.group;

  const displayScore =
    sortBy === "authority_score"
      ? deputy.authority_score
      : deputy.score_breakdown?.[sortBy] ?? 0;

  const scoreLevel =
    displayScore >= config.authorityScore.high
      ? "high"
      : displayScore >= config.authorityScore.medium
      ? "medium"
      : "low";

  const barColorClass =
    scoreLevel === "high" ? "bg-green-500" : scoreLevel === "medium" ? "bg-amber-500" : "bg-gray-400";

  const rankIcon =
    index === 0 ? <Trophy className="h-5 w-5 text-amber-500" /> :
    index === 1 ? <Medal className="h-4.5 w-4.5 text-gray-400" /> :
    index === 2 ? <Award className="h-4.5 w-4.5 text-amber-700" /> :
    null;

  return (
    <>
      {/* Desktop row */}
      <div
        className="hidden sm:grid grid-cols-[3rem_1fr_8rem_6rem_5rem] gap-3 items-center px-4 py-2.5 rounded-lg hover:bg-muted/40 transition-colors cursor-pointer group"
        onClick={() => setIsModalOpen(true)}
      >
        {/* Rank */}
        <div className="flex justify-center">
          {rankIcon || (
            <span className="text-sm font-semibold text-muted-foreground/50">{index + 1}</span>
          )}
        </div>

        {/* Deputy */}
        <div className="flex items-center gap-3 min-w-0">
          {deputy.photo ? (
            <img
              src={deputy.photo}
              alt={`${deputy.first_name} ${deputy.last_name}`}
              className="h-9 w-9 shrink-0 rounded-full object-cover"
            />
          ) : (
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
              style={{ backgroundColor: groupColor }}
            >
              {deputy.first_name[0]}{deputy.last_name[0]}
            </div>
          )}
          <p className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">
            {deputy.first_name} {deputy.last_name}
          </p>
        </div>

        {/* Group */}
        <Badge
          variant="outline"
          className="text-[10px] px-1.5 py-0 h-5 font-medium border truncate justify-center"
          style={{ color: groupColor, borderColor: groupColor }}
        >
          {groupLabel.length > 18 ? groupLabel.substring(0, 18) + "…" : groupLabel}
        </Badge>

        {/* Coalition */}
        <span className="text-xs text-muted-foreground capitalize">
          {deputy.coalition === "maggioranza" ? "Maggioranza" : "Opposizione"}
        </span>

        {/* Score */}
        <div className="flex items-center justify-end gap-2">
          <div className="w-12 h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", barColorClass)}
              style={{ width: `${displayScore * 100}%` }}
            />
          </div>
          <span className="text-sm font-bold text-foreground min-w-[28px] text-right tabular-nums">
            {(displayScore * 100).toFixed(0)}
          </span>
        </div>
      </div>

      {/* Mobile row */}
      <div
        className="sm:hidden flex items-center gap-3 px-3 py-3 active:bg-muted/40 transition-colors cursor-pointer"
        onClick={() => setIsModalOpen(true)}
      >
        <div className="shrink-0 w-8 flex justify-center">
          {rankIcon || (
            <span className="text-xs font-bold text-muted-foreground/50">{index + 1}</span>
          )}
        </div>
        {deputy.photo ? (
          <img
            src={deputy.photo}
            alt={`${deputy.first_name} ${deputy.last_name}`}
            className="h-9 w-9 shrink-0 rounded-full object-cover"
          />
        ) : (
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
            style={{ backgroundColor: groupColor }}
          >
            {deputy.first_name[0]}{deputy.last_name[0]}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {deputy.first_name} {deputy.last_name}
          </p>
          <p className="text-[10px] text-muted-foreground truncate" style={{ color: groupColor }}>
            {groupLabel.length > 22 ? groupLabel.substring(0, 22) + "…" : groupLabel}
          </p>
        </div>
        <span className="text-base font-bold text-foreground tabular-nums">
          {(displayScore * 100).toFixed(0)}
        </span>
      </div>

      <ExpertModal expert={deputy} isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
}
