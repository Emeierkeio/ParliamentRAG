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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Search as SearchIcon,
    Loader2,
    FilterX,
    Sparkles,
    FileText,
    MessageSquareQuote,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { config } from "@/config";

export default function SearchPage() {
    const { isCollapsed, toggle } = useSidebar();
    
    // State
    const [query, setQuery] = useState("");
    const [selectedDeputy, setSelectedDeputy] = useState<Deputy | null>(null);
    const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [searchType, setSearchType] = useState<"text" | "semantic" | "hybrid">("text");

    const [results, setResults] = useState<SearchResultItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [hasSearched, setHasSearched] = useState(false);

    const handleSearch = async () => {
        if (!query.trim()) return;
        
        setLoading(true);
        setHasSearched(true);
        setResults([]);
        
        try {
            const params = new URLSearchParams();
            params.append('q', query);
            params.append('limit', '100');
            params.append('search_type', searchType);
            
            if (selectedDeputy) {
                params.append('deputy_id', selectedDeputy.id);
            }
            if (selectedGroup && !selectedDeputy) { 
                params.append('group', selectedGroup);
            }
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);

            const res = await fetch(`${config.api.baseUrl}/search/results?${params.toString()}`);
            if (res.ok) {
                const data = await res.json();
                setResults(data);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }

    const clearFilters = () => {
        setQuery("");
        setSelectedDeputy(null);
        setSelectedGroup(null);
        setStartDate("");
        setEndDate("");
        setSearchType("text");
        setResults([]);
        setHasSearched(false);
    }

    const speechCount = results.filter(r => r.type === "speech").length;
    const actCount = results.filter(r => r.type === "act").length;

    return (
        <div className="flex h-screen overflow-hidden bg-white dark:bg-zinc-950">
             <Sidebar isCollapsed={isCollapsed} onToggle={toggle} />
             
             <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50/50 dark:bg-slate-950/50">
                {/* Header Page */}
                <div className="border-b px-8 py-5 bg-background flex items-center justify-between sticky top-0 z-10 shrink-0">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Ricerca</h1>
                        <p className="text-muted-foreground">Esplorazione diretta degli atti e interventi parlamentari</p>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto px-8 py-6">
                    <div className="max-w-4xl mx-auto space-y-8 pb-20">
                        
                        {/* Search Main Card */}
                        <div className="bg-card border rounded-xl shadow-lg overflow-hidden transition-all hover:shadow-xl">
                            <div className="p-8 space-y-8">
                                
                                {/* Main Search Input */}
                                <div className="space-y-4">
                                     <div className="relative">
                                         <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-6 w-6 text-muted-foreground" />
                                         <Input 
                                            placeholder="Cerca negli atti e interventi parlamentari (es. superbonus, pnrr, diminuzione tassazione)..." 
                                            value={query}
                                            onChange={(e) => setQuery(e.target.value)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                                            className="h-16 text-xl px-14 shadow-sm border-2 focus-visible:ring-offset-2 focus-visible:border-primary transition-all rounded-lg"
                                         />
                                         {query && (
                                              <Button 
                                                variant="ghost" 
                                                size="sm" 
                                                onClick={() => setQuery("")}
                                                className="absolute right-4 top-1/2 -translate-y-1/2 h-8 w-8 p-0 text-muted-foreground hover:bg-transparent hover:text-foreground"
                                              >
                                                  <FilterX className="h-4 w-4" />
                                              </Button>
                                         )}
                                    </div>
                                </div>

                                {/* Search Type Toggle */}
                                <div className="flex items-center gap-2">
                                    <Label className="text-sm font-semibold mr-2">Modalità:</Label>
                                    <div className="inline-flex rounded-lg border p-0.5 bg-muted/30">
                                        <button
                                            onClick={() => setSearchType("text")}
                                            className={cn(
                                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                                                searchType === "text"
                                                    ? "bg-background shadow-sm text-foreground"
                                                    : "text-muted-foreground hover:text-foreground"
                                            )}
                                        >
                                            <SearchIcon className="h-3.5 w-3.5" />
                                            Testuale
                                        </button>
                                        <button
                                            onClick={() => setSearchType("semantic")}
                                            className={cn(
                                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                                                searchType === "semantic"
                                                    ? "bg-background shadow-sm text-foreground"
                                                    : "text-muted-foreground hover:text-foreground"
                                            )}
                                        >
                                            <Sparkles className="h-3.5 w-3.5" />
                                            Semantica
                                        </button>
                                        <button
                                            onClick={() => setSearchType("hybrid")}
                                            className={cn(
                                                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
                                                searchType === "hybrid"
                                                    ? "bg-background shadow-sm text-foreground"
                                                    : "text-muted-foreground hover:text-foreground"
                                            )}
                                        >
                                            <SearchIcon className="h-3.5 w-3.5" />
                                            <Sparkles className="h-3.5 w-3.5 -ml-1" />
                                            Ibrida
                                        </button>
                                    </div>
                                </div>

                                {/* Filters Sections */}
                                <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
                                    
                                    {/* Author Filter (Col 1 - Span 7) */}
                                    <div className="md:col-span-7 space-y-3">
                                        <Label className="text-sm font-semibold flex items-center gap-2">
                                            Filtra per Autore (Opzionale)
                                        </Label>
                                        <Tabs 
                                            defaultValue="all" 
                                            className="w-full text-foreground/80 font-normal"
                                            onValueChange={(val) => {
                                                if(val === 'deputy') setSelectedGroup(null);
                                                if(val === 'group') setSelectedDeputy(null);
                                                if(val === 'all') { setSelectedDeputy(null); setSelectedGroup(null); }
                                            }}
                                        >
                                            <TabsList className="grid w-full grid-cols-3 mb-4">
                                                <TabsTrigger value="all">Tutti</TabsTrigger>
                                                <TabsTrigger value="deputy">Deputato</TabsTrigger>
                                                <TabsTrigger value="group">Gruppo</TabsTrigger>
                                            </TabsList>
                                            
                                            <TabsContent value="all" className="text-sm text-muted-foreground py-2 text-center bg-muted/20 rounded-md border border-dashed">
                                                Ricerca in tutti gli atti e interventi
                                            </TabsContent>
                                            
                                            <TabsContent value="deputy" className="space-y-2">
                                                <DeputySelector 
                                                    selectedDeputy={selectedDeputy} 
                                                    onSelect={setSelectedDeputy} 
                                                />
                                            </TabsContent>
                                            
                                            <TabsContent value="group" className="space-y-2">
                                                <GroupSelector 
                                                    selectedGroup={selectedGroup}
                                                    onSelect={setSelectedGroup}
                                                />
                                            </TabsContent>
                                        </Tabs>
                                    </div>

                                    {/* Date Filter (Col 2 - Span 5) */}
                                    <div className="md:col-span-5 space-y-3">
                                         <Label className="text-sm font-semibold flex items-center gap-2">
                                            Periodo
                                        </Label>
                                        <div className="bg-muted/30 p-4 rounded-lg border space-y-3">
                                            <div className="grid gap-2">
                                                <Label className="text-xs text-muted-foreground">Da</Label>
                                                <Input 
                                                    type="date" 
                                                    value={startDate}
                                                    onChange={(e) => setStartDate(e.target.value)}
                                                    className="h-9 bg-background"
                                                />
                                            </div>
                                            <div className="grid gap-2">
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

                                {/* Main Action */}
                                <div className="pt-2">
                                    <Button 
                                        size="lg"
                                        disabled={!query.trim() || loading} 
                                        onClick={handleSearch}
                                        className="w-full py-6 text-lg font-semibold shadow-xl transition-all hover:scale-[1.01]"
                                    >
                                        {loading ? <Loader2 className="mr-2 h-6 w-6 animate-spin" /> : <SearchIcon className="mr-2 h-6 w-6" />}
                                        Esegui Ricerca
                                    </Button>
                                    {(hasSearched) && (
                                         <Button 
                                            variant="link" 
                                            size="sm" 
                                            onClick={clearFilters} 
                                            className="w-full mt-2 text-muted-foreground"
                                         >
                                            Resetta filtri
                                         </Button>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Search Stats & Results */}
                        {(hasSearched) && (
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
                                <div className="flex items-center justify-between px-2">
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-1 bg-primary rounded-full"></div>
                                        <div>
                                            <h2 className="text-xl font-bold tracking-tight">Risultati</h2>
                                            <p className="text-sm text-muted-foreground flex items-center gap-2">
                                                <span>{results.length} risultati</span>
                                                {results.length > 0 && (
                                                    <>
                                                        <span className="text-muted-foreground/50">—</span>
                                                        <span className="flex items-center gap-1">
                                                            <MessageSquareQuote className="h-3 w-3" />
                                                            {speechCount} interventi
                                                        </span>
                                                        <span className="flex items-center gap-1">
                                                            <FileText className="h-3 w-3" />
                                                            {actCount} atti
                                                        </span>
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
                                            {searchType === "semantic" || searchType === "hybrid"
                                                ? "Ricerca semantica in corso..."
                                                : "Scansione degli atti parlamentari in corso..."}
                                        </p>
                                    </div>
                                ) : (
                                    <ResultsList results={results} query={query} />
                                )}
                            </div>
                        )}
                    </div>
                </div>
             </main>
        </div>
    )
}
