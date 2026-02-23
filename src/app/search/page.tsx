"use client";

import { useState } from "react";
import { Sidebar, MobileMenuButton } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { DeputySelector, Deputy } from "@/components/search/DeputySelector";
import { GroupSelector } from "@/components/search/GroupSelector";
import { ResultsList, SearchResultItem } from "@/components/search/ResultsList";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Sheet,
    SheetContent,
    SheetHeader,
    SheetTitle,
    SheetFooter,
    SheetClose,
} from "@/components/ui/sheet";
import {
    Search as SearchIcon,
    Loader2,
    FilterX,
    FileText,
    MessageSquareQuote,
    ChevronLeft,
    ChevronRight,
    User,
    Calendar,
    Text,
    Users,
    SlidersHorizontal,
    History,
    Clock,
    X,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import { config } from "@/config";
import { useLocalHistory } from "@/hooks/use-local-history";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";

const PAGE_SIZE = 20;

export default function SearchPage() {
    const { isCollapsed, toggle, isMobile, isMobileOpen, closeMobile } = useSidebar();

    // Search history
    type SearchHistoryData = {
        query: string;
        authorFilterMode: "all" | "deputy" | "group";
        selectedDeputies: Deputy[];
        selectedGroups: string[];
        startDate: string;
        endDate: string;
        docType: "all" | "speech" | "act";
    };
    const searchHistory = useLocalHistory<SearchHistoryData>("parliamentrag-search-history");

    const restoreSearchEntry = async (data: SearchHistoryData) => {
        setQuery(data.query);
        setAuthorFilterMode(data.authorFilterMode);
        setSelectedDeputies(data.selectedDeputies);
        setSelectedGroups(data.selectedGroups);
        setStartDate(data.startDate);
        setEndDate(data.endDate);
        setDocType(data.docType);
        setHasSearched(true);
        setCurrentPage(1);
        await fetchPage(1, data);
    };

    // Filter state
    const [query, setQuery] = useState("");
    const [selectedDeputies, setSelectedDeputies] = useState<Deputy[]>([]);
    const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [docType, setDocType] = useState<"all" | "speech" | "act">("all");
    const [authorFilterMode, setAuthorFilterMode] = useState<"all" | "deputy" | "group">("all");

    // Sort state
    const [sortBy, setSortBy] = useState<"relevance" | "date_desc" | "date_asc">("relevance");

    // Results state
    const [results, setResults] = useState<SearchResultItem[]>([]);
    const [totalResults, setTotalResults] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [hasSearched, setHasSearched] = useState(false);

    // Mobile filter sheet state
    const [filterSheetOpen, setFilterSheetOpen] = useState(false);
    const [filterTab, setFilterTab] = useState<"autore" | "tipo" | "periodo">("autore");

    // Mobile history sheet state
    const [historySheetOpen, setHistorySheetOpen] = useState(false);

    const fetchPage = async (
        page: number,
        override?: SearchHistoryData,
        overrideSortBy?: "relevance" | "date_desc" | "date_asc"
    ) => {
        const q = override?.query ?? query;
        const mode = override?.authorFilterMode ?? authorFilterMode;
        const deputies = override?.selectedDeputies ?? selectedDeputies;
        const groups = override?.selectedGroups ?? selectedGroups;
        const sd = override?.startDate ?? startDate;
        const ed = override?.endDate ?? endDate;
        const dt = override?.docType ?? docType;
        const sb = overrideSortBy ?? sortBy;

        if (!q.trim()) return;

        setLoading(true);
        setResults([]);

        try {
            const params = new URLSearchParams();
            params.append('q', q);
            params.append('search_type', 'hybrid');
            params.append('doc_type', dt);
            params.append('sort_by', sb);
            params.append('page', String(page));
            params.append('page_size', String(PAGE_SIZE));

            if (deputies.length > 0 && mode === 'deputy') {
                for (const d of deputies) params.append('deputy_id', d.id);
            }
            if (groups.length > 0 && mode === 'group') {
                for (const g of groups) params.append('group', g);
            }
            if (sd) params.append('start_date', sd);
            if (ed) params.append('end_date', ed);

            const res = await fetch(`${config.api.baseUrl}/search/results?${params.toString()}`);
            if (res.ok) {
                const data = await res.json();
                setResults(data.results);
                setTotalResults(data.total);
                setTotalPages(data.total_pages);
                setCurrentPage(data.page);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = async () => {
        setHasSearched(true);
        setCurrentPage(1);
        await fetchPage(1);
        searchHistory.addEntry(query.trim(), {
            query,
            authorFilterMode,
            selectedDeputies,
            selectedGroups,
            startDate,
            endDate,
            docType,
        });
    };

    const handlePageChange = async (page: number) => {
        await fetchPage(page);
        document.getElementById("search-results")?.scrollIntoView({ behavior: "smooth" });
    };

    const handleSortChange = async (newSort: "relevance" | "date_desc" | "date_asc") => {
        setSortBy(newSort);
        if (hasSearched) {
            setCurrentPage(1);
            await fetchPage(1, undefined, newSort);
        }
    };

    const clearFilters = () => {
        setQuery("");
        setSelectedDeputies([]);
        setSelectedGroups([]);
        setStartDate("");
        setEndDate("");
        setDocType("all");
        setAuthorFilterMode("all");
        setSortBy("relevance");
        setResults([]);
        setTotalResults(0);
        setTotalPages(0);
        setCurrentPage(1);
        setHasSearched(false);
    };

    const handleAuthorModeChange = (mode: "all" | "deputy" | "group") => {
        setAuthorFilterMode(mode);
        if (mode === 'deputy') setSelectedGroups([]);
        if (mode === 'group') setSelectedDeputies([]);
        if (mode === 'all') { setSelectedDeputies([]); setSelectedGroups([]); }
    };

    const getFilterTags = (data: SearchHistoryData): string[] => {
        const tags: string[] = [];
        if (data.authorFilterMode === 'deputy' && data.selectedDeputies.length > 0) {
            tags.push(data.selectedDeputies.length === 1
                ? `${data.selectedDeputies[0].first_name} ${data.selectedDeputies[0].last_name}`
                : `${data.selectedDeputies.length} deputati`);
        }
        if (data.authorFilterMode === 'group' && data.selectedGroups.length > 0) {
            tags.push(data.selectedGroups.length === 1 ? data.selectedGroups[0] : `${data.selectedGroups.length} gruppi`);
        }
        if (data.docType !== 'all') {
            tags.push(data.docType === 'speech' ? 'Interventi' : 'Atti');
        }
        if (data.startDate && data.endDate) {
            tags.push(`${formatDate(data.startDate)} – ${formatDate(data.endDate)}`);
        } else if (data.startDate) {
            tags.push(`dal ${formatDate(data.startDate)}`);
        } else if (data.endDate) {
            tags.push(`al ${formatDate(data.endDate)}`);
        }
        return tags;
    };

    // Count of active filters for badge
    const activeFilterCount = [
        authorFilterMode !== "all" && (selectedDeputies.length > 0 || selectedGroups.length > 0),
        docType !== "all",
        !!(startDate || endDate),
    ].filter(Boolean).length;

    return (
        <div className="flex h-screen overflow-hidden bg-white dark:bg-zinc-950">
             <Sidebar isCollapsed={isCollapsed} onToggle={toggle} isMobile={isMobile} isMobileOpen={isMobileOpen} onCloseMobile={closeMobile} />

             <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50/50 dark:bg-slate-950/50">
                {/* Header */}
                <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm shrink-0">
                    <div className="flex items-center gap-3 px-4 sm:px-6 h-14">
                        <MobileMenuButton onClick={toggle} />
                        <h1 className="text-base font-semibold whitespace-nowrap">Ricerca Atti</h1>
                        <div className="flex items-center gap-2 ml-auto shrink-0">
                            {/* Mobile: apre bottom sheet */}
                            <button
                                className="md:hidden inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                                title="Cronologia"
                                onClick={() => setHistorySheetOpen(true)}
                            >
                                <History className="h-4 w-4" />
                            </button>

                            {/* Desktop: popover */}
                            <div className="hidden md:block">
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <button
                                            className="inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                                            title="Cronologia"
                                        >
                                            <History className="h-4 w-4" />
                                        </button>
                                    </PopoverTrigger>
                                    <PopoverContent className="w-80 p-2" align="end">
                                        <p className="text-xs font-medium px-2 py-1 text-muted-foreground mb-1">Cronologia ricerche</p>
                                        {searchHistory.entries.length === 0 ? (
                                            <p className="text-xs text-center py-4 text-muted-foreground">Nessuna ricerca salvata</p>
                                        ) : (
                                            <div className="space-y-0.5">
                                                {searchHistory.entries.map((entry) => {
                                                    const tags = getFilterTags(entry.data);
                                                    return (
                                                        <div key={entry.id} className="flex items-start gap-1 group rounded-md hover:bg-muted/60">
                                                            <button
                                                                className="flex-1 flex items-start gap-2 px-2 py-2 text-left min-w-0"
                                                                onClick={() => restoreSearchEntry(entry.data)}
                                                            >
                                                                <Clock className="h-3 w-3 shrink-0 text-muted-foreground/60 mt-0.5" />
                                                                <div className="min-w-0 space-y-1">
                                                                    <span className="text-xs font-medium truncate block">{entry.topic}</span>
                                                                    {tags.length > 0 && (
                                                                        <div className="flex flex-wrap gap-1">
                                                                            {tags.map((tag, i) => (
                                                                                <span key={i} className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground leading-none">
                                                                                    {tag}
                                                                                </span>
                                                                            ))}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </button>
                                                            <button
                                                                className="shrink-0 p-1.5 mt-0.5 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                                                                onClick={() => searchHistory.removeEntry(entry.id)}
                                                                title="Rimuovi"
                                                            >
                                                                <X className="h-3 w-3" />
                                                            </button>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </PopoverContent>
                                </Popover>
                            </div>
                        </div>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto px-4 md:px-8 py-4 md:py-6">
                    <div className="max-w-4xl mx-auto space-y-6 md:space-y-8 pb-20">

                        {/* Intro */}
                        {!hasSearched && (
                          <div className="text-center space-y-4 pt-2 pb-2">
                            <div className="mx-auto h-14 w-14 rounded-2xl bg-primary/8 flex items-center justify-center">
                              <SearchIcon className="h-7 w-7 text-primary/60" />
                            </div>
                            <div className="space-y-2">
                              <h2 className="text-xl font-semibold text-foreground">
                                Ricerca Atti e Interventi
                              </h2>
                              <p className="text-sm text-muted-foreground leading-relaxed max-w-lg mx-auto">
                                Cerca tra gli atti parlamentari e gli interventi in aula.
                                Puoi filtrare per deputato, gruppo parlamentare, tipo di documento e periodo temporale.
                              </p>
                            </div>
                            <div className="flex flex-wrap justify-center gap-3 pt-1 max-w-md mx-auto">
                              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/40 text-[11px] text-muted-foreground font-medium">
                                <Text className="h-3.5 w-3.5 text-primary/70" />
                                Ricerca testuale
                              </div>
                              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/40 text-[11px] text-muted-foreground font-medium">
                                <Users className="h-3.5 w-3.5 text-primary/70" />
                                Filtra per autore
                              </div>
                              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/40 text-[11px] text-muted-foreground font-medium">
                                <SlidersHorizontal className="h-3.5 w-3.5 text-primary/70" />
                                Tipo e periodo
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Search Card */}
                        <div className="bg-card border rounded-xl shadow-lg overflow-hidden">

                            {/* Search Input */}
                            <div className="p-4 md:p-6 pb-3 md:pb-0">
                                <div className="relative">
                                    <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                                    <Input
                                        placeholder="Cerca negli atti e interventi parlamentari..."
                                        value={query}
                                        onChange={(e) => setQuery(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                                        className="h-14 text-lg pl-12 pr-10 shadow-sm border-2 focus-visible:ring-offset-2 focus-visible:border-primary transition-all rounded-lg"
                                    />
                                    {query && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setQuery("")}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 h-8 w-8 p-0 text-muted-foreground hover:bg-transparent hover:text-foreground"
                                        >
                                            <FilterX className="h-4 w-4" />
                                        </Button>
                                    )}
                                </div>
                            </div>

                            {/* ── MOBILE: compact filter bar ── */}
                            <div className="md:hidden px-4 pt-2 pb-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                    {/* Active filter chips */}
                                    {docType !== "all" && (
                                        <button
                                            onClick={() => setDocType("all")}
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                                        >
                                            {docType === "speech" ? "Interventi" : "Atti"}
                                            <X className="h-3 w-3" />
                                        </button>
                                    )}
                                    {authorFilterMode === "deputy" && selectedDeputies.length > 0 && (
                                        <button
                                            onClick={() => { setAuthorFilterMode("all"); setSelectedDeputies([]); }}
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                                        >
                                            {selectedDeputies.length === 1
                                                ? selectedDeputies[0].last_name
                                                : `${selectedDeputies.length} deputati`}
                                            <X className="h-3 w-3" />
                                        </button>
                                    )}
                                    {authorFilterMode === "group" && selectedGroups.length > 0 && (
                                        <button
                                            onClick={() => { setAuthorFilterMode("all"); setSelectedGroups([]); }}
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                                        >
                                            {selectedGroups.length === 1 ? selectedGroups[0] : `${selectedGroups.length} gruppi`}
                                            <X className="h-3 w-3" />
                                        </button>
                                    )}
                                    {(startDate || endDate) && (
                                        <button
                                            onClick={() => { setStartDate(""); setEndDate(""); }}
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                                        >
                                            {startDate && endDate
                                                ? `${formatDate(startDate)} – ${formatDate(endDate)}`
                                                : startDate
                                                    ? `dal ${formatDate(startDate)}`
                                                    : `al ${formatDate(endDate)}`}
                                            <X className="h-3 w-3" />
                                        </button>
                                    )}

                                    {/* Filtri button */}
                                    <button
                                        onClick={() => setFilterSheetOpen(true)}
                                        className={cn(
                                            "ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors shrink-0",
                                            activeFilterCount > 0
                                                ? "border-primary text-primary bg-primary/5"
                                                : "border-border text-muted-foreground hover:text-foreground hover:bg-muted/40"
                                        )}
                                    >
                                        <SlidersHorizontal className="h-3.5 w-3.5" />
                                        Filtri
                                        {activeFilterCount > 0 && (
                                            <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-primary text-primary-foreground text-[10px] font-bold leading-none">
                                                {activeFilterCount}
                                            </span>
                                        )}
                                    </button>
                                </div>
                            </div>

                            {/* ── DESKTOP: full filter grid ── */}
                            <div className="hidden md:block p-6 space-y-5">
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                                    {/* Left: Author Filter */}
                                    <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                                        <div className="flex items-center gap-2 mb-1">
                                            <User className="h-4 w-4 text-primary" />
                                            <Label className="text-sm font-semibold">Autore</Label>
                                            <span className="text-xs text-muted-foreground ml-auto">Opzionale</span>
                                        </div>
                                        <div className="inline-flex rounded-lg border p-0.5 bg-background w-full">
                                            {([
                                                { value: "all" as const, label: "Tutti" },
                                                { value: "deputy" as const, label: "Deputato" },
                                                { value: "group" as const, label: "Gruppo" },
                                            ]).map((tab) => (
                                                <button
                                                    key={tab.value}
                                                    onClick={() => handleAuthorModeChange(tab.value)}
                                                    className={cn(
                                                        "flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                                                        authorFilterMode === tab.value
                                                            ? "bg-primary text-primary-foreground shadow-sm"
                                                            : "text-muted-foreground hover:text-foreground"
                                                    )}
                                                >
                                                    {tab.label}
                                                </button>
                                            ))}
                                        </div>
                                        <div className="min-h-[42px]">
                                            {authorFilterMode === "all" && (
                                                <p className="text-sm text-muted-foreground text-center py-2 bg-background rounded-md border border-dashed">
                                                    Ricerca in tutti gli atti e interventi
                                                </p>
                                            )}
                                            {authorFilterMode === "deputy" && (
                                                <DeputySelector
                                                    selectedDeputies={selectedDeputies}
                                                    onSelect={setSelectedDeputies}
                                                />
                                            )}
                                            {authorFilterMode === "group" && (
                                                <GroupSelector
                                                    selectedGroups={selectedGroups}
                                                    onSelect={setSelectedGroups}
                                                />
                                            )}
                                        </div>
                                    </div>

                                    {/* Right: Doc Type + Date */}
                                    <div className="space-y-5">
                                        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                                            <div className="flex items-center gap-2 mb-1">
                                                <FileText className="h-4 w-4 text-primary" />
                                                <Label className="text-sm font-semibold">Tipo Documento</Label>
                                            </div>
                                            <div className="inline-flex rounded-lg border p-0.5 bg-background w-full">
                                                {([
                                                    { value: "all" as const, label: "Tutti", icon: null },
                                                    { value: "speech" as const, label: "Interventi", icon: MessageSquareQuote },
                                                    { value: "act" as const, label: "Atti", icon: FileText },
                                                ]).map((tab) => (
                                                    <button
                                                        key={tab.value}
                                                        onClick={() => setDocType(tab.value)}
                                                        className={cn(
                                                            "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                                                            docType === tab.value
                                                                ? "bg-primary text-primary-foreground shadow-sm"
                                                                : "text-muted-foreground hover:text-foreground"
                                                        )}
                                                    >
                                                        {tab.icon && <tab.icon className="h-3.5 w-3.5" />}
                                                        {tab.label}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                                            <div className="flex items-center gap-2 mb-1">
                                                <Calendar className="h-4 w-4 text-primary" />
                                                <Label className="text-sm font-semibold">Periodo</Label>
                                                <span className="text-xs text-muted-foreground ml-auto">Opzionale</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-3">
                                                <div className="space-y-1.5">
                                                    <Label className="text-xs text-muted-foreground">Da</Label>
                                                    <Input
                                                        type="date"
                                                        value={startDate}
                                                        onChange={(e) => setStartDate(e.target.value)}
                                                        className="h-9 bg-background"
                                                    />
                                                </div>
                                                <div className="space-y-1.5">
                                                    <Label className="text-xs text-muted-foreground">A</Label>
                                                    <Input
                                                        type="date"
                                                        value={endDate}
                                                        onChange={(e) => setEndDate(e.target.value)}
                                                        className="h-9 bg-background"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Action Buttons (always visible) */}
                            <div className="px-4 md:px-6 pb-4 md:pb-6 pt-3 flex gap-3">
                                <Button
                                    size="lg"
                                    disabled={!query.trim() || loading}
                                    onClick={handleSearch}
                                    className="flex-1 h-12 text-base font-semibold shadow-md transition-all hover:shadow-lg"
                                >
                                    {loading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <SearchIcon className="mr-2 h-5 w-5" />}
                                    Esegui Ricerca
                                </Button>
                                {hasSearched && (
                                    <Button
                                        variant="outline"
                                        size="lg"
                                        onClick={clearFilters}
                                        className="h-12 px-5 text-muted-foreground"
                                    >
                                        <FilterX className="mr-2 h-4 w-4" />
                                        Resetta
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Search Stats & Results */}
                        {(hasSearched) && (
                            <div id="search-results" className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">

                                {/* Results header */}
                                <div className="px-2 space-y-3">
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-1 bg-primary rounded-full shrink-0"></div>
                                        <div>
                                            <h2 className="text-xl font-bold tracking-tight">Risultati</h2>
                                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                                                <span>{totalResults} risultati</span>
                                                {results.length > 0 && (
                                                    <>
                                                        <span className="text-muted-foreground/50">—</span>
                                                        <span>Pagina {currentPage} di {totalPages}</span>
                                                    </>
                                                )}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Sort controls — riga dedicata, label sempre visibili */}
                                    {results.length > 0 && (
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-muted-foreground shrink-0">Ordina:</span>
                                            <div className="inline-flex rounded-lg border p-0.5 bg-card shadow-sm flex-1 sm:flex-none">
                                                {([
                                                    { value: "relevance" as const, label: "Rilevanza", icon: ArrowUpDown },
                                                    { value: "date_desc" as const, label: "Più recenti", icon: ArrowDown },
                                                    { value: "date_asc" as const, label: "Meno recenti", icon: ArrowUp },
                                                ]).map((opt) => (
                                                    <button
                                                        key={opt.value}
                                                        onClick={() => handleSortChange(opt.value)}
                                                        className={cn(
                                                            "flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all",
                                                            sortBy === opt.value
                                                                ? "bg-primary text-primary-foreground shadow-sm"
                                                                : "text-muted-foreground hover:text-foreground"
                                                        )}
                                                    >
                                                        <opt.icon className="h-3.5 w-3.5 shrink-0" />
                                                        {opt.label}
                                                    </button>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {loading ? (
                                    <div className="flex flex-col items-center justify-center py-20 space-y-4 border rounded-xl bg-card/50">
                                        <Loader2 className="h-10 w-10 animate-spin text-primary" />
                                        <p className="text-muted-foreground animate-pulse">
                                            Ricerca in corso...
                                        </p>
                                    </div>
                                ) : (
                                    <>
                                        <ResultsList results={results} query={query} />

                                        {/* Pagination */}
                                        {totalPages > 1 && (
                                            <div className="flex items-center justify-center gap-1 sm:gap-2 pt-4 flex-wrap">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={currentPage <= 1}
                                                    onClick={() => handlePageChange(currentPage - 1)}
                                                >
                                                    <ChevronLeft className="h-4 w-4 sm:mr-1" />
                                                    <span className="hidden sm:inline">Precedente</span>
                                                </Button>

                                                <div className="flex items-center gap-1">
                                                    {generatePageNumbers(currentPage, totalPages).map((p, i) =>
                                                        p === "..." ? (
                                                            <span key={`ellipsis-${i}`} className="px-1 sm:px-2 text-muted-foreground">...</span>
                                                        ) : (
                                                            <Button
                                                                key={p}
                                                                variant={p === currentPage ? "default" : "outline"}
                                                                size="sm"
                                                                className="w-8 h-8 sm:w-9 sm:h-9 p-0"
                                                                onClick={() => handlePageChange(p as number)}
                                                            >
                                                                {p}
                                                            </Button>
                                                        )
                                                    )}
                                                </div>

                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={currentPage >= totalPages}
                                                    onClick={() => handlePageChange(currentPage + 1)}
                                                >
                                                    <span className="hidden sm:inline">Successiva</span>
                                                    <ChevronRight className="h-4 w-4 sm:ml-1" />
                                                </Button>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </div>
             </main>

            {/* ── MOBILE HISTORY SHEET ── */}
            <Sheet open={historySheetOpen} onOpenChange={setHistorySheetOpen}>
                <SheetContent side="bottom" showCloseButton={false} className="rounded-t-2xl max-h-[80vh] flex flex-col p-0">
                    <SheetHeader className="px-4 pt-4 pb-3 shrink-0 border-b">
                        <div className="flex items-center justify-between">
                            <SheetTitle className="flex items-center gap-2 text-base">
                                <History className="h-4 w-4 text-primary" />
                                Cronologia ricerche
                            </SheetTitle>
                            <SheetClose asChild>
                                <button className="inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent">
                                    <X className="h-4 w-4" />
                                </button>
                            </SheetClose>
                        </div>
                    </SheetHeader>
                    <div className="flex-1 overflow-y-auto py-2">
                        {searchHistory.entries.length === 0 ? (
                            <p className="text-sm text-center py-10 text-muted-foreground">Nessuna ricerca salvata</p>
                        ) : (
                            <div className="px-4 space-y-0.5 pb-8">
                                {searchHistory.entries.map((entry) => {
                                    const tags = getFilterTags(entry.data);
                                    return (
                                        <div key={entry.id} className="flex items-start gap-1 group rounded-md hover:bg-muted/60">
                                            <button
                                                className="flex-1 flex items-start gap-3 px-2 py-3 text-left min-w-0"
                                                onClick={() => { restoreSearchEntry(entry.data); setHistorySheetOpen(false); }}
                                            >
                                                <Clock className="h-4 w-4 shrink-0 text-muted-foreground/60 mt-0.5" />
                                                <div className="min-w-0 space-y-1">
                                                    <span className="text-sm font-medium truncate block">{entry.topic}</span>
                                                    {tags.length > 0 && (
                                                        <div className="flex flex-wrap gap-1">
                                                            {tags.map((tag, i) => (
                                                                <span key={i} className="inline-block text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground leading-none">
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </button>
                                            <button
                                                className="shrink-0 p-2.5 mt-0.5 text-muted-foreground hover:text-destructive transition-colors"
                                                onClick={() => searchHistory.removeEntry(entry.id)}
                                                title="Rimuovi"
                                            >
                                                <X className="h-4 w-4" />
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </SheetContent>
            </Sheet>

            {/* ── MOBILE FILTER SHEET ── */}
            <Sheet open={filterSheetOpen} onOpenChange={setFilterSheetOpen}>
                <SheetContent side="bottom" showCloseButton={false} className="rounded-t-2xl max-h-[90vh] flex flex-col p-0">
                    <SheetHeader className="px-4 pt-4 pb-0 shrink-0">
                        <div className="flex items-center justify-between">
                            <SheetTitle className="text-base">Filtri</SheetTitle>
                            <SheetClose asChild>
                                <button className="inline-flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent">
                                    <X className="h-4 w-4" />
                                </button>
                            </SheetClose>
                        </div>

                        {/* Tab bar */}
                        <div className="flex gap-1 mt-3 border-b pb-0">
                            {([
                                { key: "autore" as const, label: "Autore", icon: User,
                                  active: authorFilterMode !== "all" && (selectedDeputies.length > 0 || selectedGroups.length > 0) },
                                { key: "tipo" as const, label: "Tipo", icon: FileText,
                                  active: docType !== "all" },
                                { key: "periodo" as const, label: "Periodo", icon: Calendar,
                                  active: !!(startDate || endDate) },
                            ]).map((tab) => (
                                <button
                                    key={tab.key}
                                    onClick={() => setFilterTab(tab.key)}
                                    className={cn(
                                        "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px",
                                        filterTab === tab.key
                                            ? "border-primary text-primary"
                                            : "border-transparent text-muted-foreground hover:text-foreground"
                                    )}
                                >
                                    <tab.icon className="h-3.5 w-3.5" />
                                    {tab.label}
                                    {tab.active && (
                                        <span className="inline-flex items-center justify-center w-1.5 h-1.5 rounded-full bg-primary" />
                                    )}
                                </button>
                            ))}
                        </div>
                    </SheetHeader>

                    {/* Tab content */}
                    <div className="flex-1 overflow-y-auto px-4 py-4">

                        {/* Autore tab */}
                        {filterTab === "autore" && (
                            <div className="space-y-4">
                                <div className="inline-flex rounded-lg border p-0.5 bg-muted/30 w-full">
                                    {([
                                        { value: "all" as const, label: "Tutti" },
                                        { value: "deputy" as const, label: "Deputato" },
                                        { value: "group" as const, label: "Gruppo" },
                                    ]).map((tab) => (
                                        <button
                                            key={tab.value}
                                            onClick={() => handleAuthorModeChange(tab.value)}
                                            className={cn(
                                                "flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all",
                                                authorFilterMode === tab.value
                                                    ? "bg-primary text-primary-foreground shadow-sm"
                                                    : "text-muted-foreground hover:text-foreground"
                                            )}
                                        >
                                            {tab.label}
                                        </button>
                                    ))}
                                </div>

                                <div className="min-h-[60px]">
                                    {authorFilterMode === "all" && (
                                        <p className="text-sm text-muted-foreground text-center py-4 bg-muted/20 rounded-lg border border-dashed">
                                            Ricerca in tutti gli atti e interventi
                                        </p>
                                    )}
                                    {authorFilterMode === "deputy" && (
                                        <DeputySelector
                                            selectedDeputies={selectedDeputies}
                                            onSelect={setSelectedDeputies}
                                        />
                                    )}
                                    {authorFilterMode === "group" && (
                                        <GroupSelector
                                            selectedGroups={selectedGroups}
                                            onSelect={setSelectedGroups}
                                        />
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Tipo tab */}
                        {filterTab === "tipo" && (
                            <div className="space-y-3">
                                <p className="text-sm text-muted-foreground">Scegli il tipo di documento da cercare.</p>
                                <div className="grid grid-cols-3 gap-3">
                                    {([
                                        { value: "all" as const, label: "Tutti", icon: null, desc: "Atti e interventi" },
                                        { value: "speech" as const, label: "Interventi", icon: MessageSquareQuote, desc: "Discorsi in aula" },
                                        { value: "act" as const, label: "Atti", icon: FileText, desc: "Atti parlamentari" },
                                    ]).map((opt) => (
                                        <button
                                            key={opt.value}
                                            onClick={() => setDocType(opt.value)}
                                            className={cn(
                                                "flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-center",
                                                docType === opt.value
                                                    ? "border-primary bg-primary/5 text-primary"
                                                    : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                                            )}
                                        >
                                            {opt.icon ? (
                                                <opt.icon className="h-5 w-5" />
                                            ) : (
                                                <SearchIcon className="h-5 w-5" />
                                            )}
                                            <span className="text-sm font-semibold">{opt.label}</span>
                                            <span className="text-[11px] text-muted-foreground leading-tight">{opt.desc}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Periodo tab */}
                        {filterTab === "periodo" && (
                            <div className="space-y-4">
                                <p className="text-sm text-muted-foreground">Filtra per intervallo di date. Entrambi i campi sono opzionali.</p>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1.5">
                                        <Label className="text-sm font-medium">Data inizio</Label>
                                        <Input
                                            type="date"
                                            value={startDate}
                                            onChange={(e) => setStartDate(e.target.value)}
                                            className="h-11 bg-background"
                                        />
                                    </div>
                                    <div className="space-y-1.5">
                                        <Label className="text-sm font-medium">Data fine</Label>
                                        <Input
                                            type="date"
                                            value={endDate}
                                            onChange={(e) => setEndDate(e.target.value)}
                                            className="h-11 bg-background"
                                        />
                                    </div>
                                </div>
                                {(startDate || endDate) && (
                                    <button
                                        onClick={() => { setStartDate(""); setEndDate(""); }}
                                        className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1 transition-colors"
                                    >
                                        <X className="h-3 w-3" />
                                        Rimuovi filtro periodo
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Sheet footer */}
                    <SheetFooter className="px-4 pb-6 pt-3 shrink-0 border-t">
                        <SheetClose asChild>
                            <Button className="w-full h-12 text-base font-semibold">
                                Applica filtri
                                {activeFilterCount > 0 && (
                                    <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary-foreground/20 text-[11px] font-bold">
                                        {activeFilterCount}
                                    </span>
                                )}
                            </Button>
                        </SheetClose>
                    </SheetFooter>
                </SheetContent>
            </Sheet>
        </div>
    );
}

function generatePageNumbers(current: number, total: number): (number | "...")[] {
    if (total <= 7) {
        return Array.from({ length: total }, (_, i) => i + 1);
    }

    const pages: (number | "...")[] = [1];

    if (current > 3) {
        pages.push("...");
    }

    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);

    for (let i = start; i <= end; i++) {
        pages.push(i);
    }

    if (current < total - 2) {
        pages.push("...");
    }

    pages.push(total);
    return pages;
}
