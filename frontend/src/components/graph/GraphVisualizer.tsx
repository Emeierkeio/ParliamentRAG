"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useRef, type MutableRefObject } from "react";
import { useTheme } from "next-themes";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Maximize2, Minimize2, ZoomIn, ZoomOut, RefreshCcw } from "lucide-react";
import type { ForceGraphMethods, NodeObject } from "react-force-graph-2d";

// Dynamically import ForceGraph2D with no SSR as it relies on window/canvas
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

/** Raw record from a Cypher query row value */
type GraphRecord = Record<string, unknown>;

interface GraphNode {
  id: string | number;
  label: string;
  caption: string;
  val: number;
  color: string;
  properties: Record<string, string | number | boolean | null>;
  x?: number;
  y?: number;
}

interface GraphLink {
  id: string | number;
  source: string | number;
  target: string | number;
  type?: string;
}

interface GraphVisualizerProps {
  data: GraphRecord[];
}

export function GraphVisualizer({ data }: GraphVisualizerProps) {
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({
    nodes: [],
    links: [],
  });
  const fgRef = useRef<ForceGraphMethods | undefined>(undefined) as MutableRefObject<ForceGraphMethods | undefined>;
  const { theme } = useTheme();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (!data || !Array.isArray(data) || data.length === 0) {
        setGraphData({ nodes: [], links: [] });
        return;
    }
    
    // Transform Cypher result array into nodes/links
    // We handle:
    // 1. Nodes returned directly (e.g. RETURN n)
    // 2. Relationships returned directly (e.g. RETURN r)
    // 3. Paths (not handled in simple implementation without metadata)
    // 4. Manual parsing of dicts

    const nodes = new Map();
    const links = new Map();

    /** Extract a string property from an unknown record, returning undefined if not a string. */
    const strProp = (obj: Record<string, unknown>, ...keys: string[]): string | undefined => {
        for (const k of keys) {
            const v = obj[k];
            if (typeof v === "string" && v) return v;
        }
        return undefined;
    };

    const processItem = (item: GraphRecord) => {
        if (!item || typeof item !== 'object') return;

        // If it has 'start', 'end', 'type' -> likely a relationship
        if ('start' in item && 'end' in item && 'type' in item) {
             const linkId = item.id ?? `${String(item.start)}-${String(item.type)}-${String(item.end)}`;
             if (!links.has(linkId)) {
                 links.set(linkId, {
                    id: linkId,
                    source: item.start,
                    target: item.end,
                    type: item.type,
                 });
             }
            if (!nodes.has(item.start)) nodes.set(item.start, { id: item.start, label: "Unknown", caption: "?", color: "#888", properties: {} });
            if (!nodes.has(item.end)) nodes.set(item.end, { id: item.end, label: "Unknown", caption: "?", color: "#888", properties: {} });
             return;
        }

        // Neo4j node structure: { id, labels, properties }
        const id = item.id ?? item.elementId;
        if (id !== undefined) {
            if (!nodes.has(id)) {
                // Get label from labels array
                let label = "Node";
                if (Array.isArray(item.labels) && item.labels.length > 0) {
                    label = String(item.labels[0]);
                }

                // Properties are nested in item.properties or the item itself
                const props = (typeof item.properties === 'object' && item.properties !== null
                    ? item.properties
                    : item) as Record<string, unknown>;

                // Build caption based on node label type
                let caption = "";
                const firstName = strProp(props, "first_name", "nome");
                const lastName = strProp(props, "last_name", "cognome");
                const title = strProp(props, "title", "titolo");
                const name = strProp(props, "name");
                const text = strProp(props, "text", "testo");
                const number = strProp(props, "number", "numero");
                const date = strProp(props, "date", "data");

                // Label-specific caption logic
                switch (label) {
                    case "Deputy":
                    case "Deputato":
                    case "GovernmentMember":
                    case "MembroGoverno":
                        caption = firstName && lastName ? `${firstName} ${lastName}` : firstName ?? lastName ?? "?";
                        break;
                    case "Session":
                    case "Seduta":
                        caption = number ? `Seduta ${number}` : (date ? `${date}` : "Session");
                        break;
                    case "Debate":
                    case "Dibattito":
                        caption = title ? (title.length > 30 ? title.substring(0, 30) + "..." : title) : "Debate";
                        break;
                    case "Phase":
                    case "Fase":
                        caption = title ? (title.length > 25 ? title.substring(0, 25) + "..." : title) : "Phase";
                        break;
                    case "Speech":
                    case "Intervento":
                        caption = text ? (text.length > 25 ? text.substring(0, 25) + "..." : text) : "Speech";
                        break;
                    case "Chunk":
                        caption = text ? (text.length > 20 ? text.substring(0, 20) + "..." : text) : "Chunk";
                        break;
                    case "ParliamentaryGroup":
                    case "GruppoParlamentare":
                        caption = name ?? strProp(props, "acronym", "sigla") ?? "Group";
                        break;
                    case "Committee":
                    case "Commissione":
                        caption = name ? (name.length > 25 ? name.substring(0, 25) + "..." : name) : "Committee";
                        break;
                    case "ParliamentaryAct":
                    case "AttoParlamentare":
                        caption = title ? (title.length > 30 ? title.substring(0, 30) + "..." : title) : "Act";
                        break;
                    default:
                        // Generic fallback
                        if (firstName && lastName) caption = `${firstName} ${lastName}`;
                        else if (name) caption = name;
                        else if (title) caption = title.length > 25 ? title.substring(0, 25) + "..." : title;
                        else caption = String(id).split('/').pop()?.substring(0, 12) ?? "Node";
                }

                nodes.set(id, {
                    id: id,
                    label: label,
                    caption: caption,
                    val: 1,
                    color: getNodeColor(label),
                    properties: props
                });
            }
        }
    }

    data.forEach(row => {
        Object.values(row).forEach(val => {
             if (Array.isArray(val)) {
                 val.forEach((item: unknown) => {
                     if (item !== null && typeof item === 'object') processItem(item as GraphRecord);
                 });
             } else if (val !== null && typeof val === 'object') {
                 processItem(val as GraphRecord);
             }
        });
    });
    
    setGraphData({
        nodes: Array.from(nodes.values()),
        links: Array.from(links.values())
    });

  }, [data]);

    const getNodeColor = (label: string) => {
        const colors: Record<string, string> = {
            // English labels
            "Deputy": "#3b82f6", // Blue
            "GovernmentMember": "#2563eb", // Darker blue
            "ParliamentaryGroup": "#ef4444", // Red
            "Committee": "#10b981", // Green
            "ParliamentaryAct": "#f59e0b", // Amber
            "Speech": "#8b5cf6", // Purple
            "Session": "#06b6d4", // Cyan
            "Debate": "#ec4899", // Pink
            "Phase": "#f97316", // Orange
            "Chunk": "#6366f1", // Indigo
            // Italian fallbacks
            "Deputato": "#3b82f6",
            "MembroGoverno": "#2563eb",
            "GruppoParlamentare": "#ef4444",
            "Commissione": "#10b981",
            "AttoParlamentare": "#f59e0b",
            "Intervento": "#8b5cf6",
            "Seduta": "#06b6d4",
            "Dibattito": "#ec4899",
            "Fase": "#f97316",
        };
        return colors[label] || "#94a3b8"; // Default slate
    };

    const handleZoomIn = () => {
        fgRef.current?.zoom(fgRef.current.zoom() * 1.2, 400);
    };

    const handleZoomOut = () => {
        fgRef.current?.zoom(fgRef.current.zoom() / 1.2, 400);
    };
    
    const handleFitView = () => {
        fgRef.current?.zoomToFit(400, 20);
    };

    const handleNodeClick = (node: NodeObject) => {
      setSelectedNode(node as GraphNode);
      // Optional: Zoom to node
      // fgRef.current?.centerAt(node.x, node.y, 1000);
      // fgRef.current?.zoom(4, 1000);
    };

    const handleBackgroundClick = () => {
      setSelectedNode(null);
    };

  return (
    <Card className={`relative flex flex-col overflow-hidden ${isFullscreen ? "fixed inset-0 z-50 rounded-none w-screen h-screen" : "w-full h-full"}`}>
        {/* ... Toolbar ... */}
        <div className="absolute top-2 right-2 z-10 flex gap-1 bg-background/50 p-1 rounded-md backdrop-blur-sm border border-border/20">
            {/* ... buttons ... */}
             <Button size="icon" variant="ghost" className="h-8 w-8" onClick={handleFitView} title="Fit View">
                <RefreshCcw className="h-4 w-4" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={handleZoomIn} title="Zoom In">
                <ZoomIn className="h-4 w-4" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={handleZoomOut} title="Zoom Out">
                <ZoomOut className="h-4 w-4" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => setIsFullscreen(!isFullscreen)} title="Fullscreen">
                {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </Button>
        </div>

      <div className="flex-1 w-full h-full bg-slate-950 relative">
          <ForceGraph2D
            ref={fgRef}
            width={isFullscreen ? window.innerWidth : undefined}
            graphData={graphData}
            nodeLabel="caption"
            nodeRelSize={6}
            linkColor={() => "rgba(255,255,255,0.3)"}
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            linkLabel="type"

            // Custom node rendering with label
            nodeCanvasObject={(node: NodeObject, ctx: CanvasRenderingContext2D, globalScale: number) => {
                const gn = node as GraphNode;
                const label = gn.caption || '';
                const fontSize = 12 / globalScale;
                const nodeR = 6;

                // Draw node circle
                ctx.beginPath();
                ctx.arc(node.x ?? 0, node.y ?? 0, nodeR, 0, 2 * Math.PI);
                ctx.fillStyle = gn.color || '#3b82f6';
                ctx.fill();

                // Draw border
                ctx.strokeStyle = 'rgba(255,255,255,0.3)';
                ctx.lineWidth = 1 / globalScale;
                ctx.stroke();

                // Draw label below node
                if (globalScale > 0.5) {
                    ctx.font = `${fontSize}px Sans-Serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';
                    ctx.fillStyle = 'rgba(255,255,255,0.9)';
                    ctx.fillText(label, node.x ?? 0, (node.y ?? 0) + nodeR + 2);
                }
            }}
            nodePointerAreaPaint={(node: NodeObject, color: string, ctx: CanvasRenderingContext2D) => {
                ctx.beginPath();
                ctx.arc(node.x ?? 0, node.y ?? 0, 8, 0, 2 * Math.PI);
                ctx.fillStyle = color;
                ctx.fill();
            }}

            // Interaction
            cooldownTicks={100}
            onNodeClick={handleNodeClick}
            onBackgroundClick={handleBackgroundClick}
          />
          
          {/* Selected Node Details Panel */}
          {selectedNode && (
            <div className={`absolute top-0 left-0 h-full w-[300px] bg-background/95 backdrop-blur-sm border-r border-border p-4 overflow-auto transition-transform duration-300 ${selectedNode ? 'translate-x-0' : '-translate-x-full'}`}>
                <div className="flex justify-between items-start mb-4">
                     <h3 className="font-bold text-lg truncate flex-1" title={selectedNode.caption}>
                        {selectedNode.caption || "Node Details"}
                     </h3>
                     <Button variant="ghost" size="icon" className="h-6 w-6 -mr-2" onClick={() => setSelectedNode(null)}>
                        <Minimize2 className="h-4 w-4 rotate-45" /> {/* Close icon visual hack */}
                     </Button>
                </div>
                
                <div className="space-y-4 text-sm">
                    <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2">
                             <span className="bg-primary/20 text-primary px-2 py-0.5 rounded text-xs font-semibold">
                                {selectedNode.label}
                            </span>
                             <span className="text-xs text-muted-foreground">ID</span>
                        </div>
                        <div className="font-mono text-xs bg-muted/30 p-1.5 rounded break-all border border-border/30">
                            {selectedNode.id}
                        </div>
                    </div>

                    <div className="space-y-2">
                        <h4 className="font-semibold text-xs uppercase text-muted-foreground">Properties</h4>
                        <div className="bg-muted/50 rounded-md p-2 space-y-3">
                            {Object.entries(selectedNode.properties || {}).map(([key, val]) => {
                                if (key === 'labels' || key === 'id' || key === 'elementId' || key === 'properties') return null;
                                const displayVal = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val ?? '');
                                if (!displayVal) return null;
                                return (
                                    <div key={key} className="flex flex-col gap-1 text-xs border-b last:border-0 border-border/50 pb-2 last:pb-0">
                                        <span className="font-medium text-muted-foreground">{key}</span>
                                        <div className="font-mono bg-background p-1.5 rounded border border-border/50 break-all whitespace-pre-wrap max-h-[200px] overflow-auto">
                                            {displayVal}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </div>
          )}
      </div>
      
      {!graphData.nodes.length && (
           <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
               <span className="text-muted-foreground bg-background/80 px-3 py-1 rounded">No graph data to visualize from this query</span>
           </div>
      )}
      
      {graphData.nodes.length > 0 && (
          <div className="absolute bottom-2 left-2 z-10 text-xs text-slate-400 bg-background/80 px-2 py-1 rounded select-none">
              Nodes: {graphData.nodes.length} | Links: {graphData.links.length}
          </div>
      )}
    </Card>
  );
}
