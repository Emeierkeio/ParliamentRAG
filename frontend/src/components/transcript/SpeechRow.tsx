"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, Link2, Shield } from "lucide-react";
import { cn } from "@/lib/utils";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { getSpeechText } from "@/lib/transcript-api";
import type { TranscriptSpeechRow as SpeechData } from "@/types/transcript";

interface SpeechRowProps {
  debateId: string;
  speech: SpeechData;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

type TextState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; text: string }
  | { status: "error" };

export function SpeechRow({ debateId, speech, isOpen, onOpenChange }: SpeechRowProps) {
  const t = useTranslations("Transcript");
  const [textState, setTextState] = useState<TextState>({ status: "idle" });
  const [copyTooltip, setCopyTooltip] = useState(false);

  const handleOpenChange = async (open: boolean) => {
    onOpenChange(open);
    if (open && textState.status === "idle") {
      setTextState({ status: "loading" });
      try {
        const data = await getSpeechText(debateId, speech.speech_id);
        setTextState({ status: "loaded", text: data.text });
      } catch {
        setTextState({ status: "error" });
      }
    }
  };

  const handleRetry = async () => {
    setTextState({ status: "loading" });
    try {
      const data = await getSpeechText(debateId, speech.speech_id);
      setTextState({ status: "loaded", text: data.text });
    } catch {
      setTextState({ status: "error" });
    }
  };

  const handleCopyLink = async () => {
    const url = `${window.location.href.split("#")[0]}#speech-${speech.speech_id}`;
    await navigator.clipboard.writeText(url);
    setCopyTooltip(true);
    setTimeout(() => setCopyTooltip(false), 2000);
  };

  return (
    <Collapsible
      id={`speech-${speech.speech_id}`}
      open={isOpen}
      onOpenChange={handleOpenChange}
    >
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-3 py-2 rounded-md hover:bg-muted/50 transition-colors text-left group">
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
        <span className="text-sm font-semibold truncate">
          {speech.first_name} {speech.last_name}
        </span>
        {speech.party && (
          <Badge variant="outline" className="text-[10px] shrink-0">{speech.party}</Badge>
        )}
        {speech.speaking_role && (
          <Badge variant="secondary" className="text-[10px] shrink-0">{speech.speaking_role}</Badge>
        )}
        {speech.is_government_member && (
          <Badge variant="default" className="text-[10px] gap-0.5 shrink-0">
            <Shield className="h-3 w-3" />
            {t("governmentBadge")}
          </Badge>
        )}
        <span className="ml-auto text-xs text-muted-foreground shrink-0">
          {speech.phase_title}
        </span>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="pl-9 pr-3 pb-3 relative">
          {textState.status === "loading" && (
            <div className="space-y-2 py-2">
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-3/4" />
            </div>
          )}
          {textState.status === "error" && (
            <button
              onClick={handleRetry}
              className="text-sm text-destructive py-2 hover:underline"
            >
              {t("speechError")}
            </button>
          )}
          {textState.status === "loaded" && (
            <>
              <p className="text-[15px] leading-[1.6] whitespace-pre-wrap">
                {textState.text}
              </p>
              {/* Copy link button */}
              <div className="absolute top-0 right-0">
                <Tooltip open={copyTooltip}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={handleCopyLink}
                      aria-label={t("copyLink")}
                    >
                      <Link2 className="h-3.5 w-3.5" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {copyTooltip ? t("copyLinkDone") : t("copyLink")}
                  </TooltipContent>
                </Tooltip>
              </div>
            </>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
