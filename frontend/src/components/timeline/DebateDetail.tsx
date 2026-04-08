"use client";

import { useState, useEffect, useId } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { ArrowRight, BookOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { SpeakerRow } from "./SpeakerRow";
import { getDebateDetail } from "@/lib/timeline-api";
import type { DebateDetailResponse } from "@/types/timeline";

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
  const tTr = useTranslations("Transcript");
  const router = useRouter();
  const votesId = useId();
  const [detail, setDetail] = useState<DetailState>({ status: "idle" });
  const [votesOpen, setVotesOpen] = useState(false);

  useEffect(() => {
    if (detail.status !== "idle") return;
    setDetail({ status: "loading" });
    getDebateDetail(debateId)
      .then((data) => setDetail({ status: "loaded", data }))
      .catch(() => setDetail({ status: "error" }));
  }, [debateId, detail.status]);

  if (detail.status === "loading" || detail.status === "idle") {
    return (
      <div className="bg-muted/30 rounded-md p-4 mt-2 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    );
  }

  if (detail.status === "error") {
    return (
      <div className="bg-muted/30 rounded-md p-4 mt-2">
        <p className="text-sm text-muted-foreground">
          Unable to load debate details
        </p>
      </div>
    );
  }

  const { data } = detail;

  return (
    <div className="bg-muted/30 rounded-md p-4 mt-2">
      {/* 1. Debate recap */}
      {data.recap ? (
        <p className="text-sm">{data.recap}</p>
      ) : (
        <p className="text-xs text-muted-foreground italic">
          {data.phases.reduce((sum, p) => sum + p.speech_count, 0) < 3
            ? t("shortDebateNoSummary")
            : t("summaryNotYetGenerated")}
        </p>
      )}

      {/* 2. Phase list */}
      {data.phases.length > 0 && (
        <div className="mt-3 space-y-0.5">
          {data.phases.map((phase) => (
            <p key={phase.id} className="text-xs text-muted-foreground">
              {phase.title} ({t("speechCount", { count: phase.speech_count })})
            </p>
          ))}
        </div>
      )}

      {/* 3. Votes summary */}
      {data.votes.length > 0 && (
        <div className="mt-2">
          <Collapsible open={votesOpen} onOpenChange={setVotesOpen}>
            <CollapsibleTrigger
              className="text-xs font-semibold hover:underline underline-offset-4"
              aria-expanded={votesOpen}
              aria-controls={votesId}
            >
              {t("votesLabel", { count: data.votes.length })}
            </CollapsibleTrigger>
            <CollapsibleContent id={votesId} role="region">
              <div className="mt-1 space-y-1 pl-2">
                {data.votes.map((vote) => (
                  <div key={vote.id} className="flex flex-wrap items-center gap-2 text-xs">
                    {vote.subject && (
                      <span className="text-muted-foreground">{vote.subject}</span>
                    )}
                    {vote.outcome && (
                      <Badge
                        variant={vote.outcome === "approved" ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {vote.outcome}
                      </Badge>
                    )}
                    {(vote.in_favor !== null ||
                      vote.against !== null ||
                      vote.abstained !== null) && (
                      <span className="text-muted-foreground">
                        {vote.in_favor ?? "-"} / {vote.against ?? "-"} /{" "}
                        {vote.abstained ?? "-"}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}

      {/* 4. Acts badges */}
      {data.acts.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
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
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            {t("speakersHeading")}
          </h4>
          <div>
            {data.speakers.map((speaker, idx) => (
              <SpeakerRow key={`${speaker.id}-${idx}`} speaker={speaker} debateId={debateId} />
            ))}
          </div>
        </div>
      )}

      {/* 5.5 Read transcript button */}
      <div className="mt-3">
        <Button
          variant="default"
          size="sm"
          onClick={() => router.push(`/transcript/${encodeURIComponent(debateId)}`)}
        >
          <BookOpen className="mr-1 h-3.5 w-3.5" />
          {tTr("readTranscript")}
        </Button>
      </div>

      {/* 6. Ask about this button */}
      <div className="mt-4">
        <Button
          variant="default"
          size="sm"
          onClick={() =>
            router.push(
              "/home?q=" +
                encodeURIComponent(
                  t("askQuestionTemplate", {
                    debateTitle: data.title,
                    date: sessionDate,
                  }),
                ),
            )
          }
        >
          {t("askAboutThis")}
          <ArrowRight className="ml-1 h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
