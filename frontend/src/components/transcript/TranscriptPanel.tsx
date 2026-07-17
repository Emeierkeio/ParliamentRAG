"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { TranscriptSpeechRow as SpeechRowData } from "@/types/transcript";
import { SpeechRow } from "./SpeechRow";
import { PhaseHeader } from "./PhaseHeader";

interface TranscriptPanelProps {
  debateId: string;
  speeches: SpeechRowData[];
  targetSpeechId?: string | null;
  onTargetConsumed?: () => void;
  /** Speech IDs to auto-expand (from search results) */
  searchOpenIds?: string[];
  /** Current search query for text highlighting */
  searchQuery?: string;
}

export function TranscriptPanel({ debateId, speeches, targetSpeechId, onTargetConsumed, searchOpenIds, searchQuery }: TranscriptPanelProps) {
  const [openSpeechIds, setOpenSpeechIds] = useState<Set<string>>(new Set());
  const [speechesLoaded, setSpeechesLoaded] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Mark speeches as loaded for deep-link effect
  useEffect(() => {
    if (speeches.length > 0) setSpeechesLoaded(true);
  }, [speeches]);

  // Deep-link: read hash on mount AFTER speeches are loaded
  useEffect(() => {
    if (!speechesLoaded) return;
    const hash = window.location.hash;
    if (!hash.startsWith("#speech-")) return;
    const speechId = hash.slice("#speech-".length);
    setOpenSpeechIds(new Set([speechId]));
    requestAnimationFrame(() => {
      setTimeout(() => {
        const el = document.getElementById(`speech-${speechId}`);
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    });
  }, [speechesLoaded]);

  // React to searchOpenIds changes — auto-expand matching speeches
  useEffect(() => {
    if (!searchOpenIds || searchOpenIds.length === 0) {
      // When search is cleared, close all
      setOpenSpeechIds(new Set());
      return;
    }
    setOpenSpeechIds(new Set(searchOpenIds));
    // Scroll to the first match
    if (searchOpenIds[0]) {
      setTimeout(() => {
        const el = document.getElementById(`speech-${searchOpenIds[0]}`);
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 300);
    }
  }, [searchOpenIds]);

  // Scroll to speech programmatically (called by chatbot citation click via targetSpeechId)
  const scrollToSpeech = useCallback((speechId: string) => {
    setOpenSpeechIds((prev) => new Set(prev).add(speechId));
    requestAnimationFrame(() => {
      setTimeout(() => {
        const el = document.getElementById(`speech-${speechId}`);
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
        el?.classList.add("highlight-pulse");
        setTimeout(() => el?.classList.remove("highlight-pulse"), 2000);
      }, 100);
    });
  }, []);

  // React to targetSpeechId prop changes (from chatbot citation click)
  useEffect(() => {
    if (targetSpeechId) {
      scrollToSpeech(targetSpeechId);
      onTargetConsumed?.();
    }
  }, [targetSpeechId, scrollToSpeech, onTargetConsumed]);

  const handleOpenChange = useCallback((speechId: string, isOpen: boolean) => {
    setOpenSpeechIds((prev) => {
      const next = new Set(prev);
      if (isOpen) next.add(speechId);
      else next.delete(speechId);
      return next;
    });
  }, []);

  // Build elements with phase dividers
  const elements: React.ReactNode[] = [];
  let lastPhaseId: string | null = null;

  speeches.forEach((speech) => {
    if (speech.phase_id !== lastPhaseId) {
      elements.push(
        <PhaseHeader key={`phase-${speech.phase_id}`} id={speech.phase_id} title={speech.phase_title} />
      );
      lastPhaseId = speech.phase_id;
    }

    elements.push(
      <SpeechRow
        key={speech.speech_id}
        debateId={debateId}
        speech={speech}
        isOpen={openSpeechIds.has(speech.speech_id)}
        onOpenChange={(isOpen: boolean) => handleOpenChange(speech.speech_id, isOpen)}
        highlightQuery={searchQuery}
      />
    );
  });

  return (
    <div ref={containerRef} className="px-4 py-4 lg:px-6">
      {elements}
    </div>
  );
}
