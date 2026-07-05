"use client";

import { useParams } from "next/navigation";
import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { TranscriptPanel } from "@/components/transcript/TranscriptPanel";
import { TranscriptSearch } from "@/components/transcript/TranscriptSearch";
import { TranscriptMiniMap } from "@/components/transcript/TranscriptMiniMap";
import { TranscriptChatbot } from "@/components/transcript/TranscriptChatbot";
import { SelectionAskButton } from "@/components/transcript/SelectionAskButton";
import { useTranscriptChat } from "@/hooks/use-transcript-chat";
import { getTranscriptSpeeches } from "@/lib/transcript-api";
import type { TranscriptResponse } from "@/types/transcript";

type PageState =
  | { status: "loading" }
  | { status: "loaded"; data: TranscriptResponse }
  | { status: "error" };

export default function TranscriptPage() {
  const params = useParams();
  const debateId = params.debateId as string;
  const t = useTranslations("Transcript");
  const [state, setState] = useState<PageState>({ status: "loading" });

  // Chat state — single hook instance, shared by desktop panel and mobile sheet
  const { messages, isLoading, sendMessage, stopGenerating } = useTranscriptChat(debateId);
  const [prefillText, setPrefillText] = useState<string | null>(null);
  const [targetSpeechId, setTargetSpeechId] = useState<string | null>(null);
  const transcriptContainerRef = useRef<HTMLDivElement | null>(null);

  const [searchOpenIds, setSearchOpenIds] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  const handleCitationClick = useCallback((speechId: string) => {
    setTargetSpeechId(speechId);
  }, []);

  const handleSearchResults = useCallback((speechIds: string[], query: string) => {
    setSearchOpenIds(speechIds);
    setSearchQuery(query);
  }, []);

  useEffect(() => {
    getTranscriptSpeeches(debateId)
      .then((data) => setState({ status: "loaded", data }))
      .catch(() => setState({ status: "error" }));
  }, [debateId]);

  if (state.status === "loading") {
    return (
      <div className="flex-1 p-8 space-y-4">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-4 w-1/4" />
        <div className="mt-8 space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="flex-1 p-8">
        <Alert variant="destructive">
          <AlertDescription>{t("transcriptLoadError")}</AlertDescription>
        </Alert>
      </div>
    );
  }

  const { data } = state;

  return (
    <div className="flex flex-1 flex-col h-screen overflow-hidden">
      {/* Page header */}
      <div className="shrink-0 border-b px-6 py-3">
        {/* Breadcrumb */}
        <nav
          className="flex items-center text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5"
          aria-label="Breadcrumb"
        >
          <Link
            href="/timeline"
            className="group inline-flex items-center gap-1.5 hover:text-primary transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
            {t("breadcrumbTimeline")}
          </Link>
          <span className="mx-1.5">/</span>
          <span>{t("breadcrumbSession", { date: data.session_date })}</span>
        </nav>
        <div className="flex items-start gap-3">
          <h1 className="[font-family:var(--font-display)] text-lg sm:text-xl font-medium tracking-tight leading-snug line-clamp-2 flex-1">
            {data.debate_title}
          </h1>
          <div className="flex items-baseline gap-1.5 shrink-0 pt-1 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            <span className="tabular-nums">{data.session_date}</span>
            <span className="text-muted-foreground/40">·</span>
            <span>{data.chamber}</span>
          </div>
        </div>
      </div>

      {/* Two-panel layout: left = transcript, right = chatbot (handles desktop/mobile internally) */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: transcript panel with search and mini-map */}
        <div className="flex flex-1 lg:w-3/5">
          <div ref={transcriptContainerRef} className="flex-1 overflow-y-auto scrollbar-thin">
            <TranscriptSearch
              debateId={debateId}
              onSearchResults={handleSearchResults}
            />
            <TranscriptPanel
              debateId={debateId}
              speeches={data.speeches}
              targetSpeechId={targetSpeechId}
              onTargetConsumed={() => setTargetSpeechId(null)}
              searchOpenIds={searchOpenIds}
              searchQuery={searchQuery}
            />
          </div>
          <TranscriptMiniMap speeches={data.speeches} />
        </div>

        {/* Right: chatbot — single instance, handles desktop panel (hidden lg:flex) and mobile FAB/sheet (lg:hidden) internally */}
        <TranscriptChatbot
          debateId={debateId}
          messages={messages}
          isLoading={isLoading}
          sendMessage={sendMessage}
          stopGenerating={stopGenerating}
          onCitationClick={handleCitationClick}
          prefillText={prefillText}
          onPrefillConsumed={() => setPrefillText(null)}
        />
      </div>

      {/* Floating ask button on text selection — pre-fills chatbot input */}
      <SelectionAskButton
        containerRef={transcriptContainerRef}
        onAsk={(text) => setPrefillText(text)}
      />
    </div>
  );
}
