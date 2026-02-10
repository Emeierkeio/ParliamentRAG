"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ClipboardCheck,
  ChevronRight,
  ChevronLeft,
  Check,
  AlertCircle,
  Loader2,
  ThumbsUp,
  MessageSquare,
  Quote,
  Scale,
  Compass,
  Star,
  Send,
  RefreshCw,
  CheckCircle2,
  FileText,
  Eye,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { config } from "@/config";
import { StarRating } from "./StarRating";
import { CompassCard } from "@/components/chat/CompassCard";
import {
  SURVEY_QUESTIONS,
  type SurveyFormState,
  type PendingChat,
  getInitialSurveyFormState,
} from "@/types/survey";
import {
  getPendingChats,
  createSurvey,
  getEvaluatedChatIds,
} from "@/lib/survey-api";
import { getChatMetrics } from "@/lib/evaluation-api";
import type { AutomatedMetrics } from "@/types/evaluation";

interface SurveyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ChatDetails {
  id: string;
  query: string;
  answer: string;
  citations: any[];
  experts: any[];
  balance: any;
  compass: any;
  timestamp: string;
}

type SurveyStep = "select" | "form" | "success";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  "Qualità Risposta": <MessageSquare className="w-4 h-4" />,
  "Citazioni": <Quote className="w-4 h-4" />,
  "Bilanciamento Politico": <Scale className="w-4 h-4" />,
  "Funzionalità": <Compass className="w-4 h-4" />,
  "Confronto Baseline": <Eye className="w-4 h-4" />,
  "Valutazione Complessiva": <Star className="w-4 h-4" />,
};

const BASELINE_VALUES: Record<string, { value: number; label: string }> = {
  party_coverage_score: { value: 0.35, label: "Copertura Partiti" },
  citation_integrity_score: { value: 0.65, label: "Integrità Citazioni" },
  balance_score: { value: 0.60, label: "Bilanciamento" },
  authority_utilization: { value: 0.50, label: "Utilizzo Autorità" },
  response_completeness: { value: 0.25, label: "Completezza Risposta" },
};

