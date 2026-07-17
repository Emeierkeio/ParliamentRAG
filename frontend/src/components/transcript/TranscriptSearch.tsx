"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Search, ChevronUp, ChevronDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { searchTranscript } from "@/lib/transcript-api";
import type { SearchMatch } from "@/types/transcript";

interface TranscriptSearchProps {
  debateId: string;
  /** Called with matching speech IDs and the query string */
  onSearchResults: (speechIds: string[], query: string) => void;
}

export function TranscriptSearch({ debateId, onSearchResults }: TranscriptSearchProps) {
  const t = useTranslations("Transcript");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<SearchMatch[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced search via backend API
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query || query.length < 2) {
      setMatches([]);
      setCurrentIdx(0);
      onSearchResults([], "");
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const result = await searchTranscript(debateId, query);
        setMatches(result.matches);
        setCurrentIdx(result.matches.length > 0 ? 0 : -1);

        // Tell parent to open these speeches and pass query for highlighting
        const ids = result.matches.map((m) => m.speech_id);
        onSearchResults(ids, query);

        // Scroll to first match after speeches expand
        if (ids.length > 0) {
          setTimeout(() => {
            const el = document.getElementById(`speech-${ids[0]}`);
            el?.scrollIntoView({ behavior: "smooth", block: "center" });
          }, 500);
        }
      } catch {
        setMatches([]);
        setCurrentIdx(-1);
      } finally {
        setIsSearching(false);
      }
    }, 400);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, debateId]);

  const navigateMatch = useCallback(
    (direction: "up" | "down") => {
      if (matches.length === 0) return;
      const next =
        direction === "down"
          ? (currentIdx + 1) % matches.length
          : (currentIdx - 1 + matches.length) % matches.length;
      setCurrentIdx(next);

      // Scroll to the speech element
      const speechId = matches[next].speech_id;
      const el = document.getElementById(`speech-${speechId}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    },
    [matches, currentIdx],
  );

  const hasNoResults = query.length >= 2 && !isSearching && matches.length === 0;

  return (
    <div className="sticky top-0 z-20 bg-background border-b px-4 py-2 flex items-center gap-2">
      <Search className="h-4 w-4 text-muted-foreground shrink-0" />
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && matches.length > 0) {
            e.preventDefault();
            navigateMatch(e.shiftKey ? "up" : "down");
          }
        }}
        placeholder={t("searchPlaceholder")}
        className={cn("h-8 text-sm", hasNoResults && "border-destructive")}
        aria-label={t("searchPlaceholder")}
      />
      {(query.length >= 2 || isSearching) && (
        <div className="flex items-center gap-1 shrink-0">
          <span
            className="text-xs text-muted-foreground min-w-[70px] text-right"
            aria-live="polite"
          >
            {isSearching ? (
              <Loader2 className="h-3 w-3 animate-spin inline" />
            ) : matches.length > 0 ? (
              t("searchMatchCount", {
                current: currentIdx + 1,
                total: matches.length,
              })
            ) : (
              t("searchNoResults")
            )}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => navigateMatch("up")}
            disabled={matches.length === 0}
          >
            <ChevronUp className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => navigateMatch("down")}
            disabled={matches.length === 0}
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
