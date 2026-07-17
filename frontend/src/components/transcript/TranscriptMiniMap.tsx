"use client";

import { useState, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import type { TranscriptSpeechRow } from "@/types/transcript";

interface PhaseBlock {
  id: string;
  title: string;
  speechCount: number;
}

interface TranscriptMiniMapProps {
  speeches: TranscriptSpeechRow[];
}

export function TranscriptMiniMap({ speeches }: TranscriptMiniMapProps) {
  const [activePhaseId, setActivePhaseId] = useState<string | null>(null);

  // Compute phase blocks from speeches
  const phases = useMemo(() => {
    const map = new Map<string, PhaseBlock>();
    for (const sp of speeches) {
      if (!map.has(sp.phase_id)) {
        map.set(sp.phase_id, {
          id: sp.phase_id,
          title: sp.phase_title,
          speechCount: 0,
        });
      }
      map.get(sp.phase_id)!.speechCount++;
    }
    return Array.from(map.values());
  }, [speeches]);

  // Track which phase is currently visible via IntersectionObserver on PhaseHeader elements
  // PhaseHeader (Plan 04) renders data-phase-id={id} on its root div
  useEffect(() => {
    const timer = setTimeout(() => {
      const headers = document.querySelectorAll("[data-phase-id]");
      if (headers.length === 0) return;

      const observer = new IntersectionObserver(
        (entries) => {
          // Find the topmost visible phase header
          for (const entry of entries) {
            if (entry.isIntersecting) {
              const phaseId = (entry.target as HTMLElement).dataset.phaseId;
              if (phaseId) setActivePhaseId(phaseId);
            }
          }
        },
        { rootMargin: "-20% 0px -70% 0px" },
      );

      headers.forEach((h) => observer.observe(h));
      return () => observer.disconnect();
    }, 500);

    return () => clearTimeout(timer);
  }, [speeches]);

  // Set first phase as default active
  useEffect(() => {
    if (!activePhaseId && phases.length > 0) {
      setActivePhaseId(phases[0].id);
    }
  }, [activePhaseId, phases]);

  const handleClick = (phaseId: string) => {
    const el = document.querySelector(`[data-phase-id="${phaseId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Calculate heights proportional to speech count
  const maxSpeeches = Math.max(...phases.map((p) => p.speechCount), 1);

  return (
    <div
      className="hidden lg:flex flex-col w-20 shrink-0 bg-sidebar overflow-y-auto"
      aria-label="Debate navigation"
    >
      {phases.map((phase, idx) => {
        const height = Math.max(24, Math.min(80, (phase.speechCount / maxSpeeches) * 80));
        const isActive = activePhaseId === phase.id;

        return (
          <button
            key={phase.id}
            onClick={() => handleClick(phase.id)}
            className={cn(
              "w-full flex items-center justify-center text-sidebar-foreground/60 hover:text-sidebar-foreground transition-colors border-b border-sidebar-border",
              isActive && "border-l-2 border-l-sidebar-primary bg-sidebar-accent/20 text-sidebar-foreground",
            )}
            style={{ minHeight: `${height}px` }}
            aria-label={`Go to phase: ${phase.title}`}
            title={`${phase.title} (${phase.speechCount})`}
          >
            <span className="text-[9px] font-medium text-center leading-tight px-1 line-clamp-3">
              {phase.title.replace(/^\(/, "").replace(/\)$/, "").split(" ").slice(0, 3).join(" ")}
            </span>
          </button>
        );
      })}
    </div>
  );
}
