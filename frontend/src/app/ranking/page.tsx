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
  ArrowRight,
  ArrowUpDown,
  Filter,
  X,
  Users,
  ChevronDown,
  Trophy,
  Medal,
  Award,
  RotateCcw,
  Landmark,
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

  // ── Fetch ranking ──
  const fetchRanking = useCallback(async (topicText: string) => {
    if (!topicText.trim()) return;
    setLoading(true);
    setError("");
    setActiveTopic(topicText);
    // Reset filters on new search
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchRanking(topic);
  };

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

    // Coalition filter
    if (coalitionFilter !== "all") {
      list = list.filter((d) => d.coalition === coalitionFilter);
    }

    // Group filter
    if (selectedGroups.length > 0) {
      list = list.filter((d) => {
        const groupUpper = d.group.toUpperCase();
        return selectedGroups.some((g) => groupUpper === g.toUpperCase() || groupUpper.includes(g.toUpperCase()));
      });
    }

    // Name search
    if (nameSearch.trim()) {
      const q = nameSearch.toLowerCase();
      list = list.filter(
        (d) =>
          d.first_name.toLowerCase().includes(q) ||
          d.last_name.toLowerCase().includes(q) ||
          `${d.first_name} ${d.last_name}`.toLowerCase().includes(q)
      );
    }

    // Committee filter
    if (committeeSearch) {
      list = list.filter((d) => {
        if (d.committees?.includes(committeeSearch)) return true;
        if (d.committee === committeeSearch) return true;
        return false;
      });
    }

    // Sort
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

  // ── Group toggle ──
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
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 sm:px-6 h-16 shrink-0">
          <MobileMenuButton onClick={toggle} />
          <Crown className="h-5 w-5 text-primary shrink-0" />
          <h1 className="text-lg font-semibold truncate">Ranking Autorità</h1>
          {activeTopic && !loading && (
            <Badge variant="secondary" className="ml-auto shrink-0 max-w-[200px] truncate">
              {activeTopic}
            </Badge>
          )}
        </header>

        <div className="flex-1 overflow-y-auto">
          {/* ── Welcome / Search ── */}
          {!hasResults && !loading && (
            <div className="flex flex-col items-center justify-center pt-8 sm:pt-16 pb-12 text-center px-4">
              <div className="mb-6 sm:mb-10 max-w-xl space-y-3">
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/8 px-4 py-1.5 text-xs font-medium text-primary mb-2">
                  <Crown className="w-3.5 h-3.5" />
                  Ranking per Tema
                </div>
                <h2 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-foreground leading-tight">
                  Scopri chi sono i deputati più autorevoli su un tema
                </h2>
                <p className="text-muted-foreground text-sm sm:text-base leading-relaxed">
                  Inserisci un tema e il sistema calcolerà l&apos;authority score di tutti i deputati, classificandoli in ordine di competenza.
                </p>
              </div>

              {/* Search bar */}
              <form onSubmit={handleSubmit} className="w-full max-w-lg mb-8">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Es. immigrazione, riforma fiscale, clima..."
                    className="pl-10 pr-24 h-12 text-base rounded-xl border-border/80 focus-visible:ring-primary/30"
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!topic.trim()}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg h-9"
                  >
                    Cerca
                  </Button>
                </div>
              </form>

              {/* Topic pills */}
              <div className="w-full max-w-2xl">
                <p className="text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground/60 mb-4">
                  Temi suggeriti
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {TOPICS.map((t) => (
                    <button
                      key={t}
                      className="group inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-card px-4 py-2 text-sm text-foreground transition-all duration-200 hover:border-primary/40 hover:bg-primary/5 hover:shadow-sm active:scale-[0.97]"
                      onClick={() => handleTopicClick(t)}
                    >
                      <span className="capitalize">{t}</span>
                      <ArrowRight className="w-3 h-3 text-muted-foreground/40 transition-all duration-200 group-hover:text-primary group-hover:translate-x-0.5" />
                    </button>
                  ))}
                </div>
              </div>

              {error && (
                <div className="mt-6 text-red-500 text-sm bg-red-50 rounded-lg px-4 py-3 border border-red-200">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* ── Loading ── */}
          {loading && (
            <div className="flex flex-col items-center justify-center pt-20 gap-4">
              <div className="relative">
                <div className="h-16 w-16 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
                <Crown className="absolute inset-0 m-auto h-6 w-6 text-primary" />
              </div>
              <div className="text-center space-y-1">
                <p className="text-sm font-medium text-foreground">Calcolo in corso...</p>
                <p className="text-xs text-muted-foreground">
                  Analisi dell&apos;autorità di tutti i deputati sul tema selezionato
                </p>
              </div>
            </div>
          )}

          {/* ── Results ── */}
          {hasResults && !loading && (
            <div className="px-4 sm:px-6 py-4 sm:py-6 space-y-4 sm:space-y-5 max-w-5xl mx-auto w-full">
              {/* Results header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg sm:text-xl font-bold text-foreground">
                      Ranking: <span className="text-primary capitalize">{activeTopic}</span>
                    </h2>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {filteredDeputies.length === deputies.length
                      ? `${deputies.length} deputati classificati`
                      : `${filteredDeputies.length} di ${deputies.length} deputati`}
                    {computationTime > 0 && ` · ${(computationTime / 1000).toFixed(1)}s`}
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={handleReset} className="shrink-0 gap-1.5">
                  <RotateCcw className="h-3.5 w-3.5" />
                  Nuova ricerca
                </Button>
              </div>

              {/* ── Filters bar ── */}
              <div className="flex flex-wrap items-center gap-2 p-3 rounded-xl bg-muted/30 border border-border/50">
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
                <div className="relative flex-1 min-w-[180px] max-w-[260px]">
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
                <Popover open={groupsOpen} onOpenChange={setGroupsOpen}>
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
                      {GROUPS.map((g) => {
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
                  <Popover>
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
                    <PopoverContent className="w-80 p-2 max-h-60 overflow-y-auto" align="start">
                      <div className="space-y-1">
                        {committeeSearch && (
                          <button
                            onClick={() => setCommitteeSearch("")}
                            className="w-full text-left px-2.5 py-1.5 rounded-md text-xs text-destructive hover:bg-destructive/10 transition-colors"
                          >
                            ✕ Rimuovi filtro
                          </button>
                        )}
                        {availableCommittees.map((c) => (
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
                <div className="flex flex-wrap gap-1.5">
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

              {/* ── Deputies list ── */}
              {filteredDeputies.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Filter className="h-8 w-8 mx-auto mb-3 opacity-40" />
                  <p className="text-sm">Nessun deputato corrisponde ai filtri selezionati.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredDeputies.map((deputy, index) => {
                    const sortLabel = SORT_OPTIONS.find((s) => s.value === sortBy)?.label || "";
                    const displayScore =
                      sortBy === "authority_score"
                        ? deputy.authority_score
                        : deputy.score_breakdown?.[sortBy] ?? 0;

                    return (
                      <div key={deputy.id} className="flex items-center gap-3">
                        {/* Rank number */}
                        <div className="shrink-0 w-10 flex justify-center">
                          {index === 0 ? (
                            <Trophy className="h-6 w-6 text-amber-500" />
                          ) : index === 1 ? (
                            <Medal className="h-5 w-5 text-gray-400" />
                          ) : index === 2 ? (
                            <Award className="h-5 w-5 text-amber-700" />
                          ) : (
                            <span className="text-sm font-bold text-muted-foreground/60">
                              {index + 1}
                            </span>
                          )}
                        </div>

                        {/* Card */}
                        <div className="flex-1 min-w-0">
                          <RankingCard
                            deputy={deputy}
                            sortBy={sortBy}
                            sortLabel={sortLabel}
                            displayScore={displayScore}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Ranking Card ────────────────────────────────────────────────

interface RankingCardProps {
  deputy: RankingDeputy;
  sortBy: SortKey;
  sortLabel: string;
  displayScore: number;
}

function RankingCard({ deputy, sortBy, sortLabel, displayScore }: RankingCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const groupConfig =
    config.politicalGroups[deputy.group as keyof typeof config.politicalGroups];
  const groupColor = groupConfig?.color || "#6B7280";
  const groupLabel = groupConfig?.label || deputy.group;

  const scoreLevel =
    displayScore >= config.authorityScore.high
      ? "high"
      : displayScore >= config.authorityScore.medium
      ? "medium"
      : "low";

  const barColorClass =
    scoreLevel === "high" ? "bg-green-500" : scoreLevel === "medium" ? "bg-amber-500" : "bg-gray-400";

  return (
    <>
      <div
        className="flex items-center gap-3 sm:gap-4 p-3 sm:p-4 rounded-xl border border-border/60 bg-card hover:bg-card/80 hover:shadow-sm transition-all cursor-pointer group"
        onClick={() => setIsModalOpen(true)}
      >
        {/* Avatar */}
        <div
          className="flex h-10 w-10 sm:h-11 sm:w-11 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm"
          style={{ backgroundColor: groupColor }}
        >
          {deputy.first_name[0]}{deputy.last_name[0]}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <p className="text-sm font-semibold text-foreground truncate">
              {deputy.first_name} {deputy.last_name}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="outline"
              className="text-[10px] px-1.5 py-0 h-4 font-medium border"
              style={{ color: groupColor, borderColor: groupColor }}
            >
              {groupLabel.length > 25 ? groupLabel.substring(0, 25) + "…" : groupLabel}
            </Badge>
            <span className="text-[10px] text-muted-foreground capitalize">
              {deputy.coalition === "maggioranza" ? "Maggioranza" : "Opposizione"}
            </span>
          </div>
        </div>

        {/* Score */}
        <div className="shrink-0 flex items-center gap-3">
          <div className="hidden sm:flex flex-col items-end gap-0.5">
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
              {sortBy === "authority_score" ? "Score" : sortLabel}
            </span>
            <div className="w-20 h-1.5 rounded-full bg-muted overflow-hidden">
              <div
                className={cn("h-full rounded-full transition-all", barColorClass)}
                style={{ width: `${displayScore * 100}%` }}
              />
            </div>
          </div>
          <span className="text-lg sm:text-xl font-bold text-foreground min-w-[36px] text-right">
            {(displayScore * 100).toFixed(0)}
          </span>
        </div>
      </div>

      <ExpertModal expert={deputy} isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
}
