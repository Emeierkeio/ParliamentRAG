"use client";

import { useState, useMemo, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Check, X, Minus, Loader2 } from "lucide-react";

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
  absent: { dot: "text-muted-foreground/60", icon: Minus },
};

export function VoteDetailDialog({ vote, open, onOpenChange }: VoteDetailDialogProps) {
  const t = useTranslations("Timeline");
  const [detail, setDetail] = useState<DetailState>({ status: "loading" });
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setDetail({ status: "loading" });
    setQuery("");
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
    if (!q) return detail.data.participants;
    return detail.data.participants.filter(
      (p) =>
        `${p.first_name} ${p.last_name}`.toLowerCase().includes(q) ||
        (p.party ?? "").toLowerCase().includes(q),
    );
  }, [detail, query]);

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
          <div className="flex items-start justify-between gap-3 pr-6">
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
            </DialogDescription>
          )}
        </DialogHeader>

        {detail.status === "loading" && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {detail.status === "error" && (
          <p className="px-6 py-10 text-sm text-muted-foreground text-center">
            {t("voteLoadError")}
          </p>
        )}

        {detail.status === "loaded" && (
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
            {/* Per-party stacked bars */}
            {detail.data.breakdown.length > 0 && (
              <section>
                <h4 className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                  {t("voteBreakdownHeading")}
                </h4>
                <div className="space-y-2">
                  {detail.data.breakdown.map((b) => {
                    const total = b.favor + b.against + b.absent;
                    return (
                      <div key={b.party}>
                        <div className="flex items-baseline justify-between gap-2 text-xs">
                          <span className="truncate font-medium">{b.party}</span>
                          <span className="shrink-0 tabular-nums text-muted-foreground">
                            <span className="text-emerald-700 dark:text-emerald-500">{b.favor}</span>
                            {" / "}
                            <span className="text-red-700 dark:text-red-500">{b.against}</span>
                            {" / "}
                            {b.absent}
                          </span>
                        </div>
                        <div className="mt-1 flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          {b.favor > 0 && (
                            <div
                              className="bg-emerald-600"
                              style={{ width: `${(b.favor / total) * 100}%` }}
                            />
                          )}
                          {b.against > 0 && (
                            <div
                              className="bg-red-600"
                              style={{ width: `${(b.against / total) * 100}%` }}
                            />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
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
        )}
      </DialogContent>
    </Dialog>
  );
}
