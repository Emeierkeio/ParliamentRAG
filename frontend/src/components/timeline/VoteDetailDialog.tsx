"use client";

import { useState, useMemo, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Check, X, Minus, Info, ExternalLink } from "lucide-react";

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
import { getVoteActText, getVoteDetail } from "@/lib/timeline-api";
import { voteKind, voteTitle } from "@/lib/vote-utils";
import { VoteHemicycle, wedgeKey, wedgeRank } from "@/components/timeline/VoteHemicycle";
import type { VoteInfo, VoteDetailResponse, VoteActTextResponse } from "@/types/timeline";

interface VoteDetailDialogProps {
  vote: VoteInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type DetailState =
  | { status: "loading" }
  | { status: "loaded"; data: VoteDetailResponse }
  | { status: "error" };

type ActTextState =
  | { status: "collapsed" }
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "loaded"; data: VoteActTextResponse };

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
  const [actText, setActText] = useState<ActTextState>({ status: "collapsed" });
  const [showActText, setShowActText] = useState(false);

  // Testo estraibile solo per emendamenti e articoli (l'Allegato A li ancóra);
  // per odg/mozioni c'è già il link alla scheda aic.camera.it.
  const kind = voteKind(vote);
  const canShowActText = kind === "amendment" || kind === "article";

  const toggleActText = () => {
    if (showActText) {
      setShowActText(false);
      return;
    }
    setShowActText(true);
    if (actText.status !== "collapsed") return;
    setActText({ status: "loading" });
    getVoteActText(vote.id)
      .then((data) =>
        setActText(data ? { status: "loaded", data } : { status: "unavailable" }),
      )
      .catch(() => setActText({ status: "unavailable" }));
  };

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setDetail({ status: "loading" });
    setQuery("");
    setSelectedParty(null);
    setActText({ status: "collapsed" });
    setShowActText(false);
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
              {voteTitle(vote) || t("votesLabel", { count: 1 })}
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
                {(detail.data.description ||
                  detail.data.acts.length > 0 ||
                  canShowActText) && (
                  <div className="space-y-0.5 text-xs text-muted-foreground pr-10">
                    {detail.data.description &&
                      !(voteTitle(vote) ?? "").includes(detail.data.description) && (
                        <p>{detail.data.description}</p>
                      )}
                    {detail.data.acts.map((act, i) => (
                      <div key={act.url ?? act.text_url ?? i}>
                        {act.url ? (
                          <a
                            href={act.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group/act block italic line-clamp-2 underline-offset-2 hover:underline hover:text-foreground"
                          >
                            {act.title ?? t("voteActFallback")}
                            <ExternalLink className="ml-1 inline h-3 w-3 align-[-1px] opacity-60 group-hover/act:opacity-100" />
                          </a>
                        ) : (
                          act.title && <p className="italic line-clamp-2">{act.title}</p>
                        )}
                        {act.text_url && (
                          <a
                            href={act.text_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="group/pdf inline-block text-[11px] underline-offset-2 hover:underline hover:text-foreground"
                          >
                            {t("voteActTextPdf")}
                            <ExternalLink className="ml-1 inline h-3 w-3 align-[-1px] opacity-60 group-hover/pdf:opacity-100" />
                          </a>
                        )}
                      </div>
                    ))}
                    {canShowActText && (
                      <div>
                        <button
                          type="button"
                          onClick={toggleActText}
                          className="underline underline-offset-2 hover:text-foreground"
                        >
                          {showActText ? t("voteHideText") : t("voteShowText")}
                        </button>
                        {showActText && actText.status === "loading" && (
                          <div className="mt-1.5 space-y-1.5">
                            <Skeleton className="h-3 w-full" />
                            <Skeleton className="h-3 w-4/5" />
                          </div>
                        )}
                        {showActText && actText.status === "unavailable" && (
                          <p className="mt-1 text-muted-foreground/70">
                            {t("voteTextUnavailable")}
                          </p>
                        )}
                        {showActText && actText.status === "loaded" && (
                          <div className="mt-1.5 max-h-44 space-y-1.5 overflow-y-auto rounded-md border border-border/60 bg-muted/30 px-3 py-2 text-left">
                            {actText.data.paragraphs.map((p, i) => (
                              <p key={i}>{p}</p>
                            ))}
                            <a
                              href={actText.data.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="group/src inline-block pt-0.5 text-[11px] text-muted-foreground/80 underline-offset-2 hover:underline hover:text-foreground"
                            >
                              {t("voteTextSource")}
                              <ExternalLink className="ml-1 inline h-3 w-3 align-[-1px] opacity-60 group-hover/src:opacity-100" />
                            </a>
                          </div>
                        )}
                      </div>
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
          // Solo favor/against contano come "dati individuali": nelle
          // votazioni segrete gli astenuti restano pubblici, e da soli
          // disegnerebbero un emiciclo tutto grigio.
          const hasIndividualData = detail.data.participants.some(
            (p) => p.outcome === "favor" || p.outcome === "against",
          );
          if (!hasIndividualData || detail.data.secret_vote) {
            return (
              <div className="flex-1 overflow-y-auto px-6 py-4">
                <div className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
                  <Info className="mt-0.5 h-4 w-4 shrink-0" />
                  <p>
                    {detail.data.secret_vote
                      ? t("voteSecretNotice")
                      : t("voteNoIndividualData")}
                  </p>
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
