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
}

export function TranscriptPanel({ debateId, speeches, targetSpeechId, onTargetConsumed }: TranscriptPanelProps) {
  const [openSpeechId, setOpenSpeechId] = useState<string | null>(null);
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
    setOpenSpeechId(speechId);
    // Delay scroll to allow accordion to render
    requestAnimationFrame(() => {
      setTimeout(() => {
        const el = document.getElementById(`speech-${speechId}`);
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    });
  }, [speechesLoaded]);

  // Scroll to speech programmatically (called by chatbot citation click via targetSpeechId)
  const scrollToSpeech = useCallback((speechId: string) => {
    setOpenSpeechId(speechId);
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

  // Build elements with phase dividers
  const elements: React.ReactNode[] = [];
  let lastPhaseId: string | null = null;

  speeches.forEach((speech) => {
    // Insert phase header when phase changes
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
        isOpen={openSpeechId === speech.speech_id}
        onOpenChange={(isOpen: boolean) => {
          setOpenSpeechId(isOpen ? speech.speech_id : null);
        }}
      />
    );
  });

  return (
    <div ref={containerRef} className="px-4 py-4 lg:px-6">
      {elements}
    </div>
  );
}
