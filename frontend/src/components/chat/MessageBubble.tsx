"use client";

import React, { useState, useEffect, Children, isValidElement, cloneElement } from "react";
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
import { TopicStatsModal } from "./TopicStatsModal";
import type { Message, TopicStatistics } from "@/types";
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
  Info,
  Landmark,
  Share2,
  Check as CheckIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SpeakerInfo {
  name: string;
  group: string;
  role?: string;
}

/**
 * Parse markdown content to extract bold names (**Name**) grouped by section (## heading),
 * and resolve their parliamentary group from experts/citations data.
 * For government members, resolves institutional role instead of party.
 */
function extractSpeakersBySection(
  content: string,
  experts?: import("@/types").Expert[],
  citations?: import("@/types").Citation[],
): Record<string, SpeakerInfo[]> {
  // Build a name → group lookup from experts and citations
  const nameToGroup: Record<string, string> = {};
  const nameToRole: Record<string, string> = {};
  if (experts) {
    for (const e of experts) {
      const fullName = `${e.first_name} ${e.last_name}`;
      nameToGroup[fullName] = e.group;
      if (e.institutional_role) nameToRole[fullName] = e.institutional_role;
    }
  }
  if (citations) {
    for (const c of citations) {
      const fullName = `${c.deputy_first_name} ${c.deputy_last_name}`;
      if (!nameToGroup[fullName]) {
        nameToGroup[fullName] = c.group;
      }
      if (c.institutional_role && !nameToRole[fullName]) {
        nameToRole[fullName] = c.institutional_role;
      }
    }
  }

  const result: Record<string, SpeakerInfo[]> = {};
  let currentSection = "";

  for (const line of content.split("\n")) {
    const headingMatch = line.match(/^#{1,3}\s+(.+)/);
    if (headingMatch) {
      currentSection = headingMatch[1].trim();
      if (!result[currentSection]) result[currentSection] = [];
      continue;
    }
    if (currentSection) {
      const boldNames = line.match(/\*\*([A-Z\u00C0-\u024F][a-z\u00C0-\u024F]+(?:\s+[A-Z\u00C0-\u024F][a-z\u00C0-\u024F]+)+)\*\*/g);
      if (boldNames) {
        for (const match of boldNames) {
          const name = match.replace(/\*\*/g, "");
          if (!result[currentSection].some(s => s.name === name)) {
            result[currentSection].push({
              name,
              group: nameToGroup[name] || "",
              role: nameToRole[name],
            });
          }
        }
      }
    }
  }
  return result;
}

/** Tooltip showing speakers grouped by parliamentary group (or role for government members) */
function SpeakersTooltip({ speakers, iconSize }: { speakers: SpeakerInfo[]; iconSize: string }) {
  // Group speakers by their parliamentary group or institutional role for government members
  const grouped: Record<string, string[]> = {};
  for (const s of speakers) {
    const isGov = s.group?.toLowerCase() === "governo";
    const label = isGov && s.role ? s.role : (s.group || "Altro");
    if (!grouped[label]) grouped[label] = [];
    grouped[label].push(s.name);
  }
  const groups = Object.entries(grouped);

  return (
    <Tooltip delayDuration={0}>
      <TooltipTrigger asChild>
        <span className="inline-flex cursor-help">
          <Info className={cn(iconSize, "text-muted-foreground/60 hover:text-primary transition-colors")} />
        </span>
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-[350px]">
        <p className="font-semibold text-xs mb-1.5">Parlamentari in questa sezione</p>
        <div className="space-y-1.5">
          {groups.map(([group, names]) => (
            <div key={group}>
              <p className="text-[11px] font-semibold text-foreground">{group}</p>
              <p className="text-[11px] text-muted-foreground">{names.join(", ")}</p>
            </div>
          ))}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

/** Share button that copies the chat URL to clipboard */
function ShareButton({ chatId }: { chatId: string }) {
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    const url = `${window.location.origin}/chat/${chatId}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex justify-end mt-2">
      <button
        onClick={handleShare}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all",
          copied
            ? "text-green-600 bg-green-50 dark:bg-green-950/30"
            : "text-muted-foreground hover:text-primary hover:bg-muted/50"
        )}
      >
        {copied ? (
          <>
            <CheckIcon className="h-3 w-3" />
            <span>Link copiato</span>
          </>
        ) : (
          <>
            <Share2 className="h-3 w-3" />
            <span>Condividi</span>
          </>
        )}
      </button>
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
  className?: string;
}

export function MessageBubble({ message, className }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const isError = message.status === "error";
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);
  const [statsModalView, setStatsModalView] = useState<"interventions" | "speakers" | "sessions" | null>(null);

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
        <div className="flex items-center gap-1.5 mt-1 text-[10px] text-muted-foreground/60">
          <Landmark className="h-3 w-3" />
          <span className="font-medium">Camera dei Deputati — XIX Legislatura</span>
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
                  <p className="mb-4 leading-relaxed last:mb-0">
                    {message.topicStats
                      ? linkifyStats(children, message.topicStats, setStatsModalView)
                      : children}
                  </p>
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
                strong: ({ children }) => {
                  const text = typeof children === "string" ? children : String(children);
                  // Build name → URL lookup from citations and experts
                  const nameToUrl: Record<string, string> = {};
                  if (message.experts) {
                    for (const e of message.experts) {
                      const fullName = `${e.first_name} ${e.last_name}`;
                      if (e.camera_profile_url) nameToUrl[fullName] = e.camera_profile_url;
                    }
                  }
                  if (message.citations) {
                    for (const c of message.citations) {
                      const fullName = `${c.deputy_first_name} ${c.deputy_last_name}`;
                      if (c.camera_profile_url && !nameToUrl[fullName]) nameToUrl[fullName] = c.camera_profile_url;
                    }
                  }
                  const url = nameToUrl[text];
                  if (url) {
                    return (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-foreground hover:text-primary hover:underline underline-offset-2 transition-colors"
                      >
                        {children}
                      </a>
                    );
                  }
                  return (
                    <strong className="font-semibold text-foreground">
                      {children}
                    </strong>
                  );
                },
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold mb-4 mt-6">{children}</h1>
                ),
                h2: ({ children }) => {
                  const title = typeof children === "string" ? children : String(children);
                  const speakersBySection = extractSpeakersBySection(message.content, message.experts, message.citations);
                  const speakers = speakersBySection[title] || [];
                  return (
                    <h2 className="text-xl font-bold mb-3 mt-5 flex items-center gap-2">
                      <span>{children}</span>
                      {speakers.length > 0 && (
                        <SpeakersTooltip speakers={speakers} iconSize="h-4 w-4" />
                      )}
                    </h2>
                  );
                },
                h3: ({ children }) => {
                  const title = typeof children === "string" ? children : String(children);
                  const speakersBySection = extractSpeakersBySection(message.content, message.experts, message.citations);
                  const speakers = speakersBySection[title] || [];
                  return (
                    <h3 className="text-lg font-bold mb-2 mt-4 flex items-center gap-2">
                      <span>{children}</span>
                      {speakers.length > 0 && (
                        <SpeakersTooltip speakers={speakers} iconSize="h-3.5 w-3.5" />
                      )}
                    </h3>
                  );
                },
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
                        onClick={() => {
                          const availableIds = message.citations?.map(c => c.chunk_id) || [];
                          const matched = availableIds.includes(href!);
                          if (matched) {
                            const cit = message.citations?.find(c => c.chunk_id === href);
                            console.log(`[Pipeline:Citations] Click OK: ${href} → ${cit?.deputy_first_name} ${cit?.deputy_last_name} (${cit?.group})`);
                          } else {
                            console.warn(`[Pipeline:Citations] Click MISS: "${href}" not in sidebar (${availableIds.length} available)`, availableIds);
                          }
                          setHighlightedChunkId(href);
                        }}
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

        {/* Share button */}
        {!isUser && message.status === "complete" && message.chatId && (
          <ShareButton chatId={message.chatId} />
        )}

        {/* Additional metadata for assistant messages — show progressively once text is visible */}
        {!isUser && message.content && (message.status === "complete" || message.status === "streaming") && (
          <AssistantMetadata
            message={message}
            highlightedChunkId={highlightedChunkId}
          />
        )}
        {/* Topic Stats Modal */}
        {message.topicStats && statsModalView && (
          <TopicStatsModal
            stats={message.topicStats}
            isOpen={!!statsModalView}
            onClose={() => setStatsModalView(null)}
            defaultView={statsModalView}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Scans React children for text patterns matching introduction stats
 * (e.g. "81 interventi", "46 parlamentari", "N. 27, 49, 56")
 * and replaces them with clickable spans.
 */
function linkifyStats(
  children: React.ReactNode,
  stats: TopicStatistics,
  openModal: (view: "interventions" | "speakers" | "sessions") => void,
): React.ReactNode {
  return processChildren(children, (text: string) => {
    const parts: (string | React.ReactElement)[] = [];
    let remaining = text;
    let keyIdx = 0;

    // Pattern for "N interventi" / "N intervento"
    const interventionRe = /(\d+)\s+intervent[oi]/g;
    // Pattern for "N parlamentari"
    const speakerRe = /(\d+)\s+parlamentar[ie]/g;
    // Pattern for "N. 27, 49, 56 e 65" or "N. 27, 49, 56, 61 e 65"
    const sessionRe = /N\.\s*[\d]+(?:,\s*[\d]+)*(?:\s*e\s*[\d]+)?/g;

    // Collect all matches with positions
    type Match = { index: number; length: number; text: string; view: "interventions" | "speakers" | "sessions" };
    const matches: Match[] = [];

    let m: RegExpExecArray | null;
    interventionRe.lastIndex = 0;
    while ((m = interventionRe.exec(text)) !== null) {
      matches.push({ index: m.index, length: m[0].length, text: m[0], view: "interventions" });
    }
    speakerRe.lastIndex = 0;
    while ((m = speakerRe.exec(text)) !== null) {
      matches.push({ index: m.index, length: m[0].length, text: m[0], view: "speakers" });
    }
    sessionRe.lastIndex = 0;
    while ((m = sessionRe.exec(text)) !== null) {
      matches.push({ index: m.index, length: m[0].length, text: m[0], view: "sessions" });
    }

    if (matches.length === 0) return text;

    // Sort by position
    matches.sort((a, b) => a.index - b.index);

    let cursor = 0;
    for (const match of matches) {
      // Skip overlapping matches
      if (match.index < cursor) continue;

      if (match.index > cursor) {
        parts.push(remaining.slice(cursor, match.index));
      }
      parts.push(
        <span
          key={`stat-${keyIdx++}`}
          className="cursor-pointer text-primary font-semibold border-b border-primary/40 hover:border-primary hover:bg-primary/5 transition-all duration-150 rounded-sm px-0.5 -mx-0.5"
          onClick={() => openModal(match.view)}
          title="Clicca per vedere il dettaglio"
        >
          {match.text}
        </span>
      );
      cursor = match.index + match.length;
    }
    if (cursor < remaining.length) {
      parts.push(remaining.slice(cursor));
    }

    return parts.length === 1 ? parts[0] : parts;
  });
}

/**
 * Recursively process React children, applying a transform function to text nodes.
 */
function processChildren(
  children: React.ReactNode,
  transformText: (text: string) => React.ReactNode,
): React.ReactNode {
  return Children.map(children, (child: React.ReactNode) => {
    if (typeof child === "string") {
      return transformText(child);
    }
    if (isValidElement(child)) {
      const props = child.props as Record<string, unknown>;
      if (props.children) {
        return cloneElement(child as React.ReactElement<Record<string, unknown>>, {
          children: processChildren(props.children as React.ReactNode, transformText),
        });
      }
    }
    return child;
  });
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
  const hasCompass = !!message.compass;

  // During streaming, only show if we have at least some data
  const hasAnyData = hasCitations || hasExperts || hasBalance || hasHQMetaData || hasCompass;
  if (!hasAnyData) return null;

  return (
    <div className={cn(
      "flex flex-col gap-2 w-full min-w-0",
      // Add visual separator only when content is visible above
      message.content && "mt-6 border-t border-border pt-6"
    )}>
      {/* High Quality Variants Analysis */}
      {hasHQMetaData && (
        <CollapsibleSection
          icon={Sparkles}
          title="Analisi High Quality (Best-of-N)"
          count={message.hqMetadata!.variants.length}
          defaultOpen={false}
          infoTooltip="Vengono generate 3 varianti della risposta a temperature diverse, poi un giudice LLM seleziona la migliore per qualità e bilanciamento."
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
          infoTooltip="Gli esperti sono calcolati tramite un authority score basato su: interventi in aula, atti presentati, appartenenza alle commissioni pertinenti, professione, titolo di studio e ruolo istituzionale."
        >
            {message.experts && (
               <div className="space-y-6 pt-2">
                 {(() => {
                    const groupedExperts = message.experts!.reduce((acc, expert) => {
                         if (!acc[expert.group]) acc[expert.group] = [];
                         acc[expert.group].push(expert);
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
            count={1}
            defaultOpen={true}
            infoTooltip="Mappa 2D del posizionamento ideologico dei gruppi parlamentari sul tema, calcolata analizzando i contenuti degli interventi lungo assi tematici estratti automaticamente."
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
          infoTooltip="Interventi parlamentari recuperati dal database tramite ricerca semantica ibrida (vettoriale + full-text) e filtrati per rilevanza al tema."
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
  infoTooltip?: string;
}

function CollapsibleSection({
  icon: Icon,
  title,
  count,
  defaultOpen = false,
  children,
  forceOpen = false,
  infoTooltip,
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
            {infoTooltip && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <span className="inline-flex cursor-help">
                    <Info className="h-3.5 w-3.5 text-muted-foreground/50 hover:text-primary transition-colors" />
                  </span>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[300px]">
                  <p className="text-[11px]">{infoTooltip}</p>
                </TooltipContent>
              </Tooltip>
            )}
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
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild onClick={(e) => e.stopPropagation()}>
                <span className="inline-flex cursor-help">
                  <Info className="h-3.5 w-3.5 text-muted-foreground/50 hover:text-primary transition-colors" />
                </span>
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-[300px]">
                <p className="text-[11px]">Percentuale di rappresentazione delle citazioni usate nella risposta tra maggioranza e opposizione. Un punteggio alto indica una risposta bilanciata.</p>
              </TooltipContent>
            </Tooltip>
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
