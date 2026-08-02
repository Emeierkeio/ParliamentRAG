"use client";

import { useState, useMemo, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Check, X, Minus, Info } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getVoteDetail } from "@/lib/timeline-api";
import { VoteHemicycle, wedgeKey, wedgeRank } from "@/components/timeline/VoteHemicycle";
import type { VoteInfo, VoteDetailResponse } from "@/types/timeline";

interface VoteDetailDialogProps {
  vote: VoteInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type DetailState =
  | { status: "loading" }
  | { status: "loaded"; data: VoteDetailResponse }
  | { status: "error" };

const OUTCOME_STYLES: Record<string, { dot: string; icon: typeof Check }> = {
  favor: { dot: "text-emerald-600", icon: Check },
  against: { dot: "text-red-600", icon: X },
  abstain: { dot: "text-amber-500", icon: Minus },
  absent: { dot: "text-muted-foreground/60", icon: Minus },
};

export function VoteDetailDialog({ vote, open, onOpenChange }: VoteDetailDialogProps) {
  const t = useTranslations("Timeline");
  const [detail, setDetail] = useState<DetailState>({ status: "loading" });
  const [query, setQuery] = useState("");
  const [selectedParty, setSelectedParty] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setDetail({ status: "loading" });
    setQuery("");
    setSelectedParty(null);
    getVoteDetail(vote.id)
      .then((data) => {
        if (!cancelled) setDetail({ status: "loaded", data });
      })
      .catch(() => {
        if (!cancelled) setDetail({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [open, vote.id]);

  const filtered = useMemo(() => {
    if (detail.status !== "loaded") return [];
    const q = query.trim().toLowerCase();
    return detail.data.participants
      .filter(
        (p) =>
          (selectedParty === null || wedgeKey(p.party) === selectedParty) &&
          (!q || `${p.first_name} ${p.last_name}`.toLowerCase().includes(q)),
      )
      // Same left→right order as the hemicycle; Misto components cluster
      // together, then A→Z by surname within each group/component.
      .sort(
        (a, b) =>
          wedgeRank(a.party) - wedgeRank(b.party) ||
          (a.party ?? "").localeCompare(b.party ?? "") ||
          a.last_name.localeCompare(b.last_name) ||
          a.first_name.localeCompare(b.first_name),
      );
  }, [detail, query, selectedParty]);

  const outcomeLabel = (outcome: string | null) =>
    outcome === "approved"
      ? t("outcomeApproved")
      : outcome === "rejected"
        ? t("outcomeRejected")
        : outcome;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          {/* pr-10 clears the absolute ✕ button (right-4 + icon + focus ring) */}
          <div className="flex items-start justify-between gap-3 pr-10">
            <DialogTitle className="text-base leading-snug">
              {vote.subject || t("votesLabel", { count: 1 })}
            </DialogTitle>
            {vote.outcome && (
              <Badge
                variant={vote.outcome === "approved" ? "default" : "secondary"}
                className="shrink-0"
              >
                {outcomeLabel(vote.outcome)}
              </Badge>
            )}
          </div>
          {detail.status === "loaded" && (
            <DialogDescription asChild>
              <div className="space-y-1.5">
                {(detail.data.description || detail.data.act_title) && (
                  <div className="space-y-0.5 text-xs text-muted-foreground pr-10">
                    {detail.data.description &&
                      detail.data.description !== detail.data.subject && (
                        <p>{detail.data.description}</p>
                      )}
                    {detail.data.act_title && (
                      <p className="italic line-clamp-2">{detail.data.act_title}</p>
                    )}
                  </div>
                )}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <span className="text-emerald-700 dark:text-emerald-500 font-medium">
                  {t("voteFavor")}: {detail.data.in_favor ?? "–"}
                </span>
                <span className="text-red-700 dark:text-red-500 font-medium">
                  {t("voteAgainst")}: {detail.data.against ?? "–"}
                </span>
                {detail.data.abstained !== null && detail.data.abstained > 0 && (
                  <span>
                    {t("voteAbstained")}: {detail.data.abstained}
                  </span>
                )}
                {detail.data.present !== null && (
                  <span>
                    {t("votePresent")}: {detail.data.present}
                  </span>
                )}
                {detail.data.majority !== null && (
                  <span>
                    {t("voteMajority")}: {detail.data.majority}
                  </span>
                )}
                {detail.data.on_mission !== null && detail.data.on_mission > 0 && (
                  <span>
                    {t("voteOnMission")}: {detail.data.on_mission}
                  </span>
                )}
                </div>
              </div>
            </DialogDescription>
          )}
        </DialogHeader>

        {detail.status === "loading" && (
          <div className="px-6 py-4 space-y-5">
            {/* Hemicycle placeholder: half-donut + legend, then list rows */}
            <div className="mx-auto w-full max-w-md">
              <Skeleton className="mx-auto h-24 w-48 rounded-t-full" />
              <div className="mt-2 flex justify-center gap-4">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-4 w-full" />
              ))}
            </div>
          </div>
        )}

        {detail.status === "error" && (
          <p className="px-6 py-10 text-sm text-muted-foreground text-center">
            {t("voteLoadError")}
          </p>
        )}

        {detail.status === "loaded" && (() => {
          // Aggregates exist but every individual outcome is "absent":
          // either a secret ballot or the per-deputy dataset (published
          // separately by the Camera) is not out yet. Both look identical
          // in the graph, so one honest notice covers them — drawing an
          // all-grey chamber would read as "everyone was absent".
          const hasIndividualData = detail.data.participants.some(
            (p) =>
              p.outcome === "favor" ||
              p.outcome === "against" ||
              p.outcome === "abstain",
          );
          if (!hasIndividualData) {
            return (
              <div className="flex-1 overflow-y-auto px-6 py-4">
                <div className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
                  <Info className="mt-0.5 h-4 w-4 shrink-0" />
                  <p>{t("voteNoIndividualData")}</p>
                </div>
              </div>
            );
          }
          return (
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
            {detail.data.participants.length > 0 && (
              <VoteHemicycle
                participants={detail.data.participants}
                breakdown={detail.data.breakdown}
                selectedParty={selectedParty}
                onSelectParty={setSelectedParty}
              />
            )}

            {/* Individual votes */}
            <section>
              <div className="flex items-center justify-between gap-3 mb-2">
                <h4 className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                  {t("voteParticipantsHeading", {
                    count: detail.data.participants.length,
                  })}
                </h4>
              </div>
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("voteSearchPlaceholder")}
                className="h-8 text-sm mb-2"
              />
              {filtered.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  {t("voteNoMatches")}
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {filtered.map((p) => {
                    const style = OUTCOME_STYLES[p.outcome] ?? OUTCOME_STYLES.absent;
                    const Icon = style.icon;
                    return (
                      <li
                        key={p.id + p.outcome}
                        className="flex items-center gap-2 py-1.5 text-sm"
                      >
                        <Icon className={cn("h-3.5 w-3.5 shrink-0", style.dot)} />
                        <span className="truncate">
                          {p.first_name} {p.last_name}
                        </span>
                        {p.party && (
                          <span className="ml-auto shrink-0 max-w-[45%] truncate text-right text-[11px] text-muted-foreground">
                            {p.party}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </div>
          );
        })()}
      </DialogContent>
    </Dialog>
  );
}
