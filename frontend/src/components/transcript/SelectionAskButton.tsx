"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslations } from "next-intl";
import { MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";

interface SelectionAskButtonProps {
  containerRef: React.RefObject<HTMLElement | null>;
  onAsk: (selectedText: string) => void;
}

export function SelectionAskButton({ containerRef, onAsk }: SelectionAskButtonProps) {
  const t = useTranslations("Transcript");
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const selectedTextRef = useRef("");

  const handleMouseUp = useCallback(() => {
    const selection = document.getSelection();
    const text = selection?.toString().trim() || "";

    if (text.length > 10 && containerRef.current) {
      // Check if selection is within the transcript container
      const range = selection?.getRangeAt(0);
      if (range && containerRef.current.contains(range.commonAncestorContainer)) {
        const rect = range.getBoundingClientRect();
        selectedTextRef.current = text;
        setPosition({
          top: rect.top + window.scrollY - 40,
          left: rect.left + window.scrollX,
        });
        setVisible(true);
        return;
      }
    }
    // Hide after a short delay (let click on button register first)
    setTimeout(() => setVisible(false), 200);
  }, [containerRef]);

  useEffect(() => {
    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, [handleMouseUp]);

  // Hide on scroll
  useEffect(() => {
    const hide = () => setVisible(false);
    window.addEventListener("scroll", hide, true);
    return () => window.removeEventListener("scroll", hide, true);
  }, []);

  if (!visible) return null;

  return (
    <div
      className="fixed z-[60]"
      style={{ top: `${position.top}px`, left: `${position.left}px` }}
    >
      <Button
        variant="default"
        size="sm"
        className="gap-1.5 shadow-lg animate-in fade-in duration-150"
        onMouseDown={(e) => {
          e.preventDefault(); // prevent selection clearing
          onAsk(selectedTextRef.current);
          setVisible(false);
        }}
        aria-label={t("askAboutThis")}
      >
        <MessageSquare className="h-3.5 w-3.5" />
        {t("askAboutThis")}
      </Button>
    </div>
  );
}
