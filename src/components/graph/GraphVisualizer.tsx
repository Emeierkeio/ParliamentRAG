"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useRef } from "react";
import { useTheme } from "next-themes";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Maximize2, Minimize2, ZoomIn, ZoomOut, RefreshCcw } from "lucide-react";

// Dynamically import ForceGraph2D with no SSR as it relies on window/canvas
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

interface GraphVisualizerProps {
  data: any[];
}

export function GraphVisualizer({ data }: GraphVisualizerProps) {
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({
    nodes: [],
    links: [],
  });
  const fgRef = useRef<any>(null);
  const { theme } = useTheme();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);

  useEffect(() => {
    if (!data || data.length === 0) {
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

    const processItem = (item: any) => {
        if (!item) return;

        // Check if it's a Neo4j Node structure (has labels, identity/elementId, properties)
        // Since we get raw JSON from backend (which is list of dicts/values), we need heuristic

        // It is tricky without direct neo4j types.
        // Assuming backend serialization preserves structure:
        // Node: { id: 123, labels: ["..."], properties: {...} } OR simple dict with 'id'
        
        // Let's rely on standard JSON serialization from our backend wrapper.
        // If our backend returns py2neo/neo4j driver dicts, it might just contain props.
        // Let's assume nodes have 'id' or 'element_id'.
        
        // HEURISTIC: treat any object with an 'id' as a potential node if it looks unique.
        
        // HOWEVER, data is likely just an array of dicts like: [{n: {name: "...", label: "..."}}]
        // We need to inspect values.
        
        if (typeof item === 'object') {
            // If it has 'start', 'end', 'type', 'id' -> likely a relationship
            if ('start' in item && 'end' in item && 'type' in item) {
                 const linkId = item.id || `${item.start}-${item.type}-${item.end}`;
                 if (!links.has(linkId)) {
                     links.set(linkId, {
                        id: linkId,
                        source: item.start,
                        target: item.end,
                        type: item.type,
                        ...item
                     });
                 }
                 // Ensure source/target nodes exist placeholders at least
                if (!nodes.has(item.start)) nodes.set(item.start, { id: item.start, label: "Unknown", color: "#888" });
                if (!nodes.has(item.end)) nodes.set(item.end, { id: item.end, label: "Unknown", color: "#888" });
                 return;
            }

            // If it has labels or just props with an id
            // Let's look for known fields that suggest a node
             const id = item.id || item.elementId;
             if (id !== undefined) {
                 // Likely a node
                 if (!nodes.has(id)) {
                     // Try to determine label
                     let label = "Node";
                     if (item.labels && Array.isArray(item.labels) && item.labels.length > 0) {
                         label = item.labels[0];
                     }
                     
                     // Determine name/caption
                     const caption = item.nome || item.cognome || item.name || item.title || item.label || item.id;
                     
                     nodes.set(id, {
                         id: id,
                         label: label,
                         caption: caption,
                         val: 1, // Size
                         color: getNodeColor(label),
                         properties: item
                     });
                 }
             }
        }
    }

    data.forEach(row => {
        Object.values(row).forEach(val => {
             if (Array.isArray(val)) {
                 val.forEach(processItem);
             } else {
                 processItem(val);
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
            "Deputato": "#3b82f6", // Blue
            "Gruppo": "#ef4444", // Red
            "Commissione": "#10b981", // Green
            "Atto": "#f59e0b", // Amber
            "Intervento": "#8b5cf6", // Purple
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

    const handleNodeClick = (node: any) => {
      setSelectedNode(node);
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
            nodeColor="color"
            nodeRelSize={6}
            linkColor={() => "rgba(255,255,255,0.2)"}
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            
            // Interaction
            cooldownTicks={100}
            onNodeClick={handleNodeClick}
            onBackgroundClick={handleBackgroundClick}
            onNodeDragEnd={node => {
                fgRef.current.d3Force('charge').strength(-120);
            }}
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
                                if (key === 'labels' || key === 'id' || key === 'elementId') return null;
                                return (
                                    <div key={key} className="flex flex-col gap-1 text-xs border-b last:border-0 border-border/50 pb-2 last:pb-0">
                                        <span className="font-medium text-muted-foreground">{key}</span>
                                        <div className="font-mono bg-background p-1.5 rounded border border-border/50 break-all whitespace-pre-wrap max-h-[200px] overflow-auto">
                                            {String(val)}
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
