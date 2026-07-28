"use client";

import { useState, useId } from "react";
import React from "react";
import { useTranslations } from "next-intl";
import { ChevronRight, Vote } from "lucide-react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn, cleanDebateTitle } from "@/lib/utils";
import { DebateSheet } from "./DebateSheet";
import { SessionVotesSheet } from "./SessionVotesSheet";
import type { TimelineSession } from "@/types/timeline";

interface SessionCardProps {
  session: TimelineSession;
  searchTerm?: string;
}

function highlightText(text: string, term: string): React.ReactNode {
  if (!term) return text;
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === term.toLowerCase() ? (
      <mark key={i} className="bg-primary/10 text-primary rounded-sm px-0.5">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export function SessionCard({ session, searchTerm }: SessionCardProps) {
  const t = useTranslations("Timeline");
  const [open, setOpen] = useState(false);
  const [proceduralOpen, setProceduralOpen] = useState(false);
  const [votesSheetOpen, setVotesSheetOpen] = useState(false);
  const [selectedDebate, setSelectedDebate] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const contentId = useId();
  const proceduralId = useId();

  const formattedDate = new Date(session.date).toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // Substantive debates open the detail panel; procedural items (no
  // recorded speeches) are folded behind one line so they stop competing
  // with the actual debates for attention.
  const substantive = session.debates.filter((d) => d.speech_count > 0);
  const procedural = session.debates.filter(
    (d) => d.speech_count === 0 && d.title.trim(),
  );

  const stats = [
    { count: session.debate_count, label: t("debateCount", { count: session.debate_count }) },
    { count: session.vote_count, label: t("voteCount", { count: session.vote_count }) },
    { count: session.speech_count, label: t("speechCount", { count: session.speech_count }) },
  ].filter((s) => s.count > 0);

  return (
    <div className="border-b border-border">
      <Collapsible open={open} onOpenChange={setOpen}>
        {/* Header */}
        <CollapsibleTrigger
          className="w-full text-left group"
          aria-expanded={open}
          aria-controls={contentId}
        >
          <div className="py-4">
            <div className="flex items-baseline gap-2.5">
              <span className="[font-family:var(--font-display)] text-lg text-primary/40 tabular-nums leading-none">
                {session.number}
              </span>
              <h3 className="[font-family:var(--font-display)] text-lg font-medium tracking-tight text-foreground leading-none">
                {formattedDate}
              </h3>
              <span
                className={cn(
                  "text-[10px] uppercase tracking-[0.2em] font-medium",
                  session.chamber === "senato" ? "text-chart-5" : "text-primary"
                )}
              >
                {session.chamber}
              </span>
              <ChevronRight
                className={cn(
                  "ml-auto h-4 w-4 shrink-0 self-center text-muted-foreground/40 transition-transform duration-200",
                  open && "rotate-90"
                )}
              />
            </div>
          </div>
        </CollapsibleTrigger>

        {/* Body — always visible */}
        <div className="pb-4">
          {/* AI recap */}
          {session.recap ? (
            // Clamped while collapsed: the card is a preview, the full recap
            // belongs to the expanded state (tap anywhere on the header)
            <p className={cn("text-sm text-foreground/80 leading-relaxed", !open && "line-clamp-3")}>
              {searchTerm ? highlightText(session.recap, searchTerm) : session.recap}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground/60 italic">
              {t("summaryNotYetGenerated")}
            </p>
          )}

          {/* Stats row — labelled, zeros hidden */}
          {stats.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3">
              {stats.map((s, i) => (
                <span
                  key={i}
                  className="text-[11px] text-muted-foreground tabular-nums"
                >
                  {s.label}
                </span>
              ))}
            </div>
          )}

        </div>

        {/* Expanded debate list */}
        <CollapsibleContent id={contentId} role="region" aria-label={`${formattedDate} debates`}>
          <div className="pb-4 pt-1 border-t border-border/40">
            {/* Votes are recorded per sitting, so their entry point lives
                here rather than repeated inside every debate panel. */}
            {session.vote_count > 0 && (
              <button
                type="button"
                onClick={() => setVotesSheetOpen(true)}
                className="group flex w-full items-center gap-2.5 py-2.5 px-3 -mx-3 rounded-lg text-left hover:bg-muted/50 transition-colors"
              >
                <Vote className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />
                <span className="text-sm flex-1 leading-snug font-medium">
                  {t("votesLabel", { count: session.vote_count })}
                </span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5" />
              </button>
            )}

            <div className="space-y-0.5">
              {substantive.map((debate) => {
                const title = cleanDebateTitle(debate.title);
                return (
                  <button
                    key={debate.id}
                    type="button"
                    onClick={() => setSelectedDebate({ id: debate.id, title })}
                    className="group flex w-full items-center gap-2.5 py-2.5 px-3 -mx-3 rounded-lg text-left hover:bg-muted/50 transition-colors"
                  >
                    <span className="text-sm flex-1 leading-snug">
                      {searchTerm ? highlightText(title, searchTerm) : title}
                    </span>
                    <span className="text-[11px] text-muted-foreground/50 tabular-nums shrink-0">
                      {t("speechCount", { count: debate.speech_count })}
                    </span>
                    <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5" />
                  </button>
                );
              })}
            </div>

            {procedural.length > 0 && (
              <Collapsible open={proceduralOpen} onOpenChange={setProceduralOpen}>
                <CollapsibleTrigger
                  className="mt-1 py-1.5 px-3 -mx-3 text-xs text-muted-foreground/70 hover:text-foreground transition-colors"
                  aria-expanded={proceduralOpen}
                  aria-controls={proceduralId}
                >
                  {proceduralOpen
                    ? t("proceduralItemsHide")
                    : t("proceduralItems", { count: procedural.length })}
                </CollapsibleTrigger>
                <CollapsibleContent id={proceduralId} role="region">
                  <div className="space-y-1 pb-1">
                    {procedural.map((d) => (
                      <p
                        key={d.id}
                        className="text-xs leading-snug text-muted-foreground/60"
                      >
                        {searchTerm
                          ? highlightText(cleanDebateTitle(d.title), searchTerm)
                          : cleanDebateTitle(d.title)}
                      </p>
                    ))}
                  </div>
                </CollapsibleContent>
              </Collapsible>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>

      <DebateSheet
        debate={selectedDebate}
        sessionNumber={session.number}
        sessionDate={session.date}
        onOpenChange={(isOpen) => {
          if (!isOpen) setSelectedDebate(null);
        }}
      />

      <SessionVotesSheet
        open={votesSheetOpen}
        sessionId={session.id}
        sessionNumber={session.number}
        sessionDate={session.date}
        voteCount={session.vote_count}
        onOpenChange={setVotesSheetOpen}
      />
    </div>
  );
}
