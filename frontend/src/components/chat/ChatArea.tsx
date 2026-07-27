"use client";

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { ProgressIndicator, ProgressBanner, CompletedProgressStepper, ProgressFullPage } from "@/components/shared/ProgressIndicator";
import { TranslationBanner } from "@/components/shared/TranslationBanner";
import type { Message, ProcessingProgress } from "@/types";
import { Landmark, ArrowRight, HelpCircle, History, Loader2 } from "lucide-react";
import { TOPICS } from "@/lib/constants";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

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

interface RecentTopics {
  topics: { label: string; query: string }[];
  since: string | null;
  acts: { title: string; date: string; topic?: string | null }[];
}

function formatDate(iso: string | null, locale: string): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function WelcomeScreen({ onSendMessage }: WelcomeScreenProps) {
  // Latest subjects actually on the floor (EuroVoc of recent acts), served in
  // the UI language and cached per locale so the section doesn't pop in on
  // every visit
  const locale = useLocale();
  // null = loading (server HTML and pre-fetch: skeleton chips), [] = resolved
  // empty (collapse to trending only), non-empty = real chips. The layout is
  // two columns in every state except resolved-empty, so a reload never
  // reflows: the server paints the same geometry the client settles on.
  const [recent, setRecent] = useState<RecentTopics | null>(null);
  // Cache seeded pre-paint; not in the useState initializer to avoid an SSR
  // hydration mismatch (same pattern as the Sidebar footer date).
  useLayoutEffect(() => {
    try {
      const cached = sessionStorage.getItem(`recentTopics3:${locale}`);
      if (cached) setRecent(JSON.parse(cached));
    } catch {}
  }, [locale]);
  useEffect(() => {
    const cacheKey = `recentTopics3:${locale}`;
    fetch(`/api/config/recent-topics?lang=${encodeURIComponent(locale)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (Array.isArray(data?.topics) && data.topics.length > 0) {
          sessionStorage.setItem(cacheKey, JSON.stringify(data));
          setRecent(data);
        } else {
          setRecent((prev) => prev ?? { topics: [], since: null, acts: [] });
        }
      })
      .catch(() => setRecent((prev) => prev ?? { topics: [], since: null, acts: [] }));
  }, [locale]);

  const t = useTranslations("WelcomeScreen");
  // Mobile shows one topic list at a time (the stacked sections make the
  // page two screens long); desktop keeps the two-column grid untouched.
  const [mobileTab, setMobileTab] = useState<"recent" | "trending">("recent");
  return (
    <div className="flex flex-col items-center justify-center pt-4 sm:pt-16 pb-2 sm:pb-12 text-center px-4">

      {/* Hero — tight on phones: with the search bar and the bottom nav the
          content zone is ~600px and the page must not scroll when idle */}
      <div className="mb-5 sm:mb-10 max-w-lg space-y-2.5 sm:space-y-3">
        <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground sm:mb-2">
          <Landmark className="w-3.5 h-3.5" />
          {t("badge")}
        </div>
        <h1 className="[font-family:var(--font-display)] text-[1.7rem] sm:text-4xl md:text-[2.75rem] font-medium tracking-tight text-foreground leading-[1.1]">
          {t("title")}
        </h1>
        <p className="text-muted-foreground text-sm sm:text-base leading-relaxed max-w-md mx-auto line-clamp-2 sm:line-clamp-none">
          {t.rich("subtitle", {
            bold: (chunks) => <span className="text-foreground font-medium">{chunks}</span>,
          })}
        </p>
      </div>

      {/* Topics: latest subjects from the live KG (left, skeleton while
          loading) and the curated legislature list (right). Same chip
          affordance for both — the source difference lives in the headers.
          The layout collapses to a single centered list only when the
          endpoint resolves with no data. */}
      {recent === null || recent.topics.length > 0 ? (
        <>
          <div className="mb-4 flex w-full max-w-3xl gap-1.5 sm:hidden">
            {(
              [
                ["recent", t("lastTopicsTab")],
                ["trending", t("trendingTab")],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setMobileTab(key)}
                className={cn(
                  "flex-1 rounded-lg border px-2 py-2 text-[13px] transition-colors",
                  mobileTab === key
                    ? "border-primary/40 bg-primary/5 text-primary font-medium"
                    : "border-border text-muted-foreground"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="w-full max-w-3xl grid sm:grid-cols-2 gap-y-10 sm:gap-x-10 text-left">
          <section className={cn(mobileTab !== "recent" && "hidden sm:block")}>
            <p className="hidden sm:flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
              {t("lastTopics")}
              {recent !== null && recent.acts.length > 0 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      className="text-muted-foreground/60 hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-full"
                      aria-label={t("lastTopicsHint", { date: recent.since ?? "" })}
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="bottom"
                    align="start"
                    className="max-w-sm p-3.5 text-left normal-case tracking-normal"
                  >
                    <p className="text-[11px] leading-snug opacity-75 mb-2.5">
                      {t("lastTopicsHint", { date: formatDate(recent.since, locale) })}
                    </p>
                    <p className="text-[11px] font-semibold mb-2">{t("lastTopicsHintActs")}</p>
                    <ul className="space-y-3">
                      {recent.acts.map((act) => (
                        <li key={act.title} className="leading-snug">
                          <span className="flex items-baseline justify-between gap-3 mb-0.5">
                            <span className="text-xs font-semibold">
                              {act.topic
                                ? act.topic.charAt(0).toUpperCase() + act.topic.slice(1)
                                : formatDate(act.date, locale)}
                            </span>
                            {act.topic && (
                              <span className="shrink-0 text-[10px] tabular-nums opacity-60">
                                {formatDate(act.date, locale)}
                              </span>
                            )}
                          </span>
                          <span className="line-clamp-2 text-[11px] opacity-70">{act.title}</span>
                        </li>
                      ))}
                    </ul>
                  </TooltipContent>
                </Tooltip>
              )}
            </p>
            {recent === null && (
              <p className="flex items-center gap-1.5 mb-3 text-[11px] italic text-muted-foreground/70">
                <Loader2 className="w-3 h-3 motion-safe:animate-spin" aria-hidden />
                {t("lastTopicsLoading")}
              </p>
            )}
            <div className="flex flex-wrap gap-x-6 gap-y-3">
              {recent === null
                ? ["w-28", "w-16", "w-32", "w-24", "w-36", "w-24"].map((w, i) => (
                    <span
                      key={i}
                      className={cn(
                        "h-4 mb-1 rounded-sm bg-muted/60 motion-safe:animate-pulse",
                        w,
                        // the sixth row would push the list past the fold on phones
                        i >= 5 && "hidden sm:block"
                      )}
                    />
                  ))
                : recent.topics.map((topic, i) => (
                    <TopicPill
                      key={topic.label}
                      topic={topic.label}
                      queryText={topic.query}
                      raw
                      onClick={onSendMessage}
                      className={i >= 5 ? "hidden sm:inline-flex" : undefined}
                    />
                  ))}
            </div>
          </section>
          <section
            className={cn(
              "sm:border-l sm:border-border sm:pl-10",
              mobileTab !== "trending" && "hidden sm:block"
            )}
          >
            <p className="hidden sm:block text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-4">
              {t("trendingTopics")}
            </p>
            <div className="flex flex-wrap gap-x-6 gap-y-3">
              {TOPICS.map((topic) => (
                <TopicPill key={topic} topic={topic} onClick={onSendMessage} />
              ))}
            </div>
          </section>
          </div>
        </>
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
  /** KG-derived topics arrive already localized and have no i18n key */
  raw?: boolean;
  /** Expanded phrase sent as the query (chip shows the short label, the
   *  query carries the act's context — "digital signatures" alone would
   *  lose the electoral meaning) */
  queryText?: string;
  className?: string;
}

/** Sentence case, not Title Case: EuroVoc and curated labels are lowercase
 *  phrases with embedded proper nouns ("conflitto in Ucraina"), so only the
 *  first letter is raised. */
function TopicPill({ topic, onClick, raw = false, queryText, className }: TopicPillProps) {
  const t = useTranslations("WelcomeScreen");
  const label = raw ? topic : (t(`topics.${topic}` as never) as string);
  const displayName = label.charAt(0).toUpperCase() + label.slice(1);
  // The localized label (or the expanded phrase) goes into the query
  const query = t("topicQuery", { topic: queryText ?? label });
  return (
    <button
      className={cn(
        "group inline-flex items-center gap-1.5 border-b border-border pb-1 text-sm text-left text-foreground/80 transition-colors duration-200 hover:border-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 cursor-pointer",
        className
      )}
      onClick={() => onClick(query)}
    >
      <span>{displayName}</span>
      <ArrowRight className="w-3 h-3 text-muted-foreground/40 transition-colors duration-200 group-hover:text-foreground" />
    </button>
  );
}
