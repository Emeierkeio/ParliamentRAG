"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { ProgressIndicator } from "@/components/shared/ProgressIndicator";
import { config } from "@/config";
import type { Message, ProcessingProgress } from "@/types";
import { Landmark, MessageSquare, ExternalLink } from "lucide-react";

interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  progress: ProcessingProgress | null;
  onSendMessage: (message: string) => void;
  onCancelRequest: () => void;
  className?: string;
}

export function ChatArea({
  messages,
  isLoading,
  progress,
  onSendMessage,
  onCancelRequest,
  className,
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
        <div className="mx-auto max-w-3xl p-4 py-5">
          <ChatInput
            onSend={onSendMessage}
            onCancel={onCancelRequest}
            isLoading={isLoading}
            placeholder="Fai una domanda..."
            className="w-full"
          />
        </div>
      </div>

      {/* Main Content Area */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="mx-auto max-w-3xl px-4 pb-12">
          {!hasMessages ? (
            <WelcomeScreen onSendMessage={onSendMessage} />
          ) : (
            <div className="space-y-0 min-h-[50vh]">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}

              {/* Progress indicator during processing */}
              {isLoading && progress && (
                <div className="py-6 border-t border-border/50">
                  <ProgressIndicator progress={progress} />
                </div>
              )}

              <div ref={messagesEndRef} className="h-4" />
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

interface WelcomeScreenProps {
  onSendMessage: (message: string) => void;
}

function WelcomeScreen({ onSendMessage }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center pt-10 pb-12 text-center fade-in slide-in-from-bottom-5 duration-700">
      
      {/* Minimal Hero */}
      <div className="space-y-4 mb-8 max-w-2xl">
        <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Analisi Parlamentare AI
        </h1>
        <p className="text-lg text-muted-foreground leading-relaxed max-w-lg mx-auto">
          Esplora i dibattiti, confronta le posizioni e analizza i dati ufficiali della Camera dei Deputati con l'intelligenza artificiale.
        </p>
      </div>

      {/* Modern Suggestion grid/pills */}
      <div className="w-full max-w-full">
        <div className="flex items-center justify-center gap-2 mb-6 text-xs font-medium uppercase tracking-widest text-muted-foreground/70">
          <MessageSquare className="w-3 h-3" />
          <span>Temi Suggeriti</span>
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            <SuggestionCard topic="PNRR" onClick={onSendMessage} />
            <SuggestionCard topic="riforma del sistema sanitario" onClick={onSendMessage} />
            <SuggestionCard topic="transizione energetica" onClick={onSendMessage} />
            <SuggestionCard topic="salario minimo" onClick={onSendMessage} />
            <SuggestionCard topic="conflitto in Ucraina" onClick={onSendMessage} />
            <SuggestionCard topic="riforma fiscale" onClick={onSendMessage} />
            <SuggestionCard topic="autonomia differenziata" onClick={onSendMessage} />
            <SuggestionCard topic="riforma della giustizia" onClick={onSendMessage} />
            <SuggestionCard topic="gestione dei flussi migratori" onClick={onSendMessage} />
            <SuggestionCard topic="scuola e istruzione" onClick={onSendMessage} />
            <SuggestionCard topic="cambiamento climatico" onClick={onSendMessage} />
            <SuggestionCard topic="infrastrutture" onClick={onSendMessage} />
        </div>
      </div>
    </div>
  );
}

interface SuggestionCardProps {
  topic: string;
  onClick: (message: string) => void;
}

function SuggestionCard({ topic, onClick }: SuggestionCardProps) {
  const query = `Qual è la posizione dei gruppi parlamentari sul tema: ${topic}?`;
  return (
    <button
      className="group relative overflow-hidden rounded-xl border border-border bg-card p-4 text-left transition-all duration-300 hover:border-primary/50 hover:shadow-md active:scale-[0.98]"
      onClick={() => onClick(query)}
    >
      <div className="relative z-10 flex items-center gap-2">
        <span className="font-semibold text-foreground text-sm capitalize">
            {topic}
        </span>
        <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-50 transition-opacity -translate-y-0.5 translate-x-0.5" />
      </div>
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
    </button>
  );
}
