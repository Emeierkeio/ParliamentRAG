"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { CitationCard } from "./CitationCard";
import { ExpertCard, ExpertRow } from "./ExpertCard";
import { CompassCard } from "./CompassCard";
import type { Message } from "@/types";
import { config } from "@/config";
import {
  User,
  Bot,
  ChevronDown,
  ChevronUp,
  Quote,
  Users,
  PieChart,
  Loader2,
  AlertCircle,
  Compass,
  Sparkles,
  Trophy,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface MessageBubbleProps {
  message: Message;
  className?: string;
}

export function MessageBubble({ message, className }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const isError = message.status === "error";
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);

  if (isUser) {
    return (
      <div className={cn("py-6 border-b border-border/50", className)}>
        <h2 className="text-2xl font-semibold text-foreground mb-2">
          {message.content}
        </h2>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <User className="h-3 w-3" />
          <span>Tu</span>
          <span>•</span>
          <span>
            {message.timestamp.toLocaleTimeString("it-IT", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("py-6", className)}>
      <div className="flex flex-col gap-4">
        {/* Error State */}
        {isError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <div className="flex items-center gap-2 text-destructive mb-2">
              <AlertCircle className="h-4 w-4" />
              <span className="font-medium">
                Errore nella generazione della risposta
              </span>
            </div>
            {message.content && (
              <p className="text-sm text-destructive/90">{message.content}</p>
            )}
          </div>
        )}

        {/* Loading/Streaming State */}
        {isStreaming && !message.content && (
          <div className="flex items-center gap-2 text-muted-foreground py-4">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm font-medium">
              Generazione della risposta in corso...
            </span>
          </div>
        )}

        {/* Content */}
        {message.content && (
          <div className="prose prose-sm max-w-none prose-neutral dark:prose-invert">
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-4 leading-relaxed last:mb-0">{children}</p>
                ),
                ul: ({ children }) => (
                  <ul className="mb-4 ml-4 list-disc space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="mb-4 ml-4 list-decimal space-y-1">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li className="">{children}</li>,
                strong: ({ children }) => (
                  <strong className="font-semibold text-foreground">
                    {children}
                  </strong>
                ),
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold mb-4 mt-6">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-bold mb-3 mt-5">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-bold mb-2 mt-4">{children}</h3>
                ),
                code: ({ children }) => (
                  <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-sm">
                    {children}
                  </code>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-primary/20 pl-4 py-1 italic text-muted-foreground my-4">
                    {children}
                  </blockquote>
                ),
                a: ({ href, children }) => {
                  // Check if it's a citation link (evidence_id patterns)
                  const isCitationLink = href && (
                    href.includes("chunk_") ||
                    href.startsWith("cit_") ||
                    href.startsWith("leg19_") ||
                    href.startsWith("leg18_")
                  );

                  if (isCitationLink) {
                    return (
                      <span
                        className={cn(
                          "inline cursor-pointer rounded px-1 py-0.5",
                          "bg-primary/5 text-primary/90 hover:bg-primary/15",
                          "border-b-2 border-primary/40 hover:border-primary/60",
                          "transition-all duration-150",
                          highlightedChunkId === href && "bg-yellow-400/30 border-yellow-500 text-yellow-800 dark:text-yellow-300"
                        )}
                        onClick={() => setHighlightedChunkId(href)}
                        title="Clicca per evidenziare la fonte"
                      >
                        {children}
                      </span>
                    );
                  }

                  return (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary underline underline-offset-2"
                    >
                      {children}
                    </a>
                  );
                }
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {isStreaming && message.content && (
          <div className="flex items-center gap-2 mt-2">
            <span className="inline-block w-2 h-4 bg-primary animate-pulse" />
          </div>
        )}

        {/* Additional metadata for assistant messages */}
        {!isUser && message.status === "complete" && (
          <div className="mt-6 border-t border-border pt-6">
            <AssistantMetadata
              message={message}
              highlightedChunkId={highlightedChunkId}
            />
          </div>
        )}
      </div>
    </div>
  );
}

interface AssistantMetadataProps {
  message: Message;
  highlightedChunkId?: string | null;
}

function AssistantMetadata({ message, highlightedChunkId }: AssistantMetadataProps) {
  const hasCitations = message.citations && message.citations.length > 0;
  const hasExperts = message.experts && message.experts.length > 0;
  const hasBalance = message.balanceMetrics;
  const hasHQMetaData = !!message.hqMetadata;

  if (!hasCitations && !hasExperts && !hasBalance && !hasHQMetaData) return null;

  return (
    <div className="flex flex-col gap-2 w-full min-w-0">
      {/* High Quality Variants Analysis */}
      {hasHQMetaData && (
        <CollapsibleSection
          icon={Sparkles}
          title="Analisi High Quality (Best-of-N)"
          count={message.hqMetadata!.variants.length}
          defaultOpen={false}
        >
          <div className="pt-2 px-1">
            <div className="bg-primary/5 border border-primary/10 rounded-lg p-4 mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Trophy className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold">Motivazione della scelta</span>
              </div>
              <p className="text-xs text-muted-foreground italic leading-relaxed">
                "{message.hqMetadata!.judge_reason}"
              </p>
            </div>

            <Tabs defaultValue="winner" className="w-full">
              <TabsList className="grid w-full grid-cols-3 h-9">
                <TabsTrigger value="winner" className="text-xs">🏆 Vincitore</TabsTrigger>
                <TabsTrigger value="var0" className="text-xs">Variante A</TabsTrigger>
                <TabsTrigger value="var1" className="text-xs">Variante B</TabsTrigger>
              </TabsList>
              
              {(() => {
                const winner = message.hqMetadata!.variants.find(v => v.is_best);
                const others = message.hqMetadata!.variants.filter(v => !v.is_best);
                
                return (
                  <>
                    <TabsContent value="winner" className="mt-4">
                      {winner && <VariantCard variant={winner} />}
                    </TabsContent>
                    <TabsContent value="var0" className="mt-4">
                      {others[0] && <VariantCard variant={others[0]} />}
                    </TabsContent>
                    <TabsContent value="var1" className="mt-4">
                      {others[1] && <VariantCard variant={others[1]} />}
                    </TabsContent>
                  </>
                );
              })()}
            </Tabs>
          </div>
        </CollapsibleSection>
      )}

      {/* Balance metrics */}
      {hasBalance && <BalanceSection metrics={message.balanceMetrics!} />}

      {/* Experts */}
      {hasExperts && (
        <CollapsibleSection
          icon={Users}
          title="Esperti"
          count={message.experts!.length}
        >
            {message.experts && (
               <div className="space-y-6 pt-2">
                 {(() => {
                    const groupedExperts = message.experts!.reduce((acc, expert) => {
                         if (!acc[expert.gruppo]) acc[expert.gruppo] = [];
                         acc[expert.gruppo].push(expert);
                         return acc;
                    }, {} as Record<string, typeof message.experts>);

                    return Object.entries(groupedExperts).map(([group, experts]) => (
                        <div key={group}>
                             <div className="flex items-center gap-3 mb-3 px-1">
                                <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-widest whitespace-nowrap">{group}</span>
                                <div className="h-px flex-1 bg-border/40"></div>
                             </div>
                             <div className="grid gap-2 w-full">
                                 {experts!.map(expert => (
                                     <ExpertRow key={expert.id} expert={expert} />
                                 ))}
                             </div>
                        </div>
                    ));
                 })()}
               </div>
            )}
        </CollapsibleSection>
      )}

      {/* Compass */}
      {message.compass && (
        <CollapsibleSection
            icon={Compass}
            title="Bussola Ideologica"
            count={1} // Just 1 complex visualization
            defaultOpen={true}
        >
             <CompassCard data={message.compass} />
        </CollapsibleSection>
      )}

      {/* Citations */}
      {hasCitations && (
        <CollapsibleSection
          icon={Quote}
          title="Citazioni"
          count={message.citations!.length}
          defaultOpen={true}
          forceOpen={!!highlightedChunkId}
        >
          <div className="grid gap-2 w-full min-w-0">
            {/* Deduplicate citations by chunk_id to prevent key errors */}
            {Array.from(new Map(message.citations!.map(c => [c.chunk_id, c])).values()).map((citation, index) => (
              <CitationCard
                key={citation.chunk_id}
                citation={citation}
                index={index}
                isHighlighted={highlightedChunkId === citation.chunk_id}
              />
            ))}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}

interface CollapsibleSectionProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  count: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
  forceOpen?: boolean;
}

function CollapsibleSection({
  icon: Icon,
  title,
  count,
  defaultOpen = false,
  children,
  forceOpen = false,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  useEffect(() => {
    if (forceOpen) {
      setIsOpen(true);
    }
  }, [forceOpen]);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          className="w-full justify-between h-auto py-2 px-3 hover:bg-muted/50"
        >
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{title}</span>
            <Badge variant="secondary" className="text-xs">
              {count}
            </Badge>
          </div>
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2 pb-2 px-2 w-full">{children}</CollapsibleContent>
    </Collapsible>
  );
}

interface BalanceSectionProps {
  metrics: NonNullable<Message["balanceMetrics"]>;
}

function BalanceSection({ metrics }: BalanceSectionProps) {
  const [isOpen, setIsOpen] = useState(false);

  // biasScore: -1 = tutto opposizione, 0 = bilanciato, 1 = tutto maggioranza
  const balancePercentage = Math.round((1 - Math.abs(metrics.biasScore)) * 100);
  const isBalanced = balancePercentage >= 60;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          className="w-full justify-between h-auto py-2 px-3 hover:bg-muted/50"
        >
          <div className="flex items-center gap-2">
            <PieChart className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">Bilanciamento</span>
            <Badge
              variant={isBalanced ? "default" : "secondary"}
              className={cn(
                "text-xs",
                isBalanced && "bg-green-500/20 text-green-400",
              )}
            >
              {balancePercentage}%
            </Badge>
          </div>
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2 px-3">
        <div className="rounded-lg border border-border bg-card/50 p-3 space-y-3">
          <div className="space-y-2">
            {/* Maggioranza */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-blue-400">Maggioranza</span>
                <span className="text-muted-foreground">
                  {Math.round(metrics.maggioranzaPercentage)}%
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full transition-all bg-blue-500"
                  style={{ width: `${metrics.maggioranzaPercentage}%` }}
                />
              </div>
            </div>

            {/* Opposizione */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-red-400">Opposizione</span>
                <span className="text-muted-foreground">
                  {Math.round(metrics.opposizionePercentage)}%
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-muted">
                <div
                  className="h-full rounded-full transition-all bg-red-500"
                  style={{ width: `${metrics.opposizionePercentage}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function VariantCard({ variant }: { variant: any }) {
  return (
    <div className="relative group">
      <div className="absolute top-2 right-2 flex items-center gap-2 z-10">
        <Badge variant="outline" className="text-[10px] bg-background/80 backdrop-blur-sm border-primary/20">
          Score: {variant.score}/10
        </Badge>
        <Badge variant="outline" className="text-[10px] bg-background/80 backdrop-blur-sm border-border/50">
          Temp: {variant.temperature}
        </Badge>
      </div>
      <div className="text-[11px] text-muted-foreground bg-muted/20 border border-border/40 rounded-lg p-4 pt-10 overflow-y-auto max-h-[350px] whitespace-pre-wrap leading-relaxed custom-scrollbar">
        {variant.text}
      </div>
    </div>
  );
}
