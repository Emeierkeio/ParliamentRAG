"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { KIND_LABEL_KEYS, voteKind, voteTitle } from "@/lib/vote-utils";
import { VoteDetailDialog } from "./VoteDetailDialog";
import type { VoteInfo } from "@/types/timeline";

interface VotesListProps {
  votes: VoteInfo[];
}

/* Amendment marathons produce 100+ near-identical rejected rows. Above
   the threshold only the votes worth reading stay visible by default:
   approvals, votes with a real subject (serial amendment votes carry a
   bare "Votazione"), knife-edge margins, and the last scrutiny of the
   series (often the final vote). */
const VOTES_COLLAPSE_THRESHOLD = 8;

export function VotesList({ votes }: VotesListProps) {
  const t = useTranslations("Timeline");
  const [showAll, setShowAll] = useState(false);
  const [selectedVote, setSelectedVote] = useState<VoteInfo | null>(null);

  const isKeyVote = (v: VoteInfo, i: number) => {
    if (v.outcome === "approved") return true;
    if (v.final_vote) return true;
    if (v.subject && !/^votazione\.?$/i.test(v.subject.trim())) return true;
    if (
      v.in_favor !== null &&
      v.against !== null &&
      Math.abs(v.in_favor - v.against) <= 10
    )
      return true;
    return i === votes.length - 1;
  };

  const collapse = votes.length > VOTES_COLLAPSE_THRESHOLD && !showAll;
  const visibleVotes = collapse ? votes.filter((v, i) => isKeyVote(v, i)) : votes;
  const approvedCount = votes.filter((v) => v.outcome === "approved").length;
  const rejectedCount = votes.filter((v) => v.outcome === "rejected").length;
  const otherCount = votes.length - approvedCount - rejectedCount;

  return (
    <div>
      {votes.length > VOTES_COLLAPSE_THRESHOLD && (
        <div className="mb-2">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums">
            <span className="text-emerald-700 dark:text-emerald-500">
              {t("votesApproved", { count: approvedCount })}
            </span>
            <span className="text-red-700 dark:text-red-500">
              {t("votesRejected", { count: rejectedCount })}
            </span>
            {otherCount > 0 && (
              <span className="text-muted-foreground">
                {t("votesOther", { count: otherCount })}
              </span>
            )}
          </div>
          <div className="mt-1.5 flex h-1 w-full max-w-xs overflow-hidden rounded-full bg-muted">
            {approvedCount > 0 && (
              <div
                className="bg-emerald-600"
                style={{ width: `${(approvedCount / votes.length) * 100}%` }}
              />
            )}
            {rejectedCount > 0 && (
              <div
                className="bg-red-600"
                style={{ width: `${(rejectedCount / votes.length) * 100}%` }}
              />
            )}
          </div>
        </div>
      )}
      <div className="space-y-0.5">
        {visibleVotes.map((vote) => {
          const kind = voteKind(vote);
          const title = voteTitle(vote);
          return (
          <button
            key={vote.id}
            type="button"
            onClick={() => setSelectedVote(vote)}
            className="group flex w-full flex-wrap items-center gap-2 rounded-md px-2 py-1 -mx-2 text-left text-xs transition-colors hover:bg-muted/60"
            title={t("voteDetailHint")}
          >
            {kind && (
              <span className="shrink-0 rounded border border-border/60 px-1 py-px text-[10px] uppercase tracking-wide text-muted-foreground">
                {t(KIND_LABEL_KEYS[kind])}
              </span>
            )}
            {title && (
              <span className="text-muted-foreground group-hover:text-foreground group-hover:underline underline-offset-2">
                {title}
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
          );
        })}
        {votes.length > VOTES_COLLAPSE_THRESHOLD && (
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="mt-1 text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground transition-colors"
          >
            {showAll
              ? t("showFewerVotes")
              : t("showAllVotes", { count: votes.length })}
          </button>
        )}
      </div>

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
