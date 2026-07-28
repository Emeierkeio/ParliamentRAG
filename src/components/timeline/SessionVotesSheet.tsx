"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { VotesList } from "./VotesList";
import { getSessionVotes } from "@/lib/timeline-api";
import type { VoteInfo } from "@/types/timeline";

interface SessionVotesSheetProps {
  open: boolean;
  sessionId: string;
  sessionNumber: number | null;
  sessionDate: string;
  voteCount: number;
  onOpenChange: (open: boolean) => void;
}

type VotesState =
  | { status: "loading" }
  | { status: "loaded"; votes: VoteInfo[] }
  | { status: "error" };

/* Votes are recorded per sitting in the Camera data, so they get their own
   panel at session level instead of being repeated inside every debate. */
export function SessionVotesSheet({
  open,
  sessionId,
  sessionNumber,
  sessionDate,
  voteCount,
  onOpenChange,
}: SessionVotesSheetProps) {
  const t = useTranslations("Timeline");
  const [state, setState] = useState<VotesState>({ status: "loading" });

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setState({ status: "loading" });
    getSessionVotes(sessionId)
      .then((votes) => {
        if (!cancelled) setState({ status: "loaded", votes });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [open, sessionId]);

  const formattedDate = new Date(sessionDate).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 p-0 sm:max-w-xl lg:max-w-2xl"
      >
        <SheetHeader className="border-b px-6 py-4">
          <SheetDescription className="text-[11px] uppercase tracking-[0.2em]">
            {sessionNumber !== null
              ? t("sessionRef", { number: sessionNumber, date: formattedDate })
              : formattedDate}
          </SheetDescription>
          <SheetTitle className="text-base leading-snug pr-6">
            {t("votesLabel", { count: voteCount })}
          </SheetTitle>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-6 py-4 pb-8">
          {state.status === "loading" && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {state.status === "error" && (
            <p className="py-10 text-sm text-muted-foreground text-center">
              {t("voteLoadError")}
            </p>
          )}
          {state.status === "loaded" && <VotesList votes={state.votes} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}
