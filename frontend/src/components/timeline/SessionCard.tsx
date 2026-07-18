"use client";

import { useState, useId } from "react";
import React from "react";
import { useTranslations } from "next-intl";
import { ChevronRight, MessageSquare, Vote, Mic } from "lucide-react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { DebateDetail } from "./DebateDetail";
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

interface DebateRowProps {
  debate: { id: string; title: string; speech_count: number };
  sessionDate: string;
  searchTerm?: string;
}

function DebateRow({ debate, sessionDate, searchTerm }: DebateRowProps) {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  const hasSpeeches = debate.speech_count > 0;

  // Non-expandable row for procedural items with 0 speeches
  if (!hasSpeeches) {
    return (
      <div className="flex w-full items-center gap-2.5 py-2.5 px-3 -mx-3">
        <span className="h-3.5 w-3.5 shrink-0" /> {/* spacer to align with expandable rows */}
        <span className="text-sm flex-1 leading-snug text-muted-foreground/60">
          {debate.title.trim()
            ? (searchTerm ? highlightText(debate.title, searchTerm) : debate.title)
            : "(untitled)"}
        </span>
      </div>
    );
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className="group flex w-full items-center gap-2.5 py-2.5 px-3 -mx-3 rounded-lg text-left hover:bg-muted/50 transition-colors"
        aria-expanded={open}
        aria-controls={contentId}
      >
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition-transform duration-200",
            open && "rotate-90"
          )}
        />
        <span className="text-sm flex-1 leading-snug">
          {searchTerm ? highlightText(debate.title, searchTerm) : debate.title}
        </span>
        <span className="text-[11px] text-muted-foreground/50 tabular-nums shrink-0">
          {debate.speech_count}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent id={contentId} role="region" aria-label={debate.title}>
        {open && (
          <div className="ml-6 pl-3 border-l border-border/50">
            <DebateDetail
              debateId={debate.id}
              debateTitle={debate.title}
              sessionDate={sessionDate}
            />
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}

export function SessionCard({ session, searchTerm }: SessionCardProps) {
  const t = useTranslations("Timeline");
  const [open, setOpen] = useState(false);
  const contentId = useId();

  const formattedDate = new Date(session.date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const titledDebates = session.debates.filter(d => d.title.trim());
  const previewDebates = titledDebates.slice(0, 3);
  const extraDebates = titledDebates.length - 3;

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
            <p className="text-sm text-foreground/80 leading-relaxed">
              {searchTerm ? highlightText(session.recap, searchTerm) : session.recap}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground/60 italic">
              {t("summaryNotYetGenerated")}
            </p>
          )}

          {/* Stats row — icon pills */}
          <div className="flex flex-wrap gap-3 mt-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <MessageSquare className="h-3 w-3" />
              {session.debate_count}
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Vote className="h-3 w-3" />
              {session.vote_count}
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Mic className="h-3 w-3" />
              {session.speech_count}
            </span>
          </div>

          {/* Debate preview (collapsed) */}
          {!open && previewDebates.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/40 space-y-1">
              {previewDebates.map((d) => (
                <p key={d.id} className="text-xs text-muted-foreground/70 truncate leading-relaxed">
                  {searchTerm ? highlightText(d.title, searchTerm) : d.title}
                </p>
              ))}
              {extraDebates > 0 && (
                <p className="text-xs text-primary/60 font-medium">
                  + {extraDebates} {t("debateCount", { count: extraDebates }).split(" ").pop()}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Expanded debate list */}
        <CollapsibleContent id={contentId} role="region" aria-label={`${formattedDate} debates`}>
          <div className="pb-4 pt-1 border-t border-border/40">
            <div className="space-y-0.5">
              {session.debates.map((debate) => (
                <DebateRow
                  key={debate.id}
                  debate={debate}
                  sessionDate={session.date}
                  searchTerm={searchTerm}
                />
              ))}
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