export function SurveyModal({ isOpen, onClose }: SurveyModalProps) {
  const [step, setStep] = useState<SurveyStep>("select");
  const [pendingChats, setPendingChats] = useState<PendingChat[]>([]);
  const [evaluatedIds, setEvaluatedIds] = useState<Set<string>>(new Set());
  const [selectedChat, setSelectedChat] = useState<PendingChat | null>(null);
  const [chatDetails, setChatDetails] = useState<ChatDetails | null>(null);
  const [formState, setFormState] = useState<SurveyFormState>(getInitialSurveyFormState());
  const [currentCategory, setCurrentCategory] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeContentTab, setActiveContentTab] = useState<"response" | "compass" | "metrics">("response");
  const [chatMetrics, setChatMetrics] = useState<AutomatedMetrics | null>(null);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);

  // Group questions by category
  const categories = SURVEY_QUESTIONS.reduce((acc, q) => {
    if (!acc.find((c) => c.name === q.category)) {
      acc.push({ name: q.category, questions: [] });
    }
    acc.find((c) => c.name === q.category)?.questions.push(q);
    return acc;
  }, [] as { name: string; questions: typeof SURVEY_QUESTIONS }[]);

  // Load pending chats
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [pendingRes, evaluatedRes] = await Promise.all([
        getPendingChats(),
        getEvaluatedChatIds(),
      ]);
      setPendingChats(pendingRes.pending);
      setEvaluatedIds(new Set(evaluatedRes.chat_ids));
    } catch (err) {
      setError("Errore nel caricamento delle conversazioni");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load chat details
  const loadChatDetails = useCallback(async (chatId: string) => {
    setIsLoadingDetails(true);
    try {
      const res = await fetch(`${config.api.baseUrl}/history/${chatId}`);
      if (!res.ok) throw new Error("Failed to load chat details");
      const data = await res.json();
      setChatDetails(data);
    } catch (err) {
      console.error(err);
      setError("Errore nel caricamento dei dettagli");
    } finally {
      setIsLoadingDetails(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadData();
      setStep("select");
      setSelectedChat(null);
      setChatDetails(null);
      setFormState(getInitialSurveyFormState());
      setCurrentCategory(0);
    }
  }, [isOpen, loadData]);

  // Load automated metrics for a chat
  const loadChatMetrics = useCallback(async (chatId: string) => {
    setIsLoadingMetrics(true);
    try {
      const metrics = await getChatMetrics(chatId);
      setChatMetrics(metrics);
    } catch (err) {
      console.error("Failed to load metrics:", err);
      setChatMetrics(null);
    } finally {
      setIsLoadingMetrics(false);
    }
  }, []);

  // Handle chat selection
  const handleSelectChat = async (chat: PendingChat) => {
    setSelectedChat(chat);
    setFormState(getInitialSurveyFormState());
    setCurrentCategory(0);
    setActiveContentTab("response");
    setChatMetrics(null);
    setStep("form");
    await Promise.all([loadChatDetails(chat.id), loadChatMetrics(chat.id)]);
  };

  // Handle form field change
  const handleFieldChange = (field: keyof SurveyFormState, value: number | boolean | string) => {
    setFormState((prev) => ({ ...prev, [field]: value }));
  };

  // Check if current category is complete
  const isCategoryComplete = (catIndex: number) => {
    const cat = categories[catIndex];
    return cat.questions.every((q) => formState[q.id as keyof SurveyFormState] !== 0);
  };

  // Check if all required fields are filled
  const isFormComplete = () => {
    return SURVEY_QUESTIONS.every((q) => formState[q.id as keyof SurveyFormState] !== 0);
  };

  // Calculate completion percentage
  const completionPercentage = () => {
    const filled = SURVEY_QUESTIONS.filter(
      (q) => formState[q.id as keyof SurveyFormState] !== 0
    ).length;
    return Math.round((filled / SURVEY_QUESTIONS.length) * 100);
  };

  // Navigate categories
  const goToNextCategory = () => {
    if (currentCategory < categories.length - 1) {
      setCurrentCategory((prev) => prev + 1);
    }
  };

  const goToPrevCategory = () => {
    if (currentCategory > 0) {
      setCurrentCategory((prev) => prev - 1);
    }
  };

  // Submit survey
  const handleSubmit = async () => {
    if (!selectedChat || !isFormComplete()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await createSurvey({
        chat_id: selectedChat.id,
        answer_quality: formState.answer_quality,
        answer_clarity: formState.answer_clarity,
        answer_completeness: formState.answer_completeness,
        citations_relevance: formState.citations_relevance,
        citations_accuracy: formState.citations_accuracy,
        balance_perception: formState.balance_perception,
        balance_fairness: formState.balance_fairness,
        compass_usefulness: formState.compass_usefulness,
        experts_usefulness: formState.experts_usefulness,
        baseline_improvement: formState.baseline_improvement,
        authority_value: formState.authority_value,
        citation_pipeline_value: formState.citation_pipeline_value,
        overall_satisfaction: formState.overall_satisfaction,
        would_recommend: formState.would_recommend,
        feedback_positive: formState.feedback_positive || undefined,
        feedback_improvement: formState.feedback_improvement || undefined,
      });

      setStep("success");
    } catch (err: any) {
      setError(err.message || "Errore nell'invio della valutazione");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("it-IT", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  // Render markdown-like content with proper citation formatting
  const renderContent = (text: string) => {
    // Counter object to track citations across nested function calls
    const counter = { value: 0 };

    // Process inline text to handle citations and formatting
    const processInlineText = (lineText: string): React.ReactNode[] => {
      const results: React.ReactNode[] = [];

      // Combined regex to match various citation formats:
      // 1. (leg19_..._chunk_N) - raw chunk IDs in parentheses
      // 2. [«text»](chunk_id) - markdown link format
      // 3. [CIT:chunk_id] - explicit citation marker
      // 4. **bold text** - markdown bold
      const combinedRegex = /(\(leg\d+_[^)]+\)|\[«[^»]+»\]\([^)]+\)|\[CIT:[^\]]+\]|\*\*[^*]+\*\*)/g;

      let lastIndex = 0;
      let match;

      while ((match = combinedRegex.exec(lineText)) !== null) {
        // Add text before match
        if (match.index > lastIndex) {
          results.push(lineText.slice(lastIndex, match.index));
        }

        const matched = match[0];

        if (matched.startsWith("(leg") && matched.endsWith(")")) {
          // Raw chunk ID in parentheses - show as citation badge
          counter.value++;
          results.push(
            <Badge
              key={`cit-${match.index}`}
              variant="secondary"
              className="mx-0.5 text-[10px] px-1.5 py-0 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700 cursor-help"
              title={matched.slice(1, -1)}
            >
              📎 Fonte {counter.value}
            </Badge>
          );
        } else if (matched.startsWith("[«") && matched.includes("](")) {
          // Markdown link format with citation - extract quoted text
          const quoteMatch = matched.match(/\[«([^»]+)»\]\(([^)]+)\)/);
          if (quoteMatch) {
            counter.value++;
            results.push(
              <span key={`quote-${match.index}`} className="inline">
                <span className="italic text-gray-600 dark:text-gray-400">&laquo;{quoteMatch[1]}&raquo;</span>
                <Badge
                  variant="secondary"
                  className="ml-0.5 text-[10px] px-1.5 py-0 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700 cursor-help"
                  title={quoteMatch[2]}
                >
                  {counter.value}
                </Badge>
              </span>
            );
          }
        } else if (matched.startsWith("[CIT:")) {
          // Explicit citation marker
          counter.value++;
          results.push(
            <Badge
              key={`cit-${match.index}`}
              variant="secondary"
              className="mx-0.5 text-[10px] px-1.5 py-0 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700"
            >
              📎 {counter.value}
            </Badge>
          );
        } else if (matched.startsWith("**") && matched.endsWith("**")) {
          // Bold text
          results.push(
            <strong key={`bold-${match.index}`}>{matched.slice(2, -2)}</strong>
          );
        }

        lastIndex = match.index + matched.length;
      }

      // Add remaining text
      if (lastIndex < lineText.length) {
        results.push(lineText.slice(lastIndex));
      }

      return results;
    };

    // Simple markdown rendering
    const lines = text.split("\n");
    return lines.map((line, i) => {
      if (line.startsWith("## ")) {
        return <h2 key={i} className="text-lg font-bold mt-4 mb-2 text-gray-900 dark:text-gray-100">{processInlineText(line.slice(3))}</h2>;
      }
      if (line.startsWith("### ")) {
        return <h3 key={i} className="text-base font-semibold mt-3 mb-1 text-gray-800 dark:text-gray-200">{processInlineText(line.slice(4))}</h3>;
      }
      if (line.startsWith("- ")) {
        return <li key={i} className="ml-4 text-gray-700 dark:text-gray-300">{processInlineText(line.slice(2))}</li>;
      }
      if (line.trim() === "") {
        return <br key={i} />;
      }
      return (
        <p key={i} className="text-gray-700 dark:text-gray-300 leading-relaxed mb-2">
          {processInlineText(line)}
        </p>
      );
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className={cn(
          "p-0 gap-0 overflow-hidden flex flex-col",
          step === "form" && "sm:!max-w-[95vw]"
        )}
        style={
          step === "form"
            ? { width: "1400px", maxWidth: "95vw", height: "90vh" }
            : { maxWidth: "42rem", maxHeight: "90vh" }
        }
      >
        <DialogHeader className="px-6 py-4 border-b bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <ClipboardCheck className="w-5 h-5 text-blue-600" />
            Valutazione Sistema
          </DialogTitle>
          {step === "form" && (
            <div className="flex items-center gap-3 mt-2">
              <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${completionPercentage()}%` }}
                />
              </div>
              <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                {completionPercentage()}%
              </span>
            </div>
          )}
        </DialogHeader>

        {/* Step: Select Chat */}
        {step === "select" && (
          <div className="flex flex-col h-[60vh]">
            <div className="px-6 py-3 bg-gray-50 dark:bg-gray-900/50 border-b">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Seleziona una conversazione da valutare
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={loadData}
                  disabled={isLoading}
                >
                  <RefreshCw className={cn("w-4 h-4 mr-1", isLoading && "animate-spin")} />
                  Aggiorna
                </Button>
              </div>
            </div>

            <ScrollArea className="flex-1 px-6 py-4">
              {isLoading ? (
                <div className="flex items-center justify-center h-40">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-40 text-red-500">
                  <AlertCircle className="w-8 h-8 mb-2" />
                  <p>{error}</p>
                </div>
              ) : pendingChats.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 text-gray-500">
                  <CheckCircle2 className="w-12 h-12 mb-3 text-emerald-500" />
                  <p className="text-lg font-medium">Tutte le conversazioni sono state valutate!</p>
                  <p className="text-sm mt-1">Grazie per il tuo contributo.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingChats.map((chat) => (
                    <Card
                      key={chat.id}
                      className={cn(
                        "cursor-pointer transition-all duration-200 hover:shadow-md hover:border-blue-300",
                        "dark:hover:border-blue-700"
                      )}
                      onClick={() => handleSelectChat(chat)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-gray-900 dark:text-gray-100 line-clamp-2">
                              {chat.query}
                            </p>
                            {chat.preview && (
                              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 line-clamp-1">
                                {chat.preview}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            <Badge variant="outline" className="text-xs whitespace-nowrap">
                              {formatDate(chat.timestamp)}
                            </Badge>
                            <ChevronRight className="w-5 h-5 text-gray-400" />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </ScrollArea>

            <div className="px-6 py-4 border-t bg-gray-50 dark:bg-gray-900/50">
              <div className="flex items-center justify-between text-sm text-gray-500">
                <span>{pendingChats.length} conversazioni da valutare</span>
                <span>{evaluatedIds.size} già valutate</span>
              </div>
            </div>
          </div>
        )}

        {/* Step: Survey Form with Content Preview */}
        {step === "form" && selectedChat && (
          <div className="flex flex-1 min-h-0">
            {/* Left Panel: Content Preview */}
            <div className="w-1/2 border-r flex flex-col bg-white dark:bg-gray-950 min-h-0 overflow-hidden">
              {/* Query Header */}
              <div className="px-4 py-3 bg-blue-50 dark:bg-blue-950/30 border-b">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  <span className="text-blue-600 dark:text-blue-400">Domanda:</span> {selectedChat.query}
                </p>
              </div>

              {/* Content Tabs */}
              <Tabs value={activeContentTab} onValueChange={(v) => setActiveContentTab(v as any)} className="flex-1 flex flex-col min-h-0 overflow-hidden">
                <TabsList className="mx-4 mt-3 grid w-auto grid-cols-3 h-9">
                  <TabsTrigger value="response" className="text-sm gap-1.5">
                    <FileText className="w-4 h-4" />
                    Risposta
                  </TabsTrigger>
                  <TabsTrigger value="compass" className="text-sm gap-1.5" disabled={!chatDetails?.compass}>
                    <Compass className="w-4 h-4" />
                    Compass
                  </TabsTrigger>
                  <TabsTrigger value="metrics" className="text-sm gap-1.5">
                    <Eye className="w-4 h-4" />
                    Metriche
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="response" className="flex-1 m-0 min-h-0 overflow-hidden data-[state=active]:flex data-[state=active]:flex-col">
                  <ScrollArea className="flex-1 px-4 py-4">
                    {isLoadingDetails ? (
                      <div className="flex items-center justify-center h-40">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                        <span className="ml-2 text-sm text-gray-500">Caricamento risposta...</span>
                      </div>
                    ) : chatDetails?.answer ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        {renderContent(chatDetails.answer)}
                      </div>
                    ) : (
                      <p className="text-gray-500 text-center">Nessuna risposta disponibile</p>
                    )}
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="compass" className="flex-1 m-0 min-h-0 overflow-hidden data-[state=active]:flex data-[state=active]:flex-col">
                  <ScrollArea className="flex-1 px-4 py-4">
                    {isLoadingDetails ? (
                      <div className="flex items-center justify-center h-40">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                        <span className="ml-2 text-sm text-gray-500">Caricamento compass...</span>
                      </div>
                    ) : chatDetails?.compass ? (
                      <CompassCard data={chatDetails.compass} />
                    ) : (
                      <div className="flex flex-col items-center justify-center h-40 text-gray-500">
                        <Compass className="w-10 h-10 mb-2 opacity-30" />
                        <p>Compass non disponibile per questa risposta</p>
                      </div>
                    )}
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="metrics" className="flex-1 m-0 min-h-0 overflow-hidden data-[state=active]:flex data-[state=active]:flex-col">
                  <ScrollArea className="flex-1 px-4 py-4">
                    {isLoadingMetrics ? (
                      <div className="flex items-center justify-center h-40">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                        <span className="ml-2 text-sm text-gray-500">Caricamento metriche...</span>
                      </div>
                    ) : chatMetrics ? (
                      <div className="space-y-4">
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                          Metriche automatiche calcolate dalla pipeline — confronto con baseline Naive RAG
                        </p>
                        {/* Metric bars with baseline comparison */}
                        {Object.entries(BASELINE_VALUES).map(([key, { value: baseline, label }]) => {
                          const systemValue = chatMetrics[key as keyof typeof chatMetrics] as number;
                          const delta = systemValue - baseline;
                          return (
                            <div key={key} className="space-y-1">
                              <div className="flex items-center justify-between text-sm">
                                <span className="font-medium text-gray-700 dark:text-gray-300">{label}</span>
                                <span className="font-mono text-sm">{(systemValue * 100).toFixed(0)}%</span>
                              </div>
                              <div className="relative h-5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                                <div
                                  className="absolute h-full rounded-full bg-amber-300/50 dark:bg-amber-700/30"
                                  style={{ width: `${baseline * 100}%` }}
                                />
                                <div
                                  className="absolute h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500"
                                  style={{ width: `${systemValue * 100}%` }}
                                />
                              </div>
                              <div className="flex items-center justify-between text-xs text-gray-500">
                                <span>Baseline: {(baseline * 100).toFixed(0)}%</span>
                                <span className={delta > 0 ? "text-emerald-600 font-semibold" : delta < 0 ? "text-red-600 font-semibold" : ""}>
                                  {delta > 0 ? "+" : ""}{(delta * 100).toFixed(1)}pp
                                </span>
                              </div>
                            </div>
                          );
                        })}
                        {/* Legend */}
                        <div className="flex items-center gap-4 mt-4 pt-3 border-t text-xs text-gray-500">
                          <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded bg-gradient-to-r from-blue-500 to-indigo-500" />
                            ParliamentRAG
                          </div>
                          <div className="flex items-center gap-1">
                            <div className="w-3 h-3 rounded bg-amber-300/50 dark:bg-amber-700/30" />
                            Naive RAG (baseline)
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-40 text-gray-500">
                        <Eye className="w-10 h-10 mb-2 opacity-30" />
                        <p>Metriche non disponibili</p>
                      </div>
                    )}
                  </ScrollArea>
                </TabsContent>
              </Tabs>

              {/* Balance Info */}
              {chatDetails?.balance && (
                <div className="px-4 py-3 border-t bg-gray-50 dark:bg-gray-900/50">
                  <div className="flex items-center gap-4 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-blue-500" />
                      <span className="text-gray-600 dark:text-gray-400">
                        Maggioranza: {Math.round(chatDetails.balance.maggioranza_percentage || 0)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-red-500" />
                      <span className="text-gray-600 dark:text-gray-400">
                        Opposizione: {Math.round(chatDetails.balance.opposizione_percentage || 0)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Panel: Survey Form */}
            <div className="w-1/2 flex flex-col bg-gray-50 dark:bg-gray-900/30 min-h-0 overflow-hidden">
              {/* Category tabs */}
              <div className="px-4 py-3 border-b bg-white dark:bg-gray-950 flex gap-2 overflow-x-auto">
                {categories.map((cat, idx) => (
                  <button
                    key={cat.name}
                    onClick={() => setCurrentCategory(idx)}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all whitespace-nowrap",
                      currentCategory === idx
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
                        : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800",
                      isCategoryComplete(idx) && "ring-2 ring-emerald-400 ring-offset-1"
                    )}
                  >
                    {CATEGORY_ICONS[cat.name]}
                    {cat.name}
                    {isCategoryComplete(idx) && (
                      <Check className="w-3.5 h-3.5 text-emerald-500" />
                    )}
                  </button>
                ))}
              </div>

              {/* Questions */}
              <ScrollArea className="flex-1 min-h-0 px-4 py-4">
                <div className="space-y-6">
                  {categories[currentCategory].questions.map((question) => (
                    <div key={question.id} className="space-y-2 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                      <div>
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {question.question}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {question.description}
                        </p>
                      </div>
                      <StarRating
                        value={formState[question.id as keyof SurveyFormState] as number}
                        onChange={(val) => handleFieldChange(question.id as keyof SurveyFormState, val)}
                        size="lg"
                      />
                    </div>
                  ))}

                  {/* Final category: additional fields */}
                  {currentCategory === categories.length - 1 && (
                    <>
                      <Separator className="my-4" />

                      {/* Would recommend */}
                      <div className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          Consiglieresti questo sistema ai tuoi colleghi?
                        </p>
                        <div className="flex gap-3">
                          <Button
                            type="button"
                            variant={formState.would_recommend ? "default" : "outline"}
                            onClick={() => handleFieldChange("would_recommend", true)}
                            className={cn(
                              "flex-1",
                              formState.would_recommend && "bg-emerald-600 hover:bg-emerald-700"
                            )}
                          >
                            <ThumbsUp className="w-4 h-4 mr-2" />
                            Sì, lo consiglierei
                          </Button>
                          <Button
                            type="button"
                            variant={!formState.would_recommend ? "default" : "outline"}
                            onClick={() => handleFieldChange("would_recommend", false)}
                            className={cn(
                              "flex-1",
                              !formState.would_recommend && "bg-gray-600 hover:bg-gray-700"
                            )}
                          >
                            Non ancora
                          </Button>
                        </div>
                      </div>

                      {/* Feedback text areas */}
                      <div className="space-y-4 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            Cosa ha funzionato bene? (opzionale)
                          </label>
                          <Textarea
                            placeholder="Descrivi gli aspetti positivi della tua esperienza..."
                            value={formState.feedback_positive}
                            onChange={(e) => handleFieldChange("feedback_positive", e.target.value)}
                            className="min-h-[80px] resize-none"
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            Suggerimenti per migliorare? (opzionale)
                          </label>
                          <Textarea
                            placeholder="Come potremmo migliorare il sistema..."
                            value={formState.feedback_improvement}
                            onChange={(e) => handleFieldChange("feedback_improvement", e.target.value)}
                            className="min-h-[80px] resize-none"
                          />
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </ScrollArea>

              {/* Navigation */}
              <div className="px-4 py-4 border-t bg-white dark:bg-gray-950">
                {error && (
                  <div className="mb-3 p-2 bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 text-sm rounded-lg flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <Button
                    variant="ghost"
                    onClick={() => currentCategory === 0 ? setStep("select") : goToPrevCategory()}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    {currentCategory === 0 ? "Indietro" : "Precedente"}
                  </Button>

                  {currentCategory < categories.length - 1 ? (
                    <Button onClick={goToNextCategory} disabled={!isCategoryComplete(currentCategory)}>
                      Avanti
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  ) : (
                    <Button
                      onClick={handleSubmit}
                      disabled={!isFormComplete() || isSubmitting}
                      className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                    >
                      {isSubmitting ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Send className="w-4 h-4 mr-2" />
                      )}
                      Invia Valutazione
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step: Success */}
        {step === "success" && (
          <div className="flex flex-col items-center justify-center h-[40vh] px-6 py-8">
            <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
              <CheckCircle2 className="w-10 h-10 text-emerald-600" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Grazie per la tua valutazione!
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-center max-w-sm mb-6">
              Il tuo feedback è prezioso per migliorare il sistema e renderlo più utile per la ricerca giornalistica.
            </p>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep("select")}>
                Valuta altra conversazione
              </Button>
              <Button onClick={onClose}>
                Chiudi
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
