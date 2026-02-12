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
  Star,
  Send,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { config } from "@/config";
import { StarRating } from "./StarRating";
import {
  SURVEY_QUESTIONS,
  AB_DIMENSIONS,
  type SurveyFormState,
  type ABRating,
  type PendingChat,
  type ABDimension,
  getInitialSurveyFormState,
} from "@/types/survey";
import {
  getPendingChats,
  createSurvey,
  getEvaluatedChatIds,
} from "@/lib/survey-api";

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
  baseline_answer?: string;
  ab_assignment?: Record<string, string>;
}

type SurveyStep = "select" | "form" | "success";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  "Qualita Risposta": <MessageSquare className="w-4 h-4" />,
  "Citazioni": <Quote className="w-4 h-4" />,
  "Bilanciamento Politico": <Scale className="w-4 h-4" />,
  "Valutazione Complessiva": <Star className="w-4 h-4" />,
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

  // Group questions by category (exclude overall_satisfaction - handled separately)
  const categories = SURVEY_QUESTIONS.filter(q => q.id !== "overall_satisfaction").reduce((acc, q) => {
    if (!acc.find((c) => c.name === q.category)) {
      acc.push({ name: q.category, questions: [] });
    }
    acc.find((c) => c.name === q.category)?.questions.push(q);
    return acc;
  }, [] as { name: string; questions: typeof SURVEY_QUESTIONS }[]);

  // Add final "Valutazione Complessiva" category
  categories.push({
    name: "Valutazione Complessiva",
    questions: SURVEY_QUESTIONS.filter(q => q.id === "overall_satisfaction"),
  });

  // Get response A and B based on ab_assignment
  const getResponseA = (): string => {
    if (!chatDetails) return "";
    const ab = chatDetails.ab_assignment;
    if (!ab) return chatDetails.answer;
    return ab["A"] === "system" ? chatDetails.answer : (chatDetails.baseline_answer || "");
  };

  const getResponseB = (): string => {
    if (!chatDetails) return "";
    const ab = chatDetails.ab_assignment;
    if (!ab) return chatDetails.baseline_answer || "";
    return ab["B"] === "system" ? chatDetails.answer : (chatDetails.baseline_answer || "");
  };

  // Load pending chats
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [pendingRes, evaluatedRes] = await Promise.all([
        getPendingChats(),
        getEvaluatedChatIds(),
      ]);
      console.log("[SurveyModal][BASELINE-DEBUG] Pending chats response:", JSON.stringify(pendingRes));
      console.log("[SurveyModal][BASELINE-DEBUG] Evaluated chat IDs:", evaluatedRes.chat_ids);
      console.log("[SurveyModal][BASELINE-DEBUG] Pending count:", pendingRes.pending.length, "Total:", pendingRes.total);
      setPendingChats(pendingRes.pending);
      setEvaluatedIds(new Set(evaluatedRes.chat_ids));
    } catch (err) {
      setError("Errore nel caricamento delle conversazioni");
      console.error("[SurveyModal][BASELINE-DEBUG] Error loading data:", err);
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

  // Handle chat selection
  const handleSelectChat = async (chat: PendingChat) => {
    setSelectedChat(chat);
    setFormState(getInitialSurveyFormState());
    setCurrentCategory(0);
    setStep("form");
    await loadChatDetails(chat.id);
  };

  // Handle AB rating change for a dimension
  const handleABRatingChange = (
    dimension: ABDimension,
    field: keyof ABRating,
    value: number | string
  ) => {
    setFormState((prev) => ({
      ...prev,
      [dimension]: {
        ...prev[dimension],
        [field]: value,
      },
    }));
  };

  // Check if a dimension's AB rating is complete
  const isABRatingComplete = (rating: ABRating): boolean => {
    return rating.rating_a > 0 && rating.rating_b > 0 && rating.preference !== "";
  };

  // Check if current category is complete
  const isCategoryComplete = (catIndex: number) => {
    const cat = categories[catIndex];
    if (cat.name === "Valutazione Complessiva") {
      return formState.overall_satisfaction_a > 0 &&
             formState.overall_satisfaction_b > 0 &&
             formState.overall_preference !== "";
    }
    return cat.questions.every((q) => {
      const rating = formState[q.id as ABDimension];
      return isABRatingComplete(rating);
    });
  };

  // Check if all required fields are filled
  const isFormComplete = () => {
    const dimensionsComplete = AB_DIMENSIONS.every((dim) =>
      isABRatingComplete(formState[dim])
    );
    const overallComplete = formState.overall_satisfaction_a > 0 &&
                           formState.overall_satisfaction_b > 0 &&
                           formState.overall_preference !== "";
    return dimensionsComplete && overallComplete;
  };

  // Calculate completion percentage
  const completionPercentage = () => {
    let total = AB_DIMENSIONS.length + 1; // dimensions + overall
    let filled = 0;
    for (const dim of AB_DIMENSIONS) {
      if (isABRatingComplete(formState[dim])) filled++;
    }
    if (formState.overall_satisfaction_a > 0 && formState.overall_satisfaction_b > 0 && formState.overall_preference !== "") {
      filled++;
    }
    return Math.round((filled / total) * 100);
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
        overall_satisfaction_a: formState.overall_satisfaction_a,
        overall_satisfaction_b: formState.overall_satisfaction_b,
        overall_preference: formState.overall_preference as "A" | "B" | "equal",
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

  // Render markdown-like content
  const renderContent = (text: string) => {
    const counter = { value: 0 };

    const processInlineText = (lineText: string): React.ReactNode[] => {
      const results: React.ReactNode[] = [];
      const combinedRegex = /(\(leg\d+_[^)]+\)|\[«[^»]+»\]\([^)]+\)|\[CIT:[^\]]+\]|\*\*[^*]+\*\*)/g;
      let lastIndex = 0;
      let match;

      while ((match = combinedRegex.exec(lineText)) !== null) {
        if (match.index > lastIndex) {
          results.push(lineText.slice(lastIndex, match.index));
        }

        const matched = match[0];

        if (matched.startsWith("(leg") && matched.endsWith(")")) {
          counter.value++;
          results.push(
            <Badge key={`cit-${match.index}`} variant="secondary"
              className="mx-0.5 text-[10px] px-1.5 py-0 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700 cursor-help"
              title={matched.slice(1, -1)}>
              Fonte {counter.value}
            </Badge>
          );
        } else if (matched.startsWith("[«") && matched.includes("](")) {
          const quoteMatch = matched.match(/\[«([^»]+)»\]\(([^)]+)\)/);
          if (quoteMatch) {
            counter.value++;
            results.push(
              <span key={`quote-${match.index}`} className="inline">
                <span className="italic text-gray-600 dark:text-gray-400">&laquo;{quoteMatch[1]}&raquo;</span>
                <Badge variant="secondary"
                  className="ml-0.5 text-[10px] px-1.5 py-0 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700 cursor-help"
                  title={quoteMatch[2]}>
                  {counter.value}
                </Badge>
              </span>
            );
          }
        } else if (matched.startsWith("[CIT:")) {
          counter.value++;
          results.push(
            <Badge key={`cit-${match.index}`} variant="secondary"
              className="mx-0.5 text-[10px] px-1.5 py-0 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700">
              {counter.value}
            </Badge>
          );
        } else if (matched.startsWith("**") && matched.endsWith("**")) {
          results.push(
            <strong key={`bold-${match.index}`}>{matched.slice(2, -2)}</strong>
          );
        }

        lastIndex = match.index + matched.length;
      }

      if (lastIndex < lineText.length) {
        results.push(lineText.slice(lastIndex));
      }

      return results;
    };

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
            ? { width: "1600px", maxWidth: "95vw", height: "95vh", maxHeight: "95vh" }
            : { maxWidth: "42rem", maxHeight: "90vh" }
        }
      >
        <DialogHeader className="px-6 py-4 border-b bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <ClipboardCheck className="w-5 h-5 text-blue-600" />
            Valutazione A/B Blind
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
                  Seleziona una conversazione da valutare (solo chat con baseline)
                </p>
                <Button variant="ghost" size="sm" onClick={loadData} disabled={isLoading}>
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
                  {evaluatedIds.size > 0 ? (
                    <>
                      <CheckCircle2 className="w-12 h-12 mb-3 text-emerald-500" />
                      <p className="text-lg font-medium">Tutte le conversazioni sono state valutate!</p>
                      <p className="text-sm mt-1">Grazie per il tuo contributo.</p>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-12 h-12 mb-3 text-gray-400" />
                      <p className="text-lg font-medium">Nessuna conversazione disponibile</p>
                      <p className="text-sm mt-1 text-center max-w-xs">Non ci sono ancora conversazioni con baseline per il confronto A/B. Usa la chat per generarne.</p>
                    </>
                  )}
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
                <span>{evaluatedIds.size} gia valutate</span>
              </div>
            </div>
          </div>
        )}

        {/* Step: Survey Form with A/B Blind Comparison */}
        {step === "form" && selectedChat && (
          <div className="flex flex-col md:flex-row flex-1 min-h-0">
            {/* Left Panel: Side-by-side A/B Responses */}
            <div className="md:w-3/5 md:border-r flex flex-col bg-white dark:bg-gray-950 min-h-0 overflow-hidden border-b md:border-b-0">
              {/* Query Header */}
              <div className="px-3 md:px-4 py-2 md:py-3 bg-blue-50 dark:bg-blue-950/30 border-b">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100 line-clamp-2">
                  <span className="text-blue-600 dark:text-blue-400">Domanda:</span> {selectedChat.query}
                </p>
                <p className="text-xs text-gray-500 mt-1 hidden md:block">
                  Confronta le due risposte. Non sai quale sia il sistema avanzato e quale la baseline.
                </p>
              </div>

              {/* A/B Side by side (desktop) / Tabbed (mobile) */}
              <div className="flex flex-1 min-h-0 overflow-hidden">
                {/* Response A */}
                <div className="w-1/2 border-r flex flex-col min-h-0">
                  <div className="px-3 py-2 bg-blue-100 dark:bg-blue-900/30 border-b text-center">
                    <span className="font-semibold text-blue-700 dark:text-blue-300 text-xs md:text-sm">
                      Risposta A
                    </span>
                  </div>
                  <ScrollArea className="flex-1 px-2 md:px-3 py-2 md:py-3">
                    {isLoadingDetails ? (
                      <div className="flex items-center justify-center h-40">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                      </div>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none text-xs md:text-sm">
                        {renderContent(getResponseA())}
                      </div>
                    )}
                  </ScrollArea>
                </div>

                {/* Response B */}
                <div className="w-1/2 flex flex-col min-h-0">
                  <div className="px-3 py-2 bg-amber-100 dark:bg-amber-900/30 border-b text-center">
                    <span className="font-semibold text-amber-700 dark:text-amber-300 text-xs md:text-sm">
                      Risposta B
                    </span>
                  </div>
                  <ScrollArea className="flex-1 px-2 md:px-3 py-2 md:py-3">
                    {isLoadingDetails ? (
                      <div className="flex items-center justify-center h-40">
                        <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                      </div>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none text-xs md:text-sm">
                        {renderContent(getResponseB())}
                      </div>
                    )}
                  </ScrollArea>
                </div>
              </div>
            </div>

            {/* Right Panel: Survey Form */}
            <div className="md:w-2/5 flex flex-col bg-gray-50 dark:bg-gray-900/30 min-h-0 overflow-hidden flex-1 md:flex-none">
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
                <div className="space-y-5">
                  {/* A/B dimension questions */}
                  {categories[currentCategory].name !== "Valutazione Complessiva" ? (
                    categories[currentCategory].questions.map((question) => {
                      const dim = question.id as ABDimension;
                      const rating = formState[dim];
                      return (
                        <div key={question.id} className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                          <div>
                            <p className="font-medium text-gray-900 dark:text-gray-100">
                              {question.question}
                            </p>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                              {question.description}
                            </p>
                          </div>

                          {/* Rating A */}
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold text-blue-600 w-24">Risposta A</span>
                            <StarRating
                              value={rating.rating_a}
                              onChange={(val) => handleABRatingChange(dim, "rating_a", val)}
                              size="md"
                            />
                          </div>

                          {/* Rating B */}
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold text-amber-600 w-24">Risposta B</span>
                            <StarRating
                              value={rating.rating_b}
                              onChange={(val) => handleABRatingChange(dim, "rating_b", val)}
                              size="md"
                            />
                          </div>

                          {/* Preference */}
                          <div className="flex items-center gap-2 pt-1">
                            <span className="text-xs text-gray-500">Preferenza:</span>
                            <div className="flex gap-1.5">
                              <Button
                                type="button"
                                size="sm"
                                variant={rating.preference === "A" ? "default" : "outline"}
                                onClick={() => handleABRatingChange(dim, "preference", "A")}
                                className={cn(
                                  "h-7 px-3 text-xs",
                                  rating.preference === "A" && "bg-blue-600 hover:bg-blue-700"
                                )}
                              >
                                A migliore
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant={rating.preference === "equal" ? "default" : "outline"}
                                onClick={() => handleABRatingChange(dim, "preference", "equal")}
                                className={cn(
                                  "h-7 px-3 text-xs",
                                  rating.preference === "equal" && "bg-gray-600 hover:bg-gray-700"
                                )}
                              >
                                Uguale
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant={rating.preference === "B" ? "default" : "outline"}
                                onClick={() => handleABRatingChange(dim, "preference", "B")}
                                className={cn(
                                  "h-7 px-3 text-xs",
                                  rating.preference === "B" && "bg-amber-600 hover:bg-amber-700"
                                )}
                              >
                                B migliore
                              </Button>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    /* Overall satisfaction category */
                    <>
                      <div className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          Soddisfazione complessiva
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          Valutazione generale dell'esperienza con ciascuna risposta
                        </p>

                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold text-blue-600 w-24">Risposta A</span>
                          <StarRating
                            value={formState.overall_satisfaction_a}
                            onChange={(val) => setFormState(prev => ({ ...prev, overall_satisfaction_a: val }))}
                            size="md"
                          />
                        </div>

                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold text-amber-600 w-24">Risposta B</span>
                          <StarRating
                            value={formState.overall_satisfaction_b}
                            onChange={(val) => setFormState(prev => ({ ...prev, overall_satisfaction_b: val }))}
                            size="md"
                          />
                        </div>

                        <div className="flex items-center gap-2 pt-1">
                          <span className="text-xs text-gray-500">Preferenza complessiva:</span>
                          <div className="flex gap-1.5">
                            <Button type="button" size="sm"
                              variant={formState.overall_preference === "A" ? "default" : "outline"}
                              onClick={() => setFormState(prev => ({ ...prev, overall_preference: "A" }))}
                              className={cn("h-7 px-3 text-xs", formState.overall_preference === "A" && "bg-blue-600 hover:bg-blue-700")}>
                              A migliore
                            </Button>
                            <Button type="button" size="sm"
                              variant={formState.overall_preference === "equal" ? "default" : "outline"}
                              onClick={() => setFormState(prev => ({ ...prev, overall_preference: "equal" }))}
                              className={cn("h-7 px-3 text-xs", formState.overall_preference === "equal" && "bg-gray-600 hover:bg-gray-700")}>
                              Uguale
                            </Button>
                            <Button type="button" size="sm"
                              variant={formState.overall_preference === "B" ? "default" : "outline"}
                              onClick={() => setFormState(prev => ({ ...prev, overall_preference: "B" }))}
                              className={cn("h-7 px-3 text-xs", formState.overall_preference === "B" && "bg-amber-600 hover:bg-amber-700")}>
                              B migliore
                            </Button>
                          </div>
                        </div>
                      </div>

                      <Separator className="my-4" />

                      {/* Would recommend */}
                      <div className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          Consiglieresti questo tipo di sistema ai tuoi colleghi?
                        </p>
                        <div className="flex gap-3">
                          <Button type="button"
                            variant={formState.would_recommend ? "default" : "outline"}
                            onClick={() => setFormState(prev => ({ ...prev, would_recommend: true }))}
                            className={cn("flex-1", formState.would_recommend && "bg-emerald-600 hover:bg-emerald-700")}>
                            <ThumbsUp className="w-4 h-4 mr-2" />
                            Si
                          </Button>
                          <Button type="button"
                            variant={!formState.would_recommend ? "default" : "outline"}
                            onClick={() => setFormState(prev => ({ ...prev, would_recommend: false }))}
                            className={cn("flex-1", !formState.would_recommend && "bg-gray-600 hover:bg-gray-700")}>
                            No
                          </Button>
                        </div>
                      </div>

                      {/* Feedback */}
                      <div className="space-y-4 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            Cosa ha funzionato bene? (opzionale)
                          </label>
                          <Textarea
                            placeholder="Descrivi gli aspetti positivi..."
                            value={formState.feedback_positive}
                            onChange={(e) => setFormState(prev => ({ ...prev, feedback_positive: e.target.value }))}
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
                            onChange={(e) => setFormState(prev => ({ ...prev, feedback_improvement: e.target.value }))}
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
              Il tuo feedback e prezioso per confrontare il sistema avanzato con la baseline.
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
