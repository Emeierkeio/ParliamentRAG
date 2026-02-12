"use client";

import { useState } from "react";
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
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { config } from "@/config";
import type { Expert } from "@/types";
import {
  User,
  Award,
  TrendingUp,
  MessageSquare,
  Network,
  Target,
  Layers,
  ChevronRight,
  FileText,
  ExternalLink
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ExpertCardProps {
  expert: Expert;
  className?: string;
}

export function ExpertCard({ expert, className }: ExpertCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const groupConfig = config.politicalGroups[expert.group as keyof typeof config.politicalGroups];
  const groupColor = groupConfig?.color || "#6B7280";
  const groupLabel = groupConfig?.label || expert.group;

  const scoreLevel =
    expert.authority_score >= config.authorityScore.high
      ? "high"
      : expert.authority_score >= config.authorityScore.medium
      ? "medium"
      : "low";

  const scoreLevelConfig = {
    high: { label: "Alto", color: "text-green-600" },
    medium: { label: "Medio", color: "text-amber-600" },
    low: { label: "Basso", color: "text-gray-500" },
  };

  return (
    <>
      <Card
        className={cn(
          "cursor-pointer border-transparent bg-card shadow-sm transition-all duration-300 w-full",
          "hover:shadow-md hover:scale-[1.02] hover:bg-card/80",
          className
        )}
        onClick={() => setIsModalOpen(true)}
      >
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            {/* Avatar */}
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm"
              style={{ backgroundColor: groupColor }}
            >
              {expert.first_name[0]}
              {expert.last_name[0]}
            </div>

            <div className="flex-1 min-w-0">
              {/* Name */}
              {/* Name */}
              {expert.camera_profile_url ? (
                  <a 
                    href={expert.camera_profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-semibold text-foreground leading-tight hover:underline hover:text-primary transition-colors block"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {expert.first_name} {expert.last_name}
                  </a>
              ) : (
                  <p className="text-sm font-semibold text-foreground leading-tight">
                    {expert.first_name} {expert.last_name}
                  </p>
              )}

              {/* Group badge */}
              <p
                className="text-xs font-medium mt-0.5 leading-tight"
                style={{ color: groupColor }}
              >
                {groupLabel}
              </p>

              {/* Coalizione indicator */}
              <p className="text-xs text-muted-foreground mt-1">
                {expert.coalition === "maggioranza" ? "Maggioranza" : "Opposizione"}
              </p>

              {/* Authority score preview */}
              <div className="flex items-center gap-2 mt-2">
                <Award className={cn("h-3.5 w-3.5 shrink-0", scoreLevelConfig[scoreLevel].color)} />
                <div className="flex-1 h-1.5 rounded-full bg-gray-200">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      scoreLevel === "high" && "bg-green-500",
                      scoreLevel === "medium" && "bg-amber-500",
                      scoreLevel === "low" && "bg-gray-400"
                    )}
                    style={{ width: `${expert.authority_score * 100}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-muted-foreground min-w-[24px] text-right">
                  {(expert.authority_score * 100).toFixed(0)}
                </span>
              </div>
            </div>

            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/60 mt-1" />
          </div>
        </CardContent>
      </Card>

      {/* Expert detail modal */}
      <ExpertModal
        expert={expert}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
}

export function ExpertRow({ expert, className }: ExpertCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const groupConfig = config.politicalGroups[expert.group as keyof typeof config.politicalGroups];
  const groupColor = groupConfig?.color || "#6B7280";

  return (
    <>
      <div 
        className={cn(
            "flex items-center gap-3 p-2.5 rounded-lg border border-transparent bg-muted/20 hover:bg-muted/40 hover:border-border/40 transition-all cursor-pointer group w-full",
            className
        )}
        onClick={() => setIsModalOpen(true)}
      >
        {/* Avatar */}
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white shadow-sm"
          style={{ backgroundColor: groupColor }}
        >
          {expert.first_name[0]}{expert.last_name[0]}
        </div>

        <div className="flex-1 min-w-0 flex items-center justify-between gap-4">
             <div className="min-w-0 flex flex-col justify-center">
                  <div className="font-semibold text-sm truncate leading-tight flex items-center gap-2">
                       {expert.camera_profile_url ? (
                           <a 
                             href={expert.camera_profile_url} 
                             target="_blank"
                             rel="noopener noreferrer"
                             className="hover:underline hover:text-primary relative z-10" 
                             onClick={(e) => e.stopPropagation()}
                           >
                              {expert.first_name} {expert.last_name}
                           </a>
                       ) : (
                          <span>{expert.first_name} {expert.last_name}</span>
                       )}
                  </div>
                  {expert.institutional_role && (
                      <span className="text-[10px] text-muted-foreground truncate max-w-[200px] block">
                          {expert.institutional_role}
                      </span>
                  )}
             </div>
             
             {/* Score */}
             <div className="flex items-center gap-3 shrink-0">
                   <div className="hidden sm:block w-20 h-1.5 rounded-full bg-muted-foreground/10 overflow-hidden">
                        <div 
                            className="h-full bg-primary"
                            style={{ width: `${expert.authority_score * 100}%` }}
                        />
                   </div>
                   <div className="flex flex-col items-end leading-none">
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Score</span>
                        <span className="text-sm font-bold">{(expert.authority_score * 100).toFixed(0)}</span>
                   </div>
             </div>
        </div>
        
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors" />
      </div>

      <ExpertModal expert={expert} isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
}

interface ExpertModalProps {
  expert: Expert;
  isOpen: boolean;
  onClose: () => void;
}

function ExpertModal({ expert, isOpen, onClose }: ExpertModalProps) {
  const groupConfig = config.politicalGroups[expert.group as keyof typeof config.politicalGroups];
  const groupColor = groupConfig?.color || "#6B7280";
  const groupLabel = groupConfig?.label || expert.group;

  const scoreBreakdown = [
    {
      icon: MessageSquare,
      label: "Interventi",
      value: expert.score_breakdown?.speeches || 0,
      description: "Volume e pertinenza",
    },
    {
      icon: Target,
      label: "Atti",
      value: expert.score_breakdown?.acts || 0,
      description: "Atti presentati",
    },
    {
      icon: Network,
      label: "Commissione",
      value: expert.score_breakdown?.committee || 0,
      description: "Pertinenza commissione",
      tooltip: expert.committee || "Non assegnata"
    },
    {
      icon: User,
      label: "Professione",
      value: expert.score_breakdown?.profession || 0,
      description: "Background",
      tooltip: expert.profession || "Non rilevata"
    },
    {
      icon: Layers,
      label: "Istruzione",
      value: expert.score_breakdown?.education || 0,
      description: "Titoli di studio",
      tooltip: expert.education || "Non rilevata"
    },
    {
      icon: Award,
      label: "Ruolo",
      value: expert.score_breakdown?.role || 0,
      description: "Incarichi",
      tooltip: expert.institutional_role || "Deputato"
    },
  ];

  const [selectedDetail, setSelectedDetail] = useState<"atti" | null>(null);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] sm:max-w-2xl bg-card border-none shadow-2xl p-0 overflow-hidden rounded-xl sm:rounded-2xl max-h-[90vh] sm:max-h-[85vh] flex flex-col">
        <DialogHeader className="p-4 sm:p-6 pb-2 shrink-0">
          <DialogTitle className="flex items-center gap-3 text-lg sm:text-xl">
             <div className="p-2 bg-primary/10 rounded-lg">
                <TrendingUp className="h-5 w-5 text-primary" />
             </div>
            Scheda Autorità
          </DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">
            Analisi del profilo e dell'autorevolezza sul tema specifico.
          </DialogDescription>
        </DialogHeader>

        <div className="p-4 sm:p-6 pt-2 space-y-4 sm:space-y-6 overflow-y-auto">
          {/* Header Profile */}
          <div className="flex items-start gap-3 sm:gap-5">
            <div
              className="flex h-12 w-12 sm:h-16 sm:w-16 shrink-0 items-center justify-center rounded-xl sm:rounded-2xl text-lg sm:text-xl font-bold text-white shadow-lg"
              style={{ backgroundColor: groupColor }}
            >
              {expert.first_name[0]}
              {expert.last_name[0]}
            </div>
            <div className="flex-1 min-w-0 space-y-1">
              {expert.camera_profile_url ? (
                  <a
                    href={expert.camera_profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xl sm:text-2xl font-bold text-foreground hover:underline hover:text-primary transition-colors block truncate"
                  >
                    {expert.first_name} {expert.last_name}
                  </a>
              ) : (
                  <h3 className="text-xl sm:text-2xl font-bold text-foreground truncate">
                    {expert.first_name} {expert.last_name}
                  </h3>
              )}
              <div className="flex flex-wrap items-center gap-2">
                 <Badge
                  className="px-2 py-0.5 text-xs font-semibold uppercase tracking-wider bg-transparent border shadow-none hover:bg-transparent"
                  style={{
                    color: groupColor,
                    borderColor: groupColor,
                  }}
                >
                  {groupLabel}
                </Badge>
                <span className="text-muted-foreground text-sm">•</span>
                <span className="text-sm font-medium text-muted-foreground">
                    {expert.coalition === "maggioranza" ? "Maggioranza" : "Opposizione"}
                </span>
              </div>
            </div>
          </div>

          {/* Main Score */}
          <div className="bg-muted/30 rounded-xl p-4 sm:p-5 border border-border/50">
             <div className="flex justify-between items-end mb-3">
                <span className="text-xs sm:text-sm font-medium text-muted-foreground uppercase tracking-widest">Authority Score</span>
                <span className="text-2xl sm:text-3xl font-bold text-primary">{(expert.authority_score * 100).toFixed(0)}</span>
             </div>
             <div className="h-3 w-full rounded-full bg-muted overflow-hidden">
                <div 
                    className="h-full bg-primary rounded-full transition-all duration-1000 ease-out" 
                    style={{ width: `${expert.authority_score * 100}%` }}
                />
             </div>
          </div>

          <Separator className="bg-border/40" />

          {/* Grid Breakdown */}
          <div>
            <h4 className="text-sm font-medium text-foreground mb-4">Dettagli Punteggio</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {scoreBreakdown.map((item) => {
                    const isAtti = item.label === "Atti";
                    const hasDetails = isAtti && expert.acts_detail && expert.acts_detail.length > 0;

                    const content = (
                         <div 
                            className={cn(
                                "p-3 rounded-xl bg-muted/20 border border-border/30 transition-all h-full",
                                hasDetails ? "hover:bg-muted/40 cursor-pointer ring-offset-background hover:ring-2 hover:ring-primary/20" : "hover:bg-muted/40"
                            )}
                            onClick={() => hasDetails && setSelectedDetail("atti")}
                         >
                            <div className="flex items-center gap-2 mb-2">
                                 <item.icon className={cn("w-4 h-4", hasDetails ? "text-primary" : "text-primary/70")} />
                                 <span className="text-sm font-medium text-foreground">{item.label}</span>
                                 {hasDetails && <ChevronRight className="w-3 h-3 ml-auto text-muted-foreground" />}
                            </div>
                            <div className="flex items-end justify-between gap-2 mb-1">
                                <span className="text-xs text-muted-foreground">{item.description}</span>
                                <span className="text-sm font-bold">{(item.value * 100).toFixed(0)}%</span>
                            </div>
                             <div className="h-1.5 w-full rounded-full bg-muted">
                                <div
                                    className="h-full rounded-full bg-primary/60"
                                    style={{ width: `${item.value * 100}%` }}
                                />
                            </div>
                        </div>
                    );

                    if (item.tooltip) {
                        return (
                             <TooltipProvider key={item.label}>
                                <Tooltip delayDuration={300}>
                                    <TooltipTrigger asChild>
                                        <div className="cursor-help h-full">
                                            {content}
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" className="max-w-[250px]">
                                        <p className="font-medium text-xs">{item.tooltip}</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        );
                    }
                    
                    return <div key={item.label} className="h-full">{content}</div>;
                })}
            </div>
          </div>

          {/* Details Panel (Conditional) */}
          {selectedDetail === "atti" && expert.acts_detail && (
              <div className="space-y-3 sm:space-y-4 animate-in fade-in slide-in-from-top-4 duration-300">
                  <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                          <FileText className="w-4 h-4 text-primary shrink-0" />
                          <h4 className="text-xs sm:text-sm font-semibold truncate">Atti che hanno contribuito allo score</h4>
                      </div>
                      <button 
                        onClick={() => setSelectedDetail(null)}
                        className="text-xs text-primary hover:underline font-medium"
                      >
                          Chiudi dettagli
                      </button>
                  </div>
                  <ScrollArea className="h-64 rounded-xl border border-border/40 bg-muted/5 p-3">
                      <div className="space-y-3">
                          {expert.acts_detail.map((atto, idx) => (
                              <div key={idx} className="p-3 bg-card rounded-lg border border-border/30 shadow-sm space-y-2">
                                  <div className="flex items-start justify-between gap-3">
                                      <p className="text-xs font-semibold leading-tight line-clamp-3 flex-1 italic text-foreground/90">
                                          "{atto.title || 'Senza titolo'}"
                                      </p>
                                      <Badge variant="outline" className="shrink-0 text-[10px] px-1.5 py-0 h-4 border-primary/20 text-primary">
                                          {Math.round(atto.similarity * 100)}% Match
                                      </Badge>
                                  </div>
                                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                                      <div className="flex items-center gap-1.5">
                                          <Badge className={cn(
                                              "text-[9px] px-1 py-0 h-4 font-normal",
                                              atto.is_primary ? "bg-amber-100 text-amber-700 hover:bg-amber-100 border-amber-200" : "bg-gray-100 text-gray-600 hover:bg-gray-100 border-gray-200"
                                          )}>
                                              {atto.is_primary ? "1° Firmatario" : "Co-firmatario"}
                                          </Badge>
                                          {atto.eurovoc && (
                                              <span className="truncate max-w-[150px]">Tema: {atto.eurovoc}</span>
                                          )}
                                      </div>
                                  </div>
                              </div>
                          ))}
                      </div>
                  </ScrollArea>
              </div>
          )}

        </div>
      </DialogContent>
    </Dialog>
  );
}
