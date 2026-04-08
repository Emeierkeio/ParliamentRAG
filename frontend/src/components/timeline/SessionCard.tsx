"use client";

import { useState, useId } from "react";
import React from "react";
import { useTranslations } from "next-intl";
import { ChevronDown } from "lucide-react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
      <mark key={i} className="bg-primary/10 text-primary">
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

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className="flex w-full items-center gap-2 py-2 text-left"
        aria-expanded={open}
        aria-controls={contentId}
      >
        <span className="text-sm font-semibold flex-1">
          {searchTerm
            ? highlightText(debate.title, searchTerm)
            : debate.title}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent
        id={contentId}
        role="region"
        aria-label={debate.title}
      >
        {open && (
          <DebateDetail
            debateId={debate.id}
            debateTitle={debate.title}
            sessionDate={sessionDate}
          />
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

  const previewDebates = session.debates.slice(0, 3);
  const extraDebates = session.debates.length - 3;

  return (
    <Card className="shadow-sm">
      <Collapsible open={open} onOpenChange={setOpen}>
        {/* Collapsed header / trigger */}
        <CollapsibleTrigger
          className="w-full text-left"
          aria-expanded={open}
          aria-controls={contentId}
        >
          <CardHeader className="px-6 py-4">
            <div className="flex items-center gap-3">
              <span className="text-base font-semibold">
                {formattedDate} — #{session.number}
              </span>
              <Badge variant="secondary" className="capitalize">
                {session.chamber}
              </Badge>
              <ChevronDown
                className={`ml-auto h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
                  open ? "rotate-180" : ""
                }`}
              />
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        {/* Always-visible card content */}
        <CardContent className="px-6 pb-4">
          {/* AI recap */}
          {session.recap ? (
            <p className="text-sm">
              {searchTerm
                ? highlightText(session.recap, searchTerm)
                : session.recap}
            </p>
          ) : (
            <em className="text-xs text-muted-foreground">
              {t("summaryNotYetGenerated")}
            </em>
          )}

          {/* Stats row */}
          <div className="flex flex-wrap gap-4 mt-3 text-xs font-semibold text-muted-foreground">
            <span>{t("debateCount", { count: session.debate_count })}</span>
            <span>{t("voteCount", { count: session.vote_count })}</span>
            <span>{t("speechCount", { count: session.speech_count })}</span>
          </div>

          {/* Debate title list preview (collapsed view) */}
          {!open && (
            <div className="mt-3 space-y-0.5">
              {previewDebates.map((d) => (
                <p key={d.id} className="text-xs text-muted-foreground truncate">
                  {searchTerm ? highlightText(d.title, searchTerm) : d.title}
                </p>
              ))}
              {extraDebates > 0 && (
                <p className="text-xs text-muted-foreground">
                  + {extraDebates} more
                </p>
              )}
            </div>
          )}
        </CardContent>

        {/* Expanded debate list */}
        <CollapsibleContent
          id={contentId}
          role="region"
          aria-label={`${formattedDate} debates`}
        >
          <div className="pl-4 border-l-2 border-muted mx-6 mt-0 mb-4 space-y-1">
            {session.debates.map((debate) => (
              <DebateRow
                key={debate.id}
                debate={debate}
                sessionDate={session.date}
                searchTerm={searchTerm}
              />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
