"use client";

import React, { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { ProgressIndicator, ProgressBanner, CompletedProgressStepper, ProgressFullPage } from "@/components/shared/ProgressIndicator";
import { TranslationBanner } from "@/components/shared/TranslationBanner";
import type { Message, ProcessingProgress } from "@/types";
import { Landmark, ArrowRight, History } from "lucide-react";
import { TOPICS } from "@/lib/constants";

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  progress: ProcessingProgress | null;
  lastCompletedProgress?: ProcessingProgress | null;
  onSendMessage: (message: string) => void;
  onCancelRequest: () => void;
  onOpenHistory?: () => void;
  className?: string;
  mobileMenuButton?: React.ReactNode;
}

export function ChatArea({
  messages,
  isLoading,
  progress,
  lastCompletedProgress,
  onSendMessage,
  onCancelRequest,
  onOpenHistory,
  className,
  mobileMenuButton,
}: ChatAreaProps) {
  const t = useTranslations("WelcomeScreen");
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  // Auto-scroll to bottom on new messages
  useEffect(() => {
    // Only scroll if loading or if it's a user message (start of convo)
    // If it's the final message update (complete), we don't force scroll to bottom 
    // to allow user to read from top.
    if (isLoading || (messages.length > 0 && messages[messages.length-1].role === 'user')) {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, isLoading]); // Removed 'progress' to avoid jitter, used length to detect new msg

  const hasMessages = messages.length > 0;
  const lastAssistantMessage = messages.findLast((m) => m.role === "assistant");
  const hasCitations = (lastAssistantMessage?.citations?.length ?? 0) > 0;

  return (
    <div className={cn("flex h-full flex-col bg-background", className)}>
      {/* Top Search Area - Minimal & Clean */}
      <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-xl border-b border-border/40">
        <div className="mx-auto max-w-3xl p-3 py-4 md:p-4 md:py-5">
          <div className="flex items-center gap-2">
            {mobileMenuButton}
            <ChatInput
              onSend={onSendMessage}
              onCancel={onCancelRequest}
              isLoading={isLoading}
              placeholder={t("searchPlaceholder")}
              className="flex-1"
            />
            {onOpenHistory && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onOpenHistory}
                className="h-9 w-9 shrink-0 text-muted-foreground hover:text-foreground"
                title="Cronologia"
              >
                <History className="h-4 w-4" />
              </Button>
            )}
          </div>
          <p className="mt-1.5 px-1 text-[10px] leading-tight text-muted-foreground/60">
            {t("researchNote")}{" "}
            <a
              href="/privacy"
              className="underline underline-offset-2 hover:text-muted-foreground transition-colors"
            >
              Privacy
            </a>
          </p>
        </div>
      </div>

      {/* Main Content Area */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        {/* Sticky banner for baseline generation (stays at top while scrolling) */}
        {isLoading && <ProgressBanner progress={progress} />}

        {/* Full-page progress view: shown during pre-streaming steps (1-6) */}
        {isLoading && progress && !progress.isComplete && !progress.stepResults?.some(r => r.step === 7) ? (
          <div className="mx-auto w-full max-w-5xl">
            <ProgressFullPage
              progress={progress}
              query={messages.length > 0 ? messages[messages.length - 1]?.content || messages[messages.length - 2]?.content : undefined}
            />
          </div>
        ) : (
          <div className="mx-auto max-w-3xl px-4 pb-12 overflow-x-hidden">
            <TranslationBanner hasCitations={hasCitations} />
            {!hasMessages ? (
              <WelcomeScreen onSendMessage={onSendMessage} />
            ) : (
              <div className="space-y-0 min-h-[50vh]">
                {messages.map((message, idx) => {
                  // For user messages, pass chatId and progress slot
                  const nextMsg = messages[idx + 1];
                  const chatId = message.role === "user" && nextMsg?.chatId ? nextMsg.chatId : undefined;
                  const isLastUserMsg = message.role === "user" && (idx === messages.length - 1 || idx === messages.length - 2);

                  // Show progress stepper below the last user message (only when streaming text or completed)
                  let progressSlot: React.ReactNode = null;
                  if (isLastUserMsg) {
                    if (isLoading && progress && progress.stepResults?.some(r => r.step === 7)) {
                      progressSlot = (
                        <div className="pt-4">
                          <ProgressIndicator progress={progress} />
                        </div>
                      );
                    } else if (!isLoading && lastCompletedProgress) {
                      progressSlot = (
                        <div className="pt-4">
                          <CompletedProgressStepper progress={lastCompletedProgress} />
                        </div>
                      );
                    }
                  }

                  return (
                    <MessageBubble key={message.id} message={message} chatId={chatId} progressSlot={progressSlot} />
                  );
                })}

                <div ref={messagesEndRef} className="h-4" />
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

interface WelcomeScreenProps {
  onSendMessage: (message: string) => void;
}

function WelcomeScreen({ onSendMessage }: WelcomeScreenProps) {
  // Latest subjects actually on the floor (EuroVoc of recent acts), served in
  // the UI language and cached per locale so the section doesn't pop in on
  // every visit
  const locale = useLocale();
  const [recentTopics, setRecentTopics] = useState<string[]>([]);
  useEffect(() => {
    const cacheKey = `recentTopics:${locale}`;
    try {
      const cached = sessionStorage.getItem(cacheKey);
      setRecentTopics(cached ? JSON.parse(cached) : []);
    } catch {}
    fetch(`/api/config/recent-topics?lang=${encodeURIComponent(locale)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (Array.isArray(data?.topics) && data.topics.length > 0) {
          sessionStorage.setItem(cacheKey, JSON.stringify(data.topics));
          setRecentTopics(data.topics);
        }
      })
      .catch(() => {});
  }, [locale]);

  const t = useTranslations("WelcomeScreen");
  return (
    <div className="flex flex-col items-center justify-center pt-10 sm:pt-16 pb-12 text-center px-4">

      {/* Hero */}
      <div className="mb-8 sm:mb-10 max-w-lg space-y-3">
        <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
          <Landmark className="w-3.5 h-3.5" />
          {t("badge")}
        </div>
        <h1 className="[font-family:var(--font-display)] text-3xl sm:text-4xl md:text-[2.75rem] font-medium tracking-tight text-foreground leading-[1.1]">
          {t("title")}
        </h1>
        <p className="text-muted-foreground text-sm sm:text-base leading-relaxed max-w-md mx-auto">
          {t.rich("subtitle", {
            bold: (chunks) => <span className="text-foreground font-medium">{chunks}</span>,
          })}
        </p>
      </div>

      {/* Topics: latest subjects from the live KG (left) and the curated
          legislature list (right). Two visual languages on purpose — chips
          for live data, underlined links for the curated picks. */}
      {recentTopics.length > 0 ? (
        <div className="w-full max-w-3xl grid sm:grid-cols-2 gap-y-10 sm:gap-x-10 text-left">
          <section>
            <p className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
              <span className="relative flex h-1.5 w-1.5" aria-hidden>
                <span className="absolute inline-flex h-full w-full rounded-full bg-primary/60 motion-safe:animate-ping" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
              </span>
              {t("lastTopics")}
            </p>
            <div className="flex flex-wrap gap-2">
              {recentTopics.map((topic) => (
                <TopicChip key={topic} topic={topic} onClick={onSendMessage} />
              ))}
            </div>
          </section>
          <section className="sm:border-l sm:border-border sm:pl-10">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
              {t("trendingTopics")}
            </p>
            <div className="flex flex-wrap gap-x-6 gap-y-3">
              {TOPICS.map((topic) => (
                <TopicPill key={topic} topic={topic} onClick={onSendMessage} />
              ))}
            </div>
          </section>
        </div>
      ) : (
        <div className="w-full max-w-2xl">
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
            {t("trendingTopics")}
          </p>
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-3">
            {TOPICS.map((topic) => (
              <TopicPill key={topic} topic={topic} onClick={onSendMessage} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface TopicPillProps {
  topic: string;
  onClick: (message: string) => void;
}

function TopicPill({ topic, onClick }: TopicPillProps) {
  const t = useTranslations("WelcomeScreen");
  const displayName = t(`topics.${topic}` as never) as string;
  // Use the localized topic name in the query too (EN → "healthcare reform", not "riforma sanitaria")
  const query = t("topicQuery", { topic: displayName });
  return (
    <button
      className="group inline-flex items-center gap-1.5 border-b border-border pb-1 text-sm text-foreground/80 transition-colors duration-200 hover:border-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"
      onClick={() => onClick(query)}
    >
      <span className="capitalize">{displayName}</span>
      <ArrowRight className="w-3 h-3 text-muted-foreground/40 transition-colors duration-200 group-hover:text-foreground" />
    </button>
  );
}

/** Chip for KG-derived topics: EuroVoc labels are lowercase Italian, so only
 *  the first letter is capitalized ("Protezione dell'ambiente", not
 *  "Protezione Dell'Ambiente"). */
function TopicChip({ topic, onClick }: TopicPillProps) {
  const t = useTranslations("WelcomeScreen");
  const displayName = topic.charAt(0).toUpperCase() + topic.slice(1);
  const query = t("topicQuery", { topic });
  return (
    <button
      className="inline-flex items-center rounded-full border border-border bg-muted/40 px-3 py-1.5 text-[13px] text-foreground/80 transition-colors duration-200 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer"
      onClick={() => onClick(query)}
    >
      {displayName}
    </button>
  );
}
