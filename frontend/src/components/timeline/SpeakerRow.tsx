"use client";

import { useState, useId } from "react";
import { useTranslations } from "next-intl";
import { Shield, ChevronDown, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getSpeakerSummary } from "@/lib/timeline-api";
import type { SpeakerInfo, SpeakerSummaryResponse } from "@/types/timeline";

interface SpeakerRowProps {
  speaker: SpeakerInfo;
  debateId: string;
}

type SummaryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; data: SpeakerSummaryResponse }
  | { status: "error" };

export function SpeakerRow({ speaker, debateId }: SpeakerRowProps) {
  const t = useTranslations("Timeline");
  const contentId = useId();
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState<SummaryState>({ status: "idle" });

  const handleOpenChange = async (isOpen: boolean) => {
    setOpen(isOpen);
    if (isOpen && summary.status === "idle") {
      setSummary({ status: "loading" });
      try {
        const data = await getSpeakerSummary(debateId, speaker.id);
        setSummary({ status: "loaded", data });
      } catch {
        setSummary({ status: "error" });
      }
    }
  };

  const visiblePhases = speaker.phases.slice(0, 2);
  const extraPhases = speaker.phases.length - 2;

  return (
    <Collapsible open={open} onOpenChange={handleOpenChange}>
      <CollapsibleTrigger
        className="flex w-full items-center gap-2 py-2 border-b border-muted last:border-0 text-left"
        aria-expanded={open}
        aria-controls={contentId}
      >
        {/* Speaker name link */}
        <a
          href={`/ranking?speaker=${speaker.id}`}
          className="text-sm font-semibold underline-offset-4 hover:underline shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          {speaker.first_name} {speaker.last_name}
        </a>

        {/* Party badge */}
        {speaker.party && (
          <Badge variant="outline">{speaker.party}</Badge>
        )}

        {/* Role badge */}
        {speaker.speaking_role && (
          <Badge variant="secondary" className="text-xs">
            {speaker.speaking_role}
          </Badge>
        )}

        {/* Government member shield */}
        {speaker.is_government_member && (
          <Badge variant="default" className="text-xs gap-1">
            <Shield className="h-3.5 w-3.5" />
          </Badge>
        )}

        {/* Speech count */}
        <span className="text-xs text-muted-foreground">
          {t("speechCount", { count: speaker.speech_count })}
        </span>

        {/* Phase tags */}
        <div className="flex flex-wrap gap-1">
          {visiblePhases.map((phase, i) => (
            <Badge key={i} variant="outline" className="text-xs">
              {phase}
            </Badge>
          ))}
          {extraPhases > 0 && (
            <Badge variant="outline" className="text-xs">
              +{extraPhases} more
            </Badge>
          )}
        </div>

        {/* Chevron right-aligned */}
        <ChevronDown
          className={`ml-auto h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </CollapsibleTrigger>

      <CollapsibleContent
        id={contentId}
        role="region"
        aria-label={`${speaker.first_name} ${speaker.last_name} summary`}
      >
        <div className="bg-muted/20 rounded p-3 mt-1 ml-4 text-sm">
          {summary.status === "loading" && (
            <span className="text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin inline mr-2" />
              {t("speakerSummaryLoading")}
            </span>
          )}
          {summary.status === "loaded" && summary.data.summary && (
            <p>{summary.data.summary}</p>
          )}
          {summary.status === "loaded" && !summary.data.summary && (
            <p className="text-xs text-muted-foreground">
              {t("speakerSummaryUnavailable")}
            </p>
          )}
          {summary.status === "error" && (
            <p className="text-xs text-muted-foreground">
              {t("speakerSummaryUnavailable")}
            </p>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
