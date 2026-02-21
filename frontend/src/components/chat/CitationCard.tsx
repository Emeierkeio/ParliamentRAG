"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { config } from "@/config";
import type { Citation } from "@/types";
import { Quote, Calendar, MapPin, User, ExternalLink, Link as LinkIcon } from "lucide-react";

function getCameraUrl(id: string | undefined): string | null {
  if (!id) return null;
  // Match legXX_sedY_... where Y is the seduta number
  // Example: leg19_sed2_tit00040
  // Example: leg19_sed3_tit00080.int00060
  const match = id.match(/leg\d+_sed(\d+)_(.+)/);
  if (!match) return null;
  
  const [_, sedutaStr, rest] = match;
  const sedutaId = sedutaStr.padStart(4, '0');
  
  return `https://www.camera.it/leg19/410?idSeduta=${sedutaId}&tipo=stenografico#sed${sedutaId}.stenografico.${rest}`;
}

interface CitationCardProps {
  citation: Citation;
  index: number;
  className?: string;
  isHighlighted?: boolean;
}

export function CitationCard({ citation, index, className, isHighlighted }: CitationCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const isGoverno = citation.group?.toLowerCase() === "governo" || !!citation.institutional_role;
  const coalitionLabel = isGoverno ? "Governo" : citation.coalition;
  const groupColor = isGoverno ? "#4B0082" : citation.coalition === "maggioranza" ? "#3B82F6" : "#EF4444";

  // Auto-scroll when highlighted
  useEffect(() => {
    if (isHighlighted && cardRef.current) {
        cardRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [isHighlighted]);

  return (
    <>
      <Card
        ref={cardRef}
        className={cn(
          "cursor-pointer border-transparent bg-card shadow-sm transition-all duration-300 w-full max-w-full",
          "hover:border-primary/30 hover:shadow-md",
          isHighlighted && "border-yellow-400/50 bg-yellow-400/5 shadow-[0_0_15px_rgba(250,204,21,0.15)] ring-1 ring-yellow-400/30",
          className
        )}
        onClick={() => setIsModalOpen(true)}
      >
        <CardContent className="p-4">
          <div className="flex items-start gap-4 max-w-full">
             {/* Icon instead of Index */}
            <div className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors",
                isHighlighted && "bg-yellow-400/20 text-yellow-700"
            )}>
              <Quote className="h-4 w-4" />
            </div>

            <div className="flex-1 min-w-0">
              {/* Header */}
              <div className="flex flex-col gap-1 mb-1.5 min-w-0">
                <div className="flex items-center gap-2 min-w-0">
                  {citation.camera_profile_url ? (
                      <a 
                          href={citation.camera_profile_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-semibold text-foreground truncate flex-1 min-w-0 hover:underline hover:text-primary transition-colors"
                          onClick={(e) => e.stopPropagation()} 
                      >
                          {citation.deputy_first_name} {citation.deputy_last_name}
                      </a>
                  ) : (
                      <span className="text-sm font-semibold text-foreground break-words flex-1 min-w-0 hover:underline hover:text-primary transition-colors">
                          {citation.deputy_first_name} {citation.deputy_last_name}
                      </span>
                  )}
                  <Badge
                    variant="outline"
                    className="shrink-0 text-[10px] px-1.5 py-0 h-5"
                    style={{
                      borderColor: groupColor,
                      color: groupColor,
                    }}
                  >
                    {coalitionLabel}
                  </Badge>
                </div>
                {!isGoverno && (
                  <span className="text-[10px] text-muted-foreground block max-w-full break-words" title={citation.group}>
                    {citation.group}
                  </span>
                )}
              </div>

              {/* Extracted text preview */}
              <p className="text-sm text-muted-foreground line-clamp-2 mb-3 leading-relaxed break-words">
                &ldquo;{citation.text || citation.quote_text || ""}&rdquo;
                {getCameraUrl(citation.intervention_id || citation.intervention_id) && (
                     <a 
                        href={getCameraUrl(citation.intervention_id || citation.intervention_id) || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex align-middle ml-1 text-primary/60 hover:text-primary transition-colors"
                        onClick={(e) => e.stopPropagation()}
                        title="Vai all'intervento originale"
                     >
                        <LinkIcon className="h-3 w-3" />
                     </a>
                )}
              </p>

              {/* Metadata */}
              <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground font-medium max-w-full">
                <span className="flex items-center gap-1.5 shrink-0">
                  <Calendar className="h-3 w-3" />
                  {citation.date}
                </span>
                {citation.debate && (
                  <span className="flex items-center gap-1 min-w-0 flex-wrap max-w-full">
                    <MapPin className="h-3 w-3 shrink-0" />
                    {getCameraUrl(citation.debate_id || citation.debate_id) ? (
                        <a 
                            href={getCameraUrl(citation.debate_id || citation.debate_id) || "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline hover:text-foreground cursor-pointer transition-colors break-words"
                            onClick={(e) => e.stopPropagation()}
                        >
                            {citation.debate}
                        </a>
                    ) : (
                        <span className="break-words max-w-full">{citation.debate}</span>
                    )}
                  </span>
                )}
              </div>
            </div>

            {/* Expand icon */}
            <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground/30 group-hover:text-primary transition-colors" />
          </div>
        </CardContent>
      </Card>

      {/* Full citation modal */}
      <CitationModal
        citation={citation}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
}

interface CitationModalProps {
  citation: Citation;
  isOpen: boolean;
  onClose: () => void;
}

function CitationModal({ citation, isOpen, onClose }: CitationModalProps) {
  const isGoverno = citation.group?.toLowerCase() === "governo" || !!citation.institutional_role;
  const coalitionLabel = isGoverno ? "Governo" : citation.coalition;
  const groupColor = isGoverno ? "#4B0082" : citation.coalition === "maggioranza" ? "#3B82F6" : "#EF4444";
  const displayText = citation.full_text || citation.text || "";

  const contextUrl = getCameraUrl(citation.debate_id || citation.debate_id);
  const interventionUrl = getCameraUrl(citation.intervention_id || citation.intervention_id);

  // Highlighting logic: only highlight if we have a specific quote_text that differs from full_text
  // Don't try to highlight the entire chunk - it doesn't make sense
  const quoteText = citation.quote_text || "";
  const hasSpecificQuote = quoteText && citation.full_text &&
    quoteText.length < citation.full_text.length * 0.8; // Quote should be notably shorter than full text

  let parts: string[] = [displayText];
  let highlightText = quoteText;

  if (hasSpecificQuote && citation.full_text) {
    // Try to find and highlight the specific quote within the full text
    if (citation.full_text.includes(quoteText)) {
      parts = citation.full_text.split(quoteText);
    } else {
      // Try normalized matching
      const normalize = (s: string) => s.replace(/\s+/g, ' ').trim();
      const normalizedQuote = normalize(quoteText);
      const normalizedFull = normalize(citation.full_text);

      if (normalizedFull.includes(normalizedQuote)) {
        try {
          const escaped = quoteText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          const pattern = escaped.replace(/\s+/g, '\\s+');
          const regex = new RegExp(pattern, 'i');
          parts = citation.full_text.split(regex);
        } catch {
          // Keep parts as [displayText]
        }
      }
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] sm:max-w-3xl bg-background border-none shadow-2xl p-0 overflow-hidden rounded-xl sm:rounded-2xl h-[90vh] sm:h-[85vh] flex flex-col">
        
        {/* Header: Title & Close */}
        <DialogHeader className="px-6 py-4 border-b border-border/40 shrink-0 bg-card/50 backdrop-blur-sm">
          <DialogTitle className="flex items-center gap-2 text-lg">
             <Quote className="h-5 w-5 text-primary fill-primary/10" />
             <span>Intervento</span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col relative">
             {/* Sticky Speaker Metadata Bar */}
             <div className="bg-card z-10 px-6 py-4 flex items-center gap-4 border-b border-border/40 shrink-0 shadow-sm">
                 <div className="flex items-center gap-4 min-w-0 flex-1">
                    {citation.photo ? (
                        <img
                            src={citation.photo}
                            alt={`${citation.deputy_first_name} ${citation.deputy_last_name}`}
                            className="h-12 w-12 shrink-0 rounded-full object-cover shadow-sm border border-border"
                            style={{ borderColor: `${groupColor}30` }}
                            onError={(e) => {
                                const target = e.currentTarget;
                                target.style.display = "none";
                                const next = target.nextElementSibling as HTMLElement | null;
                                if (next) next.style.display = "flex";
                            }}
                        />
                    ) : null}
                    <div
                        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-background shadow-sm border border-border text-lg font-bold text-muted-foreground/80"
                        style={{ color: groupColor, borderColor: `${groupColor}30`, backgroundColor: `${groupColor}05`, display: citation.photo ? "none" : "flex" }}
                    >
                        {citation.deputy_first_name?.[0]}{citation.deputy_last_name?.[0]}
                    </div>
                    <div className="flex flex-col min-w-0">
                        {citation.camera_profile_url ? (
                            <a 
                                href={citation.camera_profile_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-bold text-foreground text-lg leading-tight truncate hover:underline hover:text-primary transition-colors"
                            >
                                {citation.deputy_first_name} {citation.deputy_last_name}
                            </a>
                        ) : (
                            <div className="font-bold text-foreground text-lg leading-tight truncate">
                                {citation.deputy_first_name} {citation.deputy_last_name}
                            </div>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                             <Badge
                                variant="outline"
                                className="h-5 text-[10px] px-1.5 font-medium capitalize"
                                style={{ borderColor: `${groupColor}40`, color: groupColor }}
                             >
                                {coalitionLabel}
                             </Badge>
                             {!isGoverno && (
                               <span className="text-xs text-muted-foreground truncate max-w-[300px]" title={citation.group}>
                                  {citation.group}
                               </span>
                             )}
                        </div>
                    </div>
                </div>
                
                {/* Date & Meta */}
                <div className="flex flex-col items-end text-xs text-muted-foreground gap-1 shrink-0">
                    <div className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded-md">
                        <Calendar className="w-3 h-3" /> 
                        <span className="font-medium">{citation.date}</span>
                    </div>
                </div>
             </div>

             {/* Content Area */}
             <ScrollArea className="flex-1">
                <div className="p-6 md:p-8 space-y-8">
                    {/* Context Box */}
                    {citation.debate && (
                        <div className="bg-muted/30 rounded-xl p-4 border border-border/50 text-sm leading-relaxed text-muted-foreground">
                            <div className="flex items-center gap-2 mb-2 text-primary font-medium text-xs uppercase tracking-wider">
                                <MapPin className="w-3 h-3" />
                                Contesto Parlamentare
                            </div>
                            {contextUrl ? (
                                <a 
                                    href={contextUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="hover:text-primary hover:underline transition-colors flex items-center gap-1 group/link"
                                >
                                    {citation.debate}
                                    <ExternalLink className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity" />
                                </a>
                            ) : (
                                citation.debate
                            )}
                        </div>
                    )}

                    {/* Speech Text */}
                    <div className="prose prose-lg max-w-none dark:prose-invert font-serif tracking-wide leading-loose text-foreground/90">
                        {parts.length > 1 ? (
                            <>
                                {parts.map((part, i) => (
                                    <span key={i}>
                                        {part}
                                        {i < parts.length - 1 && (
                                            <mark className="bg-yellow-200/50 text-foreground px-1 -mx-1 rounded border-b-2 border-yellow-400 dark:bg-yellow-500/20 dark:text-yellow-100 font-medium">
                                                {highlightText}
                                            </mark>
                                        )}
                                    </span>
                                ))}
                            </>
                        ) : (
                            displayText
                        )}
                        
                        {interventionUrl && (
                            <a 
                                href={interventionUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center justify-center ml-2 text-primary/40 hover:text-primary transition-colors align-middle"
                                title="Vai all'intervento sul sito della Camera"
                            >
                                <LinkIcon className="w-4 h-4" />
                            </a>
                        )}
                    </div>
                </div>
             </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}