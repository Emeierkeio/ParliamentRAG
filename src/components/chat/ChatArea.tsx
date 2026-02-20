"use client";

import React, { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { ProgressIndicator, ProgressBanner, CompletedProgressStepper, ProgressFullPage } from "@/components/shared/ProgressIndicator";
import type { Message, ProcessingProgress } from "@/types";
import { Atom, ArrowRight, History } from "lucide-react";

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
              placeholder="Cerca un tema..."
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
  return (
    <div className="flex flex-col items-center justify-center pt-8 sm:pt-16 pb-12 text-center px-2">

      {/* Action-oriented Hero */}
      <div className="mb-6 sm:mb-10 max-w-xl space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full bg-primary/8 px-4 py-1.5 text-xs font-medium text-primary mb-2">
          <Atom className="w-3.5 h-3.5" />
          Camera dei Deputati - XIX Legislatura
        </div>
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight text-foreground leading-tight">
          Cerca un tema e scopri cosa ne pensano i gruppi parlamentari
        </h1>
        <p className="text-muted-foreground text-sm sm:text-base leading-relaxed">
          Scrivi un tema nella barra in alto oppure scegli uno dei temi qui sotto.
        </p>
      </div>

      {/* Topic pills */}
      <div className="w-full max-w-2xl">
        <p className="text-[11px] font-medium uppercase tracking-[0.15em] text-muted-foreground/60 mb-4">
          Temi di tendenza
        </p>

        <div className="flex flex-wrap justify-center gap-2">
          <TopicPill topic="PNRR" onClick={onSendMessage} />
          <TopicPill topic="riforma sanitaria" onClick={onSendMessage} />
          <TopicPill topic="transizione energetica" onClick={onSendMessage} />
          <TopicPill topic="salario minimo" onClick={onSendMessage} />
          <TopicPill topic="conflitto in Ucraina" onClick={onSendMessage} />
          <TopicPill topic="riforma fiscale" onClick={onSendMessage} />
          <TopicPill topic="autonomia differenziata" onClick={onSendMessage} />
          <TopicPill topic="riforma della giustizia" onClick={onSendMessage} />
          <TopicPill topic="flussi migratori" onClick={onSendMessage} />
          <TopicPill topic="scuola e istruzione" onClick={onSendMessage} />
          <TopicPill topic="cambiamento climatico" onClick={onSendMessage} />
          <TopicPill topic="infrastrutture" onClick={onSendMessage} />
        </div>
      </div>
    </div>
  );
}

interface TopicPillProps {
  topic: string;
  onClick: (message: string) => void;
}

function TopicPill({ topic, onClick }: TopicPillProps) {
  const query = `Qual è la posizione dei gruppi parlamentari sul tema: ${topic}?`;
  return (
    <button
      className="group inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-card px-4 py-2 text-sm text-foreground transition-all duration-200 hover:border-primary/40 hover:bg-primary/5 hover:shadow-sm active:scale-[0.97]"
      onClick={() => onClick(query)}
    >
      <span className="capitalize">{topic}</span>
      <ArrowRight className="w-3 h-3 text-muted-foreground/40 transition-all duration-200 group-hover:text-primary group-hover:translate-x-0.5" />
    </button>
  );
}
