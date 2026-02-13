"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { config } from "@/config";
import type { TopicStatistics } from "@/types";
import {
  MessageSquareQuote,
  Users,
  Calendar,
  Hash,
} from "lucide-react";

type StatsView = "interventions" | "speakers" | "sessions";

interface TopicStatsModalProps {
  stats: TopicStatistics;
  isOpen: boolean;
  onClose: () => void;
  defaultView?: StatsView;
}

function getGroupColor(party: string): string {
  const entry = config.politicalGroups[party as keyof typeof config.politicalGroups];
  return entry?.color || "#9E9E9E";
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("it-IT", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function TopicStatsModal({
  stats,
  isOpen,
  onClose,
  defaultView = "interventions",
}: TopicStatsModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[95vw] sm:max-w-2xl bg-background border-none shadow-2xl p-0 overflow-hidden rounded-xl sm:rounded-2xl h-[85vh] sm:h-[80vh] flex flex-col">
        <DialogHeader className="px-6 py-4 border-b border-border/40 shrink-0 bg-card/50 backdrop-blur-sm">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Hash className="h-5 w-5 text-primary" />
            <span>Dettaglio Statistiche</span>
          </DialogTitle>
        </DialogHeader>

        <Tabs defaultValue={defaultView} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-3 h-10 px-6 mt-2 shrink-0">
            <TabsTrigger value="interventions" className="text-xs gap-1.5">
              <MessageSquareQuote className="h-3.5 w-3.5" />
              Interventi
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 ml-1">
                {stats.intervention_count}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="speakers" className="text-xs gap-1.5">
              <Users className="h-3.5 w-3.5" />
              Parlamentari
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 ml-1">
                {stats.speaker_count}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="sessions" className="text-xs gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              Sedute
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 ml-1">
                {stats.sessions_detail.length}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 overflow-hidden">
            <TabsContent value="interventions" className="h-full mt-0 data-[state=active]:flex data-[state=active]:flex-col">
              <ScrollArea className="flex-1">
                <div className="px-6 py-4 space-y-2">
                  {stats.interventions_detail.map((intervention, i) => (
                    <div
                      key={`${intervention.speech_id}-${i}`}
                      className="flex items-start gap-3 p-3 rounded-lg border border-border/50 bg-card/50 hover:bg-muted/30 transition-colors"
                    >
                      <div
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                        style={{
                          backgroundColor: `${getGroupColor(intervention.party)}10`,
                          color: getGroupColor(intervention.party),
                          border: `1px solid ${getGroupColor(intervention.party)}30`,
                        }}
                      >
                        {intervention.speaker_name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-semibold text-foreground truncate">
                            {intervention.speaker_name}
                          </span>
                          <Badge
                            variant="outline"
                            className="shrink-0 text-[9px] px-1.5 py-0 h-4"
                            style={{
                              borderColor: `${getGroupColor(intervention.party)}40`,
                              color: getGroupColor(intervention.party),
                            }}
                          >
                            {intervention.coalition === "maggioranza" ? "magg." : "opp."}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-muted-foreground truncate" title={intervention.party}>
                          {intervention.party}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-[10px] text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-2.5 w-2.5" />
                            {formatDate(intervention.date)}
                          </span>
                          {intervention.session_number > 0 && (
                            <span className="flex items-center gap-1">
                              <Hash className="h-2.5 w-2.5" />
                              Seduta {intervention.session_number}
                            </span>
                          )}
                        </div>
                        {intervention.debate_title && (
                          <p className="text-[10px] text-muted-foreground/70 mt-1 truncate" title={intervention.debate_title}>
                            {intervention.debate_title}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  {stats.interventions_detail.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      Nessun intervento disponibile.
                    </p>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="speakers" className="h-full mt-0 data-[state=active]:flex data-[state=active]:flex-col">
              <ScrollArea className="flex-1">
                <div className="px-6 py-4 space-y-2">
                  {stats.speakers_detail.map((speaker, i) => (
                    <div
                      key={`${speaker.speaker_id}-${i}`}
                      className="flex items-center gap-3 p-3 rounded-lg border border-border/50 bg-card/50 hover:bg-muted/30 transition-colors"
                    >
                      <div
                        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold"
                        style={{
                          backgroundColor: `${getGroupColor(speaker.party)}10`,
                          color: getGroupColor(speaker.party),
                          border: `1px solid ${getGroupColor(speaker.party)}30`,
                        }}
                      >
                        {speaker.speaker_name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-semibold text-foreground truncate">
                            {speaker.speaker_name}
                          </span>
                          <Badge
                            variant="outline"
                            className="shrink-0 text-[9px] px-1.5 py-0 h-4"
                            style={{
                              borderColor: `${getGroupColor(speaker.party)}40`,
                              color: getGroupColor(speaker.party),
                            }}
                          >
                            {speaker.coalition === "maggioranza" ? "magg." : "opp."}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-muted-foreground truncate" title={speaker.party}>
                          {speaker.party}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Badge variant="secondary" className="text-xs px-2 py-0.5">
                          {speaker.intervention_count} {speaker.intervention_count === 1 ? "intervento" : "interventi"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                  {stats.speakers_detail.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      Nessun parlamentare disponibile.
                    </p>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="sessions" className="h-full mt-0 data-[state=active]:flex data-[state=active]:flex-col">
              <ScrollArea className="flex-1">
                <div className="px-6 py-4 space-y-2">
                  {stats.sessions_detail.map((session, i) => (
                    <div
                      key={`${session.session_number}-${i}`}
                      className="flex items-center gap-3 p-3 rounded-lg border border-border/50 bg-card/50 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-sm">
                        {session.session_number}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-semibold text-foreground">
                            Seduta N. {session.session_number}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-2.5 w-2.5" />
                            {formatDate(session.date)}
                          </span>
                        </div>
                        {session.debate_title && (
                          <p className="text-[10px] text-muted-foreground/70 mt-1 truncate" title={session.debate_title}>
                            {session.debate_title}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  {stats.sessions_detail.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      Nessuna seduta disponibile.
                    </p>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
