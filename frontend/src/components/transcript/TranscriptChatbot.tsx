"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Send, Square, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { getDebateSuggestions } from "@/lib/transcript-api";
import type { TranscriptMessage, TranscriptCitation } from "@/types/transcript";

interface TranscriptChatbotProps {
  debateId: string;
  messages: TranscriptMessage[];
  isLoading: boolean;
  sendMessage: (content: string) => void;
  stopGenerating: () => void;
  onCitationClick: (speechId: string) => void;
  prefillText?: string | null;
  onPrefillConsumed?: () => void;
}

export function TranscriptChatbot({
  debateId,
  messages,
  isLoading,
  sendMessage,
  stopGenerating,
  onCitationClick,
  prefillText,
  onPrefillConsumed,
}: TranscriptChatbotProps) {
  const t = useTranslations("Transcript");
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Load suggested questions on mount
  useEffect(() => {
    getDebateSuggestions(debateId)
      .then((data) => setSuggestions(data.questions))
      .catch(() => setSuggestions([]))
      .finally(() => setSuggestionsLoading(false));
  }, [debateId]);

  // Handle prefill from select-to-ask
  useEffect(() => {
    if (prefillText) {
      setInput(prefillText);
      inputRef.current?.focus();
      onPrefillConsumed?.();
    }
  }, [prefillText, onPrefillConsumed]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Parse citation references like [1], [2] in assistant message text
  const renderMessageContent = (content: string, citations?: TranscriptCitation[]) => {
    if (!citations || citations.length === 0) return content;

    const parts = content.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const idx = parseInt(match[1], 10);
        const citation = citations.find((c) => c.index === idx);
        if (citation) {
          return (
            <button
              key={i}
              className="text-primary font-semibold underline cursor-pointer hover:text-primary/80 transition-colors"
              onClick={() => onCitationClick(citation.speech_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onCitationClick(citation.speech_id);
              }}
              title={`${citation.speaker_name}${citation.party ? ` (${citation.party})` : ""}`}
            >
              [{idx}]
            </button>
          );
        }
      }
      return <span key={i}>{part}</span>;
    });
  };

  const chatContent = (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 py-3">
        <h2 className="text-lg font-semibold">{t("chatTitle")}</h2>
        <p className="text-xs text-muted-foreground">{t("chatSubtitle")}</p>
      </div>
      <Separator />

      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-3">
        {messages.length === 0 ? (
          <div className="text-center py-8 space-y-4">
            <h3 className="text-base font-semibold">{t("emptyStateTitle")}</h3>
            <p className="text-sm text-muted-foreground">
              {suggestions.length > 0 ? t("emptyStateBody") : t("emptyStateBodyNoSuggestions")}
            </p>
            {suggestionsLoading ? (
              <div className="space-y-2 pt-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : suggestions.length > 0 ? (
              <div className="space-y-2 pt-2">
                <p className="text-xs text-muted-foreground text-left">{t("suggestedQuestionsLabel")}</p>
                {suggestions.map((q, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    className="w-full justify-start text-left text-sm py-3 h-auto whitespace-normal"
                    onClick={() => {
                      setInput(q);
                      sendMessage(q);
                    }}
                  >
                    {q}
                  </Button>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "max-w-[80%] rounded-lg px-3 py-2",
                  msg.role === "user"
                    ? "ml-auto bg-primary text-primary-foreground"
                    : "mr-auto bg-muted"
                )}
              >
                {msg.role === "assistant" && msg.content === "" && isLoading ? (
                  <div className="space-y-1.5">
                    <Skeleton className="h-3.5 w-48" />
                    <Skeleton className="h-3.5 w-32" />
                  </div>
                ) : (
                  <div className="text-sm whitespace-pre-wrap">
                    {msg.role === "assistant"
                      ? renderMessageContent(msg.content, msg.citations)
                      : msg.content}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </ScrollArea>

      {/* Input */}
      <div className="shrink-0 border-t px-4 py-3">
        <div className="flex items-end gap-2">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("chatPlaceholder")}
            className="min-h-[40px] max-h-[120px] resize-none text-sm"
            rows={1}
          />
          {isLoading ? (
            <Button
              variant="outline"
              size="icon"
              className="shrink-0 h-10 w-10"
              onClick={stopGenerating}
              aria-label={t("stopGenerating")}
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              className="shrink-0 h-10 w-10"
              onClick={handleSend}
              disabled={!input.trim()}
              aria-label={t("sendMessage")}
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop: right panel (lg:w-2/5 border-l bg-card) — sits inside the flex layout */}
      <div className="hidden lg:flex lg:w-2/5 border-l bg-card flex-col h-full">{chatContent}</div>

      {/* Mobile: FAB + bottom sheet */}
      <div className="lg:hidden">
        <Sheet>
          <SheetTrigger asChild>
            <Button
              className="fixed bottom-6 right-6 z-50 h-12 gap-2 shadow-lg rounded-full px-4"
              aria-label={t("mobileFab")}
            >
              <MessageSquare className="h-5 w-5" />
              <span className="text-sm">{t("mobileFab")}</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="h-[70vh] p-0">
            {chatContent}
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
