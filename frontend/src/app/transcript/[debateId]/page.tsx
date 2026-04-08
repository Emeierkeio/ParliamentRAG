"use client";

import { useParams } from "next/navigation";
import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { TranscriptPanel } from "@/components/transcript/TranscriptPanel";
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
      <div className="shrink-0 border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">{data.debate_title}</h1>
          <Badge variant="outline" className="text-xs">{data.session_date}</Badge>
          <Badge variant="secondary" className="text-xs capitalize">{data.chamber}</Badge>
        </div>
        {/* Breadcrumb */}
        <nav className="mt-1 text-xs text-muted-foreground" aria-label="Breadcrumb">
          <Link href="/timeline" className="hover:text-primary transition-colors">
            {t("breadcrumbTimeline")}
          </Link>
          <span className="mx-1">&gt;</span>
          <span>{t("breadcrumbSession", { date: data.session_date })}</span>
          <span className="mx-1">&gt;</span>
          <span className="text-foreground">{data.debate_title}</span>
        </nav>
      </div>

      {/* Two-panel layout — chatbot panel placeholder for Plan 06 */}
      <div className="flex flex-1 overflow-hidden">
        {/* Transcript panel (60% desktop) */}
        <div className="flex-1 lg:w-3/5 overflow-y-auto scrollbar-thin">
          <TranscriptPanel
            debateId={debateId}
            speeches={data.speeches}
          />
        </div>

        {/* Chatbot panel placeholder (40% desktop) — will be implemented in Plan 06 */}
        <div className="hidden lg:flex lg:w-2/5 border-l bg-card flex-col items-center justify-center">
          <p className="text-sm text-muted-foreground">{t("chatTitle")}</p>
        </div>
      </div>
    </div>
  );
}
