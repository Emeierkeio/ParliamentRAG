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
import { cn } from "@/lib/utils";
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

  const fullName = `${speaker.first_name} ${speaker.last_name}`;

  return (
    <Collapsible open={open} onOpenChange={handleOpenChange}>
      <CollapsibleTrigger
        className={cn(
          "group flex w-full items-start gap-3 py-3 px-3 -mx-3 rounded-lg text-left transition-colors",
          "hover:bg-muted/50",
          open && "bg-muted/30"
        )}
        aria-expanded={open}
        aria-controls={contentId}
      >
        {/* Left: speaker info */}
        <div className="flex-1 min-w-0 space-y-1">
          {/* Row 1: Name + party */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold leading-tight">
              {fullName}
            </span>
            {speaker.party && (
              <Badge
                variant="outline"
                className="text-[10px] px-1.5 py-0 font-medium shrink-0"
              >
                {speaker.party}
              </Badge>
            )}
            {speaker.is_government_member && (
              <Badge
                variant="default"
                className="text-[10px] px-1.5 py-0 gap-0.5 shrink-0"
              >
                <Shield className="h-2.5 w-2.5" />
              </Badge>
            )}
          </div>

          {/* Row 2: Role + speech count */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {speaker.speaking_role && (
              <>
                <span className="font-medium">{speaker.speaking_role}</span>
                <span className="text-muted-foreground/40">·</span>
              </>
            )}
            <span>{t("speechCount", { count: speaker.speech_count })}</span>
          </div>
        </div>

        {/* Right: chevron */}
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground/40 transition-transform duration-200 mt-1",
            open && "rotate-180"
          )}
        />
      </CollapsibleTrigger>

      <CollapsibleContent
        id={contentId}
        role="region"
        aria-label={`${fullName} speeches`}
      >
        <div className="ml-3 pl-3 border-l-2 border-border/40 pb-2 space-y-3">
          {/* Loading */}
          {summary.status === "loading" && (
            <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>{t("speakerSummaryLoading")}</span>
            </div>
          )}

          {/* Error */}
          {summary.status === "error" && (
            <p className="py-2 text-xs text-muted-foreground">
              {t("speakerSummaryUnavailable")}
            </p>
          )}

          {/* Loaded: show full speech texts */}
          {summary.status === "loaded" && (
            <>
              {summary.data.speeches.length > 0 ? (
                summary.data.speeches.map((speech, idx) => (
                  <div key={speech.id} className="space-y-1">
                    {/* Phase label + speech number */}
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/60">
                        {t("speechLabel", { n: idx + 1 })}
                      </span>
                      {speech.phase_title && (
                        <span className="text-[10px] text-muted-foreground/50 truncate max-w-[300px]">
                          {speech.phase_title}
                        </span>
                      )}
                    </div>
                    {/* Full speech text */}
                    <p className="[font-family:var(--font-display)] text-[15px] leading-relaxed text-foreground/85 whitespace-pre-line">
                      {speech.text}
                    </p>
                  </div>
                ))
              ) : (
                <p className="py-2 text-xs text-muted-foreground">
                  {t("speakerSummaryUnavailable")}
                </p>
              )}
            </>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
