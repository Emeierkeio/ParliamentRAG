"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Search, ChevronUp, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface TranscriptSearchProps {
  containerRef: React.RefObject<HTMLElement | null>;
}

export function TranscriptSearch({ containerRef }: TranscriptSearchProps) {
  const t = useTranslations("Transcript");
  const [query, setQuery] = useState("");
  const [matchCount, setMatchCount] = useState(0);
  const [currentMatch, setCurrentMatch] = useState(0);
  const highlightRefs = useRef<HTMLElement[]>([]);

  // Clear and apply highlights when query changes
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Remove previous highlights
    const existing = container.querySelectorAll("mark[data-search-highlight]");
    existing.forEach((mark) => {
      const parent = mark.parentNode;
      if (parent) {
        parent.replaceChild(document.createTextNode(mark.textContent || ""), mark);
        parent.normalize();
      }
    });

    if (!query || query.length < 2) {
      setMatchCount(0);
      setCurrentMatch(0);
      highlightRefs.current = [];
      return;
    }

    // Find and highlight matches in text nodes
    const matches: HTMLElement[] = [];
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    const textNodes: Text[] = [];
    let node: Text | null;
    while ((node = walker.nextNode() as Text | null)) {
      textNodes.push(node);
    }

    const lowerQuery = query.toLowerCase();
    for (const textNode of textNodes) {
      const text = textNode.textContent || "";
      const lowerText = text.toLowerCase();
      let startIdx = 0;
      const indices: number[] = [];

      while ((startIdx = lowerText.indexOf(lowerQuery, startIdx)) !== -1) {
        indices.push(startIdx);
        startIdx += lowerQuery.length;
      }

      if (indices.length === 0) continue;

      // Split text node and wrap matches in <mark>
      const fragment = document.createDocumentFragment();
      let lastEnd = 0;
      for (const idx of indices) {
        if (idx > lastEnd) {
          fragment.appendChild(document.createTextNode(text.slice(lastEnd, idx)));
        }
        const mark = document.createElement("mark");
        mark.setAttribute("data-search-highlight", "true");
        mark.className = "bg-yellow-100 dark:bg-yellow-900/30 rounded-sm px-0.5";
        mark.textContent = text.slice(idx, idx + query.length);
        fragment.appendChild(mark);
        matches.push(mark);
        lastEnd = idx + query.length;
      }
      if (lastEnd < text.length) {
        fragment.appendChild(document.createTextNode(text.slice(lastEnd)));
      }
      textNode.parentNode?.replaceChild(fragment, textNode);
    }

    highlightRefs.current = matches;
    setMatchCount(matches.length);
    setCurrentMatch(matches.length > 0 ? 1 : 0);

    // Scroll to first match
    if (matches.length > 0) {
      matches[0].className = "bg-yellow-200 dark:bg-yellow-800/50 rounded-sm px-0.5";
      matches[0].scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [query, containerRef]);

  const navigateMatch = useCallback(
    (direction: "up" | "down") => {
      if (matchCount === 0) return;
      const marks = highlightRefs.current;

      // Reset current highlight
      const prevIdx = currentMatch - 1;
      if (marks[prevIdx]) {
        marks[prevIdx].className = "bg-yellow-100 dark:bg-yellow-900/30 rounded-sm px-0.5";
      }

      let nextIdx: number;
      if (direction === "down") {
        nextIdx = currentMatch >= matchCount ? 0 : currentMatch;
      } else {
        nextIdx = currentMatch <= 1 ? matchCount - 1 : currentMatch - 2;
      }

      // Highlight and scroll to next match
      if (marks[nextIdx]) {
        marks[nextIdx].className = "bg-yellow-200 dark:bg-yellow-800/50 rounded-sm px-0.5";
        marks[nextIdx].scrollIntoView({ behavior: "smooth", block: "center" });
      }
      setCurrentMatch(nextIdx + 1);
    },
    [matchCount, currentMatch],
  );

  const hasNoResults = query.length >= 2 && matchCount === 0;

  return (
    <div className="sticky top-0 z-10 bg-background border-b px-4 py-2 flex items-center gap-2">
      <Search className="h-4 w-4 text-muted-foreground shrink-0" />
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("searchPlaceholder")}
        className={cn("h-8 text-sm", hasNoResults && "border-destructive")}
        aria-label={t("searchPlaceholder")}
      />
      {query.length >= 2 && (
        <div className="flex items-center gap-1 shrink-0">
          <span
            className="text-xs text-muted-foreground min-w-[60px] text-right"
            aria-live="polite"
          >
            {matchCount > 0
              ? t("searchMatchCount", { current: currentMatch, total: matchCount })
              : t("searchNoResults")}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => navigateMatch("up")}
            disabled={matchCount === 0}
          >
            <ChevronUp className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => navigateMatch("down")}
            disabled={matchCount === 0}
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
