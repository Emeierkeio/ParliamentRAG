"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { ChevronRight, Link2, Shield } from "lucide-react";
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
  highlightQuery?: string;
}

/** Highlight search query matches in text */
function HighlightedText({ text, query }: { text: string; query?: string }) {
  if (!query || query.length < 2) {
    return <>{text}</>;
  }
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  const qLower = query.toLowerCase();
  return (
    <>
      {parts.map((part, i) => {
        const isMatch = part.length === query.length && part.toLowerCase() === qLower;
        return isMatch ? (
          <mark key={i} className="bg-yellow-300 dark:bg-yellow-800/60 rounded-sm px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </>
  );
}

type TextState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; text: string }
  | { status: "error" };

export function SpeechRow({ debateId, speech, isOpen, onOpenChange, highlightQuery }: SpeechRowProps) {
  const t = useTranslations("Transcript");
  const [textState, setTextState] = useState<TextState>({ status: "idle" });
  const [copyTooltip, setCopyTooltip] = useState(false);

  // Auto-fetch text when opened programmatically (search, deep-link, citation)
  const prevIsOpen = useRef(isOpen);
  useEffect(() => {
    if (isOpen && !prevIsOpen.current && textState.status === "idle") {
      setTextState({ status: "loading" });
      getSpeechText(debateId, speech.speech_id)
        .then((data) => setTextState({ status: "loaded", text: data.text }))
        .catch(() => setTextState({ status: "error" }));
    }
    prevIsOpen.current = isOpen;
  }, [isOpen, textState.status, debateId, speech.speech_id]);

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

  const fullName = `${speech.first_name} ${speech.last_name}`;

  return (
    <Collapsible
      id={`speech-${speech.speech_id}`}
      open={isOpen}
      onOpenChange={handleOpenChange}
    >
      <CollapsibleTrigger
        className={cn(
          "flex w-full items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-colors group",
          "hover:bg-muted/50",
          isOpen && "bg-muted/30"
        )}
      >
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition-transform duration-200",
            isOpen && "rotate-90"
          )}
        />

        {/* Speaker info — two-line layout */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold truncate">{fullName}</span>
            {speech.is_government_member && (
              <Shield className="h-3 w-3 shrink-0 text-primary" />
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            {speech.party && (
              <span className="text-[11px] text-muted-foreground truncate max-w-[200px]">
                {speech.party}
              </span>
            )}
            {speech.party && speech.speaking_role && (
              <span className="text-muted-foreground/40 text-[11px]">·</span>
            )}
            {speech.speaking_role && (
              <span className="text-[11px] text-muted-foreground font-medium">
                {speech.speaking_role}
              </span>
            )}
          </div>
        </div>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="ml-8 mr-3 mb-1 pl-3 border-l-2 border-border/40 relative">
          {textState.status === "loading" && (
            <div className="space-y-2 py-3">
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-3/4" />
            </div>
          )}
          {textState.status === "error" && (
            <button
              onClick={handleRetry}
              className="text-sm text-destructive py-3 hover:underline"
            >
              {t("speechError")}
            </button>
          )}
          {textState.status === "loaded" && (
            <>
              <p className="[font-family:var(--font-display)] text-[15px] leading-relaxed whitespace-pre-wrap py-2 text-foreground/90">
                <HighlightedText text={textState.text} query={highlightQuery} />
              </p>
              <div className="absolute top-1 right-0">
                <Tooltip open={copyTooltip}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
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
