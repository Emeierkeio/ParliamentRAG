"use client";

import { useState, useEffect, useId } from "react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { SpeakerRow } from "./SpeakerRow";
import { VoteDetailDialog } from "./VoteDetailDialog";
import { getDebateDetail } from "@/lib/timeline-api";
import type { DebateDetailResponse, VoteInfo } from "@/types/timeline";

interface DebateDetailProps {
  debateId: string;
  debateTitle: string;
  sessionDate: string;
}

type DetailState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; data: DebateDetailResponse }
  | { status: "error" };

export function DebateDetail({
  debateId,
  debateTitle,
  sessionDate,
}: DebateDetailProps) {
  const t = useTranslations("Timeline");
  const votesId = useId();
  const [detail, setDetail] = useState<DetailState>({ status: "idle" });
  const [votesOpen, setVotesOpen] = useState(false);
  const [selectedVote, setSelectedVote] = useState<VoteInfo | null>(null);

  useEffect(() => {
    if (detail.status !== "idle") return;
    setDetail({ status: "loading" });
    getDebateDetail(debateId)
      .then((data) => {
        setDetail({ status: "loaded", data });
        // Votes were invisible in practice behind a collapsed section —
        // open it by default whenever the debate's session has votes.
        if (data.votes.length > 0) setVotesOpen(true);
      })
      .catch(() => setDetail({ status: "error" }));
  }, [debateId, detail.status]);

  if (detail.status === "loading" || detail.status === "idle") {
    return (
      <div className="py-4 mt-2 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    );
  }

  if (detail.status === "error") {
    return (
      <div className="py-4 mt-2">
        <p className="text-sm text-muted-foreground">
          Unable to load debate details
        </p>
      </div>
    );
  }

  const { data } = detail;

  return (
    <div className="py-4 mt-2">
      {/* 1. Debate recap */}
      {data.recap ? (
        <p className="text-sm leading-relaxed text-foreground/85">{data.recap}</p>
      ) : (
        <p className="text-xs text-muted-foreground italic">
          {data.phases.reduce((sum, p) => sum + p.speech_count, 0) < 3
            ? t("shortDebateNoSummary")
            : t("summaryNotYetGenerated")}
        </p>
      )}

      {/* 2. Phase list */}
      {data.phases.length > 0 && (
        <div className="mt-4">
          <h4 className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
            {t("phasesHeading")}
          </h4>
          <div className="space-y-1">
            {data.phases.map((phase) => (
              <div
                key={phase.id}
                className="flex items-baseline justify-between gap-3 text-xs"
              >
                <span className="text-foreground/75 leading-snug">{phase.title}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground/60">
                  {t("speechCount", { count: phase.speech_count })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3. Votes summary */}
      {data.votes.length > 0 && (
        <div className="mt-4">
          <Collapsible open={votesOpen} onOpenChange={setVotesOpen}>
            <CollapsibleTrigger
              className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground hover:text-foreground transition-colors"
              aria-expanded={votesOpen}
              aria-controls={votesId}
            >
              {t("votesLabel", { count: data.votes.length })}
            </CollapsibleTrigger>
            <CollapsibleContent id={votesId} role="region">
              <div className="mt-1 space-y-0.5 pl-2">
                {data.votes.map((vote) => (
                  <button
                    key={vote.id}
                    type="button"
                    onClick={() => setSelectedVote(vote)}
                    className="group flex w-full flex-wrap items-center gap-2 rounded-md px-2 py-1 -mx-2 text-left text-xs transition-colors hover:bg-muted/60"
                    title={t("voteDetailHint")}
                  >
                    {vote.subject && (
                      <span className="text-muted-foreground group-hover:text-foreground group-hover:underline underline-offset-2">
                        {vote.subject}
                      </span>
                    )}
                    {vote.outcome && (
                      <Badge
                        variant={vote.outcome === "approved" ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {vote.outcome === "approved"
                          ? t("outcomeApproved")
                          : vote.outcome === "rejected"
                            ? t("outcomeRejected")
                            : vote.outcome}
                      </Badge>
                    )}
                    {(vote.in_favor !== null ||
                      vote.against !== null ||
                      vote.abstained !== null) && (
                      <span className="tabular-nums">
                        <span className="text-emerald-700 dark:text-emerald-500">
                          {vote.in_favor ?? "–"}
                        </span>
                        <span className="text-muted-foreground/50"> / </span>
                        <span className="text-red-700 dark:text-red-500">
                          {vote.against ?? "–"}
                        </span>
                        <span className="text-muted-foreground/50"> / </span>
                        <span className="text-muted-foreground">
                          {vote.abstained ?? "–"}
                        </span>
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}

      {/* 4. Acts badges */}
      {data.acts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {data.acts.map((act) => (
            <Badge key={act.id} variant="outline" className="text-xs">
              {act.title || act.type || act.id}
            </Badge>
          ))}
        </div>
      )}

      {/* 5. Speakers section */}
      {data.speakers.length > 0 && (
        <div className="mt-4">
          <h4 className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
            {t("speakersHeading")}
          </h4>
          <div>
            {data.speakers.map((speaker, idx) => (
              <SpeakerRow key={`${speaker.id}-${idx}`} speaker={speaker} debateId={debateId} />
            ))}
          </div>
        </div>
      )}

      {selectedVote && (
        <VoteDetailDialog
          vote={selectedVote}
          open={selectedVote !== null}
          onOpenChange={(open) => {
            if (!open) setSelectedVote(null);
          }}
        />
      )}
    </div>
  );
}
