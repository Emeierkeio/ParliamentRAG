"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Minus, Info, RotateCcw } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface CompassData {
    meta: {
        query: string;
        explained_variance_ratio: number[];
        dimensionality?: number;
        is_stable: boolean;
        warnings?: string[];
    };
    axes: {
        x: AxisDef;
        y: AxisDef;
    };
    groups: Array<{
        group_id: string;
        position_x: number;
        position_y: number;
        dispersion: {
            center_x: number;
            center_y: number;
            radius_x: number;
            radius_y: number;
            rotation: number;
        };
        stats: any;
        core_evidence_ids: string[];
    }>;
    scatter_sample: Array<{
        x: number;
        y: number;
        group_id: string;
        text: string;
    }>;
}

interface AxisDef {
    index: number; 
    positive_pole_fragments: string[]; 
    negative_pole_fragments: string[];
    label?: string;
    description?: string;
    positive_side?: { 
        label: string; 
        explanation: string;
        keywords?: string[];
        fragments?: Array<{ text_preview: string }>;
    };
    negative_side?: { 
        label: string; 
        explanation: string;
        keywords?: string[];
        fragments?: Array<{ text_preview: string }>;
    };
}

interface CompassCardProps {
    data: CompassData;
}

export function CompassCard({ data }: CompassCardProps) {
  const [zoom, setZoom] = useState(1);
  // Pan offset in percentage points (0,0 = centered)
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ dragging: boolean; startX: number; startY: number; startPanX: number; startPanY: number } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  if (!data?.meta || !data?.groups) return null;
  const dimensionality = data.meta.dimensionality ?? 2;

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  // Drag handlers
  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    const el = containerRef.current;
    if (!el) return;
    el.setPointerCapture(e.pointerId);
    dragRef.current = { dragging: true, startX: e.clientX, startY: e.clientY, startPanX: pan.x, startPanY: pan.y };
  }, [pan]);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const d = dragRef.current;
    if (!d?.dragging) return;
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    // Convert pixel delta to percentage of container
    const dx = ((e.clientX - d.startX) / rect.width) * 100;
    const dy = ((e.clientY - d.startY) / rect.height) * 100;
    setPan({ x: d.startPanX + dx, y: d.startPanY + dy });
  }, []);

  const onPointerUp = useCallback(() => {
    if (dragRef.current) dragRef.current.dragging = false;
  }, []);

  // Wheel zoom – registered with { passive: false } to allow preventDefault
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      setZoom(z => {
        const delta = e.deltaY > 0 ? -0.15 : 0.15;
        return Math.min(6, Math.max(0.2, z + delta));
      });
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, []);

  // Group colors and abbreviations map
  const groupConfig: Record<string, { color: string; abbrev: string }> = {
      "FRATELLI D'ITALIA": { color: "#0066CC", abbrev: "FdI" },
      "PARTITO DEMOCRATICO": { color: "#E30613", abbrev: "PD" },
      "LEGA": { color: "#008C45", abbrev: "Lega" },
      "MOVIMENTO 5 STELLE": { color: "#FFCC00", abbrev: "M5S" },
      "FORZA ITALIA": { color: "#00AEEF", abbrev: "FI" },
      "AZIONE": { color: "#F5821F", abbrev: "Az" },
      "ITALIA VIVA": { color: "#EB008B", abbrev: "IV" },
      "ALLEANZA VERDI": { color: "#4CAF50", abbrev: "AVS" },
      "NOI MODERATI": { color: "#1E3A5F", abbrev: "NM" },
      "MISTO": { color: "#808080", abbrev: "Misto" },
      "GOVERNO": { color: "#4B0082", abbrev: "Gov" }
  };

  const getGroupColor = (groupId: string) => {
       const upperGroupId = groupId.toUpperCase();
       for (const [key, config] of Object.entries(groupConfig)) {
           if (upperGroupId.includes(key.toUpperCase())) return config.color;
       }
       return "#808080";
  };

  const getGroupAbbrev = (groupId: string) => {
       const upperGroupId = groupId.toUpperCase();
       for (const [key, config] of Object.entries(groupConfig)) {
           if (upperGroupId.includes(key.toUpperCase())) return config.abbrev;
       }
       // Fallback: first 3 letters
       return groupId.substring(0, 3);
  }

  // Scaling with pan offset
  const scale = (val: number, axis: 'x' | 'y') => {
      const unitPercent = 10 * zoom;
      const offset = val * unitPercent;
      return 50 + offset + (axis === 'x' ? pan.x : pan.y);
  };


  const getAxisLabel = (axis: AxisDef, side: 'pos' | 'neg') => {
      if (side === 'pos' && axis.positive_side?.label) return axis.positive_side.label;
      if (side === 'neg' && axis.negative_side?.label) return axis.negative_side.label;
      return side === 'pos' ? "Dimensione (+)" : "Dimensione (-)";
  };

  const AxisLabel = ({ axis, side, className, ...props }: { axis: AxisDef, side: 'pos'|'neg', className?: string, style?: any }) => (
      <div className={cn("absolute max-w-[40%] text-center text-xs font-medium text-slate-600 dark:text-slate-300 bg-white/90 dark:bg-black/90 px-2 py-1 rounded border shadow-sm z-10 truncate", className)} title={getAxisLabel(axis, side)} {...props}>
           {getAxisLabel(axis, side)}
      </div>
  );

  return (
    <div className="w-full">
         {/* Header con titolo onesto e tooltip esplicativo */}
         <div className="flex items-center gap-2 mb-2">
         </div>
         <div className="text-xs text-muted-foreground mb-2">
            {data.meta.query ? `Analisi basata su: "${data.meta.query}"` : "Posizionamento politico dinamico."}
            {dimensionality === 1 && <Badge variant="secondary" className="ml-2 text-[10px]">1D Spectrum</Badge>}
         </div>
         
         {/* Warnings e Flags dal backend */}
         {data.meta.warnings && data.meta.warnings.length > 0 && (
            <div className="mb-3 space-y-1">
               {data.meta.warnings.map((warning, idx) => (
                  <Badge key={idx} variant="outline" className="mr-1 text-[10px] border-orange-500 text-orange-700 dark:text-orange-400">
                     {warning.includes('WEAK_ALIGNMENT') ? '⚠️ Asse secondario: rumore (usare 1D)' : `⚠️ ${warning}`}
                  </Badge>
               ))}
            </div>
         )}
         
         <div
             ref={containerRef}
             onPointerDown={onPointerDown}
             onPointerMove={onPointerMove}
             onPointerUp={onPointerUp}
             onPointerCancel={onPointerUp}

             className={cn(
                 "relative w-full bg-slate-50 dark:bg-slate-900 rounded border overflow-hidden shadow-inner mx-auto select-none touch-none",
                 dimensionality === 1 ? "h-[200px]" : "aspect-square",
                 "cursor-grab active:cursor-grabbing"
             )}
         >
              
              {dimensionality === 2 ? (
                <>
                  {/* 2D Grid Lines */}
                  <div className="absolute top-1/2 left-0 w-full h-[1px] bg-slate-200 dark:bg-slate-700 pointer-events-none" />
                  <div className="absolute top-0 left-1/2 w-[1px] h-full bg-slate-200 dark:bg-slate-700 pointer-events-none" />
                  
                  {/* 2D Labels */}
                  <AxisLabel axis={data.axes.y} side="pos" className="top-4 left-1/2 -translate-x-1/2" />
                  <AxisLabel axis={data.axes.y} side="neg" className="bottom-4 left-1/2 -translate-x-1/2" />
                  <AxisLabel axis={data.axes.x} side="pos" className="right-4 top-1/2 -translate-y-1/2" />
                  <AxisLabel axis={data.axes.x} side="neg" className="left-4 top-1/2 -translate-y-1/2" />
                </>
              ) : (
                <>
                   {/* 1D Grid Line */}
                   <div className="absolute top-1/2 left-0 w-full h-[1px] bg-slate-200 dark:bg-slate-700 pointer-events-none" />
                   
                   {/* 1D Labels */}
                   <AxisLabel axis={data.axes.x} side="pos" className="right-4 top-[10%]" />
                   <AxisLabel axis={data.axes.x} side="neg" className="left-4 top-[10%]" />
                </>
              )}

              {/* Scatter Points */}
              {data.scatter_sample.map((pt, i) => (
                  <div
                    key={i}
                    className="absolute w-1.5 h-1.5 rounded-full opacity-20 transition-opacity hover:opacity-60"
                    style={{
                        left: `${scale(pt.x, 'x')}%`,
                        top: dimensionality === 1 ? '50%' : `${scale(-pt.y, 'y')}%`,
                        backgroundColor: getGroupColor(pt.group_id),
                        transform: 'translate(-50%, -50%)'
                    }}
                  />
              ))}

              {/* Group Centroids with Labels */}
               {data.groups.map((grp) => {
                   const cx = scale(grp.position_x, 'x');
                   const cy = dimensionality === 1 ? 50 : scale(-grp.position_y, 'y');
                   const color = getGroupColor(grp.group_id);
                   const abbrev = getGroupAbbrev(grp.group_id);

                   return (
                   <TooltipProvider key={grp.group_id}>
                       <Tooltip>
                           <TooltipTrigger asChild>
                                <div
                                    className="absolute flex flex-col items-center cursor-pointer hover:scale-110 transition-transform z-20"
                                    style={{
                                        left: `${cx}%`,
                                        top: `${cy}%`,
                                        transform: 'translate(-50%, -50%)'
                                    }}
                                >
                                    {/* Dot */}
                                    <div
                                        className="w-4 h-4 rounded-full border-2 border-white dark:border-slate-800 shadow-md"
                                        style={{ backgroundColor: color }}
                                    />
                                    {/* Label */}
                                    <span
                                        className="text-[10px] font-bold mt-0.5 px-1 rounded bg-white/80 dark:bg-slate-900/80 shadow-sm whitespace-nowrap"
                                        style={{ color: color }}
                                    >
                                        {abbrev}
                                    </span>
                                </div>
                           </TooltipTrigger>
                           <TooltipContent side="top">
                               <p className="font-bold text-sm">{grp.group_id}</p>
                               <div className="text-xs text-muted-foreground">
                                   Posizione: ({grp.position_x.toFixed(2)}, {dimensionality === 1 ? '-' : grp.position_y.toFixed(2)})
                               </div>
                               <div className="text-xs text-muted-foreground">
                                   Frammenti: {grp.stats.n_fragments}
                               </div>
                           </TooltipContent>
                       </Tooltip>
                   </TooltipProvider>
               )})}
          </div>
          
          {/* Legend */}
          <div className="flex flex-wrap gap-2 mt-3 justify-center">
              {data.groups.map((grp) => (
                  <div key={grp.group_id} className="flex items-center gap-1 text-xs">
                      <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getGroupColor(grp.group_id) }}
                      />
                      <span className="text-muted-foreground">{getGroupAbbrev(grp.group_id)}</span>
                  </div>
              ))}
          </div>

          <div className="flex justify-between items-center mt-2 px-2">
             {/* Varianza spiegata con tooltip esplicativo */}
             <div className="flex items-center gap-1 text-xs text-muted-foreground">
                 <span>Varianza spiegata: {Math.round(((data.meta.explained_variance_ratio?.[0] || 0) + (dimensionality === 2 ? (data.meta.explained_variance_ratio?.[1] || 0) : 0)) * 100)}%</span>
                 <TooltipProvider>
                    <Tooltip>
                       <TooltipTrigger asChild>
                          <Info className="h-3 w-3 cursor-help" />
                       </TooltipTrigger>
                       <TooltipContent side="top" className="max-w-xs">
                          <div className="text-xs space-y-1">
                             <p><strong>Significato:</strong></p>
                             <p>• Valore basso (≈15%): discorsi simili/sovrapposti</p>
                             <p>• Valore alto (≈40%+): forte polarizzazione semantica</p>
                             <p>• PC1: {Math.round((data.meta.explained_variance_ratio?.[0] || 0) * 100)}% | PC2: {dimensionality === 2 ? Math.round((data.meta.explained_variance_ratio?.[1] || 0) * 100) : 0}%</p>
                          </div>
                       </TooltipContent>
                    </Tooltip>
                 </TooltipProvider>
             </div>
             <div className="flex gap-1 items-center">
                 <Button variant="outline" size="icon" className="h-6 w-6" onClick={() => setZoom(z => Math.max(0.2, z - 0.2))}>
                     <Minus className="h-3 w-3" />
                 </Button>
                 <span className="text-[10px] text-muted-foreground w-8 text-center">{Math.round(zoom * 100)}%</span>
                 <Button variant="outline" size="icon" className="h-6 w-6" onClick={() => setZoom(z => Math.min(6, z + 0.2))}>
                     <Plus className="h-3 w-3" />
                 </Button>
                 <Button variant="outline" size="icon" className="h-6 w-6 ml-1" onClick={resetView} title="Reset vista">
                     <RotateCcw className="h-3 w-3" />
                 </Button>
             </div>
          </div>
    </div>
  );
}
