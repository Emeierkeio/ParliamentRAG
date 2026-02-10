"use client";

import { useState } from "react";
import { Sidebar } from "@/components/layout";
import { useSidebar } from "@/hooks";
import { DeputySelector, Deputy } from "@/components/search/DeputySelector";
import { GroupSelector } from "@/components/search/GroupSelector";
import { ResultsList, SearchResultItem } from "@/components/search/ResultsList";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { config } from "@/config";

const PAGE_SIZE = 20;

export default function SearchPage() {
    const { isCollapsed, toggle } = useSidebar();

    // State
    const [query, setQuery] = useState("");
    const [selectedDeputy, setSelectedDeputy] = useState<Deputy | null>(null);
    const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [docType, setDocType] = useState<"all" | "speech" | "act">("all");
    const [authorFilterMode, setAuthorFilterMode] = useState<"all" | "deputy" | "group">("all");

    const [results, setResults] = useState<SearchResultItem[]>([]);
    const [totalResults, setTotalResults] = useState(0);
    const [totalPages, setTotalPages] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [hasSearched, setHasSearched] = useState(false);

    const fetchPage = async (page: number) => {
        if (!query.trim()) return;

        setLoading(true);
        setResults([]);

        try {
            const params = new URLSearchParams();
            params.append('q', query);
            params.append('search_type', 'hybrid');
            params.append('doc_type', docType);
            params.append('page', String(page));
            params.append('page_size', String(PAGE_SIZE));

            if (selectedDeputy && authorFilterMode === 'deputy') {
                params.append('deputy_id', selectedDeputy.id);
            }
            if (selectedGroups.length > 0 && authorFilterMode === 'group') {
                for (const g of selectedGroups) {
                    params.append('group', g);
                }
            }
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);

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
    };

    const handlePageChange = async (page: number) => {
        await fetchPage(page);
        document.getElementById("search-results")?.scrollIntoView({ behavior: "smooth" });
    };

    const clearFilters = () => {
        setQuery("");
        setSelectedDeputy(null);
        setSelectedGroups([]);
        setStartDate("");
        setEndDate("");
        setDocType("all");
        setAuthorFilterMode("all");
        setResults([]);
        setTotalResults(0);
        setTotalPages(0);
        setCurrentPage(1);
        setHasSearched(false);
    }

    const handleAuthorModeChange = (mode: "all" | "deputy" | "group") => {
        setAuthorFilterMode(mode);
        if (mode === 'deputy') setSelectedGroups([]);
        if (mode === 'group') setSelectedDeputy(null);
        if (mode === 'all') { setSelectedDeputy(null); setSelectedGroups([]); }
    };

    return (
        <div className="flex h-screen overflow-hidden bg-white dark:bg-zinc-950">
             <Sidebar isCollapsed={isCollapsed} onToggle={toggle} />

             <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50/50 dark:bg-slate-950/50">
                {/* Header */}
                <div className="border-b px-8 py-5 bg-background flex items-center justify-between sticky top-0 z-10 shrink-0">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Ricerca</h1>
                        <p className="text-muted-foreground">Esplorazione diretta degli atti e interventi parlamentari</p>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto px-8 py-6">
                    <div className="max-w-4xl mx-auto space-y-8 pb-20">

                        {/* Search Card */}
                        <div className="bg-card border rounded-xl shadow-lg overflow-hidden">

                            {/* Search Input */}
                            <div className="p-6 pb-0">
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

                            {/* Filters Grid */}
                            <div className="p-6 space-y-5">
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                                    {/* Left: Author Filter */}
                                    <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
                                        <div className="flex items-center gap-2 mb-1">
                                            <User className="h-4 w-4 text-primary" />
                                            <Label className="text-sm font-semibold">Autore</Label>
                                            <span className="text-xs text-muted-foreground ml-auto">Opzionale</span>
                                        </div>

                                        {/* Author mode tabs */}
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

                                        {/* Author filter content */}
                                        <div className="min-h-[42px]">
                                            {authorFilterMode === "all" && (
                                                <p className="text-sm text-muted-foreground text-center py-2 bg-background rounded-md border border-dashed">
                                                    Ricerca in tutti gli atti e interventi
                                                </p>
                                            )}
                                            {authorFilterMode === "deputy" && (
                                                <DeputySelector
                                                    selectedDeputy={selectedDeputy}
                                                    onSelect={setSelectedDeputy}
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
                                        {/* Document Type */}
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

                                        {/* Date Range */}
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

                                {/* Action Buttons */}
                                <div className="flex gap-3 pt-1">
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
                        </div>

                        {/* Search Stats & Results */}
                        {(hasSearched) && (
                            <div id="search-results" className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
                                <div className="flex items-center justify-between px-2">
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-1 bg-primary rounded-full"></div>
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
                                            <div className="flex items-center justify-center gap-2 pt-4">
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={currentPage <= 1}
                                                    onClick={() => handlePageChange(currentPage - 1)}
                                                >
                                                    <ChevronLeft className="h-4 w-4 mr-1" />
                                                    Precedente
                                                </Button>

                                                <div className="flex items-center gap-1">
                                                    {generatePageNumbers(currentPage, totalPages).map((p, i) =>
                                                        p === "..." ? (
                                                            <span key={`ellipsis-${i}`} className="px-2 text-muted-foreground">...</span>
                                                        ) : (
                                                            <Button
                                                                key={p}
                                                                variant={p === currentPage ? "default" : "outline"}
                                                                size="sm"
                                                                className="w-9 h-9 p-0"
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
                                                    Successiva
                                                    <ChevronRight className="h-4 w-4 ml-1" />
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
        </div>
    )
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
