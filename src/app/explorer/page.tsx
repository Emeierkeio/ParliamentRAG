"use client";

import { useState, useEffect } from "react";
import {
    Search,
    Play,
    Table as TableIcon,
    Code,
    RefreshCcw,
    Layers,
    ArrowRightLeft,
    Share2,
    Landmark
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getGraphSchema, getGraphStats, executeCypherQuery } from "@/lib/graph-api";
import { config } from "@/config";
import { GraphVisualizer } from "@/components/graph/GraphVisualizer";

export default function ExplorerPage() {
    const [schema, setSchema] = useState<any>(null);
    const [stats, setStats] = useState<any>(null);
    const [query, setQuery] = useState("MATCH (n:Deputy) RETURN n.first_name, n.last_name LIMIT 10");
    const [results, setResults] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [history, setHistory] = useState<string[]>([]);

    useEffect(() => {
        loadSchema();
    }, []);

    const loadSchema = async () => {
        try {
            const [s, st] = await Promise.all([getGraphSchema(), getGraphStats()]);
            setSchema(s);
            setStats(st);
        } catch (err) {
            console.error(err);
        }
    };

    const runQuery = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await executeCypherQuery(query);
            setResults(data);
            if (!history.includes(query)) {
                setHistory(prev => [query, ...prev].slice(0, 10));
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Errore query");
            setResults([]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSchemaClick = (text: string, type: 'label' | 'rel') => {
        if (type === 'label') {
            setQuery(`MATCH (n:${text}) RETURN n LIMIT 25`);
        } else {
            setQuery(`MATCH ()-[r:${text}]->() RETURN r LIMIT 25`);
        }
    };

    return (
        <div className="flex h-screen overflow-hidden bg-background">
            {/* Sidebar (Schema) */}
            <div className="w-[300px] border-r border-border bg-muted/10 flex flex-col">
                <div className="p-4 border-b border-border">
                    <div
                        className="flex items-center gap-3 cursor-pointer"
                        onClick={() => window.location.href = "/"}
                    >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                            <Landmark className="h-5 w-5" />
                        </div>
                        <div className="flex flex-col">
                            <span className="text-sm font-bold tracking-tight text-foreground">
                                {config.app.name}
                            </span>
                        </div>
                    </div>
                    {stats && (
                        <div className="text-xs text-muted-foreground mt-2 flex gap-2">
                             <span>Nodes: {stats.total_nodes}</span>
                             <span>•</span>
                             <span>Rels: {stats.total_relationships}</span>
                        </div>
                    )}
                </div>
                
                <ScrollArea className="flex-1">
                    <div className="p-4 space-y-6">
                        {/* Labels */}
                        <div>
                            <h3 className="text-xs font-bold text-muted-foreground uppercase mb-3 flex items-center gap-2">
                                <Layers className="h-3 w-3" />
                                Labels
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {schema?.labels?.map((label: string) => (
                                    <Badge 
                                        key={label} 
                                        variant="outline" 
                                        className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors"
                                        onClick={() => handleSchemaClick(label, 'label')}
                                    >
                                        {label}
                                    </Badge>
                                ))}
                            </div>
                        </div>

                        <Separator />

                        {/* Relationships */}
                        <div>
                            <h3 className="text-xs font-bold text-muted-foreground uppercase mb-3 flex items-center gap-2">
                                <ArrowRightLeft className="h-3 w-3" />
                                Relationships
                            </h3>
                             <div className="flex flex-col gap-1">
                                {schema?.relationship_types?.map((rel: string) => (
                                    <button 
                                        key={rel}
                                        className="text-xs text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors truncate font-mono"
                                        onClick={() => handleSchemaClick(rel, 'rel')}
                                    >
                                        :{rel}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                </ScrollArea>
            </div>

            {/* Main Content (Query & Results) */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Query Toolbar */}
                <div className="p-4 border-b border-border bg-background flex justify-between items-center">
                    <h1 className="text-lg font-bold">Graph Explorer</h1>
                     <div className="flex items-center gap-2">
                        <Button size="sm" variant="ghost" onClick={loadSchema}>
                            <RefreshCcw className="h-4 w-4 mr-2" />
                            Refresh
                        </Button>
                        <Button size="sm" onClick={runQuery} disabled={isLoading}>
                            <Play className="h-4 w-4 mr-2 fill-current" />
                            Run Query
                        </Button>
                     </div>
                </div>

                {/* Query Editor */}
                <div className="h-[200px] border-b border-border relative bg-muted/5">
                    <Textarea 
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="w-full h-full font-mono text-sm p-4 resize-none border-0 focus-visible:ring-0 bg-transparent"
                        placeholder="Enter Cypher query..."
                    />
                    <div className="absolute bottom-2 right-2 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded">
                        Shift+Enter to run
                    </div>
                </div>

                {/* Results */}
                <div className="flex-1 flex flex-col min-h-0 bg-background">
                    {error ? (
                        <div className="p-4">
                            <Alert variant="destructive">
                                <AlertTitle>Query Error</AlertTitle>
                                <AlertDescription className="font-mono text-xs mt-2">
                                    {error}
                                </AlertDescription>
                            </Alert>
                        </div>
                    ) : (
                        <Tabs defaultValue="table" className="flex-1 flex flex-col">
                            <div className="px-4 border-b border-border flex items-center justify-between">
                                <TabsList className="my-2">
                                    <TabsTrigger value="table">
                                        <TableIcon className="h-4 w-4 mr-2" />
                                        Table
                                    </TabsTrigger>
                                    <TabsTrigger value="graph">
                                        <Share2 className="h-4 w-4 mr-2" />
                                        Graph
                                    </TabsTrigger>
                                    <TabsTrigger value="json">
                                        <Code className="h-4 w-4 mr-2" />
                                        JSON
                                    </TabsTrigger>
                                </TabsList>
                                <div className="text-xs text-muted-foreground">
                                    {results.length} records found
                                </div>
                            </div>
                            
                            <TabsContent value="table" className="flex-1 min-h-0 p-0 m-0">
                                <ScrollArea className="h-full">
                                    <div className="p-4">
                                        {results.length > 0 ? (
                                            <div className="rounded-md border overflow-x-auto">
                                                <table className="w-full text-sm">
                                                    <thead className="bg-muted text-left">
                                                        <tr>
                                                            {Object.keys(results[0]).map(key => (
                                                                <th key={key} className="p-3 font-medium text-muted-foreground whitespace-nowrap border-b border-border/50">
                                                                    {key}
                                                                </th>
                                                            ))}
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {results.map((row, i) => (
                                                            <tr key={i} className="border-b last:border-0 hover:bg-muted/5">
                                                                {Object.values(row).map((val: any, j) => (
                                                                    <td key={j} className="p-3 max-w-[300px] truncate border-r last:border-0 border-border/50">
                                                                        {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                                                                    </td>
                                                                ))}
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        ) : (
                                            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
                                                <Search className="h-10 w-10 mb-4 opacity-20" />
                                                <p>No results found</p>
                                            </div>
                                        )}
                                    </div>
                                </ScrollArea>
                            </TabsContent>
                            
                            <TabsContent value="graph" className="flex-1 min-h-0 p-0 m-0 overflow-hidden">
                                <GraphVisualizer data={results} />
                            </TabsContent>

                            <TabsContent value="json" className="flex-1 min-h-0 p-0 m-0">
                                <ScrollArea className="h-full">
                                    <pre className="p-4 text-xs font-mono">
                                        {JSON.stringify(results, null, 2)}
                                    </pre>
                                </ScrollArea>
                            </TabsContent>
                        </Tabs>
                    )}
                </div>
            </div>
        </div>
    );
}
