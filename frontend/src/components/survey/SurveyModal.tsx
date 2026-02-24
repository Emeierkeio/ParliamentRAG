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
  RefreshCw,
  CheckCircle2,
  BarChart2,
  UserCheck,
} from "lucide-react";
import type { Expert } from "@/types/chat";
import { ExpertCard } from "@/components/chat/ExpertCard";
import { cn } from "@/lib/utils";
import { config } from "@/config";
import { StarRating } from "./StarRating";
import { CitationReviewStep } from "./CitationReviewStep";
import {
  SURVEY_QUESTIONS,
  AB_DIMENSIONS,
  SIMPLE_DIMENSIONS,
  SIMPLE_DIMENSION_LABELS,
  type SurveyFormState,
  type ABRating,
  type PendingChat,
  type ABDimension,
  type SimpleRatingFormState,
  getInitialSurveyFormState,
  getInitialSimpleRatingFormState,
  getInitialCitationEvaluation,
} from "@/types/survey";
import type { Citation } from "@/types/chat";
import {
  getPendingChats,
  createSurvey,
  createSimpleRating,
  getEvaluatedChatIds,
} from "@/lib/survey-api";

interface SurveyModalProps {
  isOpen: boolean;
  onClose: () => void;
  evaluatorId?: string;
}

interface ChatDetails {
  id: string;
  query: string;
  answer: string;
  citations: any[];
  experts: Expert[];
  balance: any;
  compass: any;
  timestamp: string;
}

type SurveyStep = "select" | "form" | "simple_form" | "citations" | "success";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  "Qualita Risposta": <MessageSquare className="w-4 h-4" />,
  "Citazioni": <Quote className="w-4 h-4" />,
  "Bilanciamento Politico": <Scale className="w-4 h-4" />,
  "Autorità Esperti": <UserCheck className="w-4 h-4" />,
  "Valutazione Complessiva": <Star className="w-4 h-4" />,
};

// ─── Known political groups ordered by coalition ──────────────────────────────

const POLITICAL_GROUPS_ORDERED = [
  // Maggioranza
  { key: "FRATELLI D'ITALIA", label: "Fratelli d'Italia", coalition: "maggioranza" },
  { key: "LEGA - SALVINI PREMIER", label: "Lega - Salvini Premier", coalition: "maggioranza" },
  { key: "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE", label: "Forza Italia", coalition: "maggioranza" },
  { key: "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC, ITALIA AL CENTRO)-MAIE", label: "Noi Moderati", coalition: "maggioranza" },
  // Opposizione
  { key: "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA", label: "Partito Democratico", coalition: "opposizione" },
  { key: "MOVIMENTO 5 STELLE", label: "Movimento 5 Stelle", coalition: "opposizione" },
  { key: "ALLEANZA VERDI E SINISTRA", label: "Alleanza Verdi e Sinistra", coalition: "opposizione" },
  { key: "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE", label: "Azione", coalition: "opposizione" },
  { key: "ITALIA VIVA-IL CENTRO-RENEW EUROPE", label: "Italia Viva", coalition: "opposizione" },
  { key: "MISTO", label: "Gruppo Misto", coalition: "altro" },
];

/** Pick the best expert (highest authority_score) per political group. */
function pickOnePerGroup(experts: Expert[]): Record<string, Expert> {
  const result: Record<string, Expert> = {};
  for (const e of experts) {
    const g = (e.group || "MISTO").toUpperCase();
    if (!result[g] || e.authority_score > result[g].authority_score) {
      result[g] = e;
    }
  }
  return result;
}

// ─── Group-by-group authority comparison panel ───────────────────────────────

function AuthorityGroupComparisonPanel({
  expertsA,
  expertsB,
  isLoadingA,
  isLoadingB,
}: {
  expertsA: Expert[];
  expertsB: Expert[];
  isLoadingA: boolean;
  isLoadingB: boolean;
}) {
  const byGroupA = pickOnePerGroup(expertsA);
  const byGroupB = pickOnePerGroup(expertsB);

  if (isLoadingA || isLoadingB) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-gray-400 gap-2">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
        <p className="text-xs">Ricerca deputati nel testo...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0 overflow-y-auto px-2 py-2 space-y-1">
      {/* Header row */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-center px-1 mb-1 shrink-0">
        <div className="text-center">
          <span className="text-xs font-semibold text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/30 px-2 py-0.5 rounded-full">
            Risposta A
          </span>
        </div>
        <div className="w-20 text-center">
          <span className="text-xs text-gray-400 font-medium">Gruppo</span>
        </div>
        <div className="text-center">
          <span className="text-xs font-semibold text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-900/30 px-2 py-0.5 rounded-full">
            Risposta B
          </span>
        </div>
      </div>

      {POLITICAL_GROUPS_ORDERED.map(({ key, label, coalition }) => {
        const expertA = byGroupA[key] || byGroupA[key.toLowerCase()] || null;
        const expertB = byGroupB[key] || byGroupB[key.toLowerCase()] || null;

        const coalColor =
          coalition === "maggioranza" ? "text-red-500" :
          coalition === "opposizione" ? "text-blue-500" : "text-gray-400";

        return (
          <div key={key} className="grid grid-cols-[1fr_auto_1fr] gap-2 items-center border-b border-gray-100 dark:border-gray-800 pb-1 last:border-0">
            {/* Expert A */}
            <div className="flex flex-col items-end">
              {expertA ? (
                <AuthorityExpertMini expert={expertA} side="A" />
              ) : (
                <div className="text-xs text-gray-400 italic text-right px-1 py-1.5">
                  Citazione non disponibile
                </div>
              )}
            </div>

            {/* Group label */}
            <div className="w-20 flex flex-col items-center gap-0.5 shrink-0">
              <span className={`text-[10px] font-bold uppercase tracking-wide ${coalColor}`}>
                {label}
              </span>
            </div>

            {/* Expert B */}
            <div className="flex flex-col items-start">
              {expertB ? (
                <AuthorityExpertMini expert={expertB} side="B" />
              ) : (
                <div className="text-xs text-gray-400 italic text-left px-1 py-1.5">
                  Citazione non disponibile
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Compact expert display for the group comparison panel. */
function AuthorityExpertMini({ expert, side }: { expert: Expert; side: "A" | "B" }) {
  const groupConfig = config.politicalGroups[expert.group as keyof typeof config.politicalGroups];
  const groupColor = groupConfig?.color || "#6B7280";
  const isA = side === "A";

  return (
    <div className={cn(
      "flex items-center gap-1.5 py-1 px-1.5 rounded-lg w-full",
      isA ? "flex-row-reverse text-right" : "flex-row text-left"
    )}>
      {expert.photo ? (
        <img
          src={expert.photo}
          alt={`${expert.first_name} ${expert.last_name}`}
          className="h-8 w-8 shrink-0 rounded-full object-cover"
        />
      ) : (
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
          style={{ backgroundColor: groupColor }}
        >
          {expert.first_name[0]}{expert.last_name[0]}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-foreground leading-tight truncate">
          {expert.first_name} {expert.last_name}
        </p>
        <div className={cn("flex items-center gap-1 mt-0.5", isA ? "flex-row-reverse" : "flex-row")}>
          <div className="h-1 w-10 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full", expert.authority_score >= 0.7 ? "bg-emerald-500" : expert.authority_score >= 0.4 ? "bg-amber-500" : "bg-gray-400")}
              style={{ width: `${expert.authority_score * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">{(expert.authority_score * 100).toFixed(0)}</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

// ─── Comparative Slider (A ←→ B) ─────────────────────────────────────────────

/**
 * A 7-step comparative slider replacing dual star ratings for authority questions.
 * Steps: -3(A▶▶▶) -2(A▶▶) -1(A▶) 0(=) +1(◀B) +2(◀◀B) +3(◀◀◀B)
 * Maps to (rating_a, rating_b) pairs.
 */
const SLIDER_STEP_MAP: Record<number, { rating_a: number; rating_b: number; label: string }> = {
  "-3": { rating_a: 5, rating_b: 2, label: "A molto meglio" },
  "-2": { rating_a: 4, rating_b: 2, label: "A meglio" },
  "-1": { rating_a: 4, rating_b: 3, label: "A leggermente meglio" },
   "0": { rating_a: 3, rating_b: 3, label: "Equivalenti" },
   "1": { rating_a: 3, rating_b: 4, label: "B leggermente meglio" },
   "2": { rating_a: 2, rating_b: 4, label: "B meglio" },
   "3": { rating_a: 2, rating_b: 5, label: "B molto meglio" },
};

function ratingsToSliderStep(rating_a: number, rating_b: number): number {
  if (rating_a === 0 || rating_b === 0) return 0; // unset → neutral
  const delta = rating_b - rating_a;
  if (delta >= 3) return 3;
  if (delta <= -3) return -3;
  return delta;
}

interface ComparativeSliderProps {
  ratingA: number;
  ratingB: number;
  onChange: (rating_a: number, rating_b: number, preference: "A" | "B" | "equal") => void;
  disabled?: boolean;
}

function ComparativeSlider({ ratingA, ratingB, onChange, disabled }: ComparativeSliderProps) {
  const step = ratingA === 0 && ratingB === 0 ? undefined : ratingsToSliderStep(ratingA, ratingB);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = parseInt(e.target.value);
    const mapped = SLIDER_STEP_MAP[v.toString() as keyof typeof SLIDER_STEP_MAP];
    if (!mapped) return;
    const pref: "A" | "B" | "equal" = v < 0 ? "A" : v > 0 ? "B" : "equal";
    onChange(mapped.rating_a, mapped.rating_b, pref);
  };

  const currentLabel = step !== undefined ? (SLIDER_STEP_MAP[step.toString() as keyof typeof SLIDER_STEP_MAP]?.label ?? "Sposta lo slider") : "Sposta lo slider";
  const isSet = step !== undefined;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs font-semibold">
        <span className="text-blue-600 dark:text-blue-400">A migliore</span>
        <span className={cn(
          "text-xs px-2 py-0.5 rounded-full font-medium",
          !isSet ? "text-gray-400 bg-gray-100 dark:bg-gray-800" :
          step! < 0 ? "text-blue-700 bg-blue-100 dark:bg-blue-900/40" :
          step! > 0 ? "text-amber-700 bg-amber-100 dark:bg-amber-900/40" :
          "text-gray-600 bg-gray-100 dark:bg-gray-800"
        )}>
          {currentLabel}
        </span>
        <span className="text-amber-600 dark:text-amber-400">B migliore</span>
      </div>
      <div className="relative">
        <input
          type="range"
          min={-3}
          max={3}
          step={1}
          value={step ?? 0}
          onChange={handleChange}
          disabled={disabled}
          className={cn(
            "w-full h-2 rounded-full appearance-none cursor-pointer",
            "bg-gradient-to-r from-blue-400 via-gray-200 to-amber-400",
            "dark:from-blue-600 dark:via-gray-700 dark:to-amber-600",
            "[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:w-5",
            "[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white",
            "[&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:shadow-md",
            !isSet ? "[&::-webkit-slider-thumb]:border-gray-300" :
            step! < 0 ? "[&::-webkit-slider-thumb]:border-blue-500" :
            step! > 0 ? "[&::-webkit-slider-thumb]:border-amber-500" :
            "[&::-webkit-slider-thumb]:border-gray-400",
            disabled && "opacity-50 cursor-not-allowed"
          )}
        />
        {/* Tick marks */}
        <div className="flex justify-between px-1 mt-0.5">
          {[-3,-2,-1,0,1,2,3].map((v) => (
            <div
              key={v}
              className={cn(
                "h-1 w-0.5 rounded",
                step === v ? (v < 0 ? "bg-blue-500" : v > 0 ? "bg-amber-500" : "bg-gray-500") : "bg-gray-300 dark:bg-gray-600"
              )}
            />
          ))}
        </div>
      </div>
      {!isSet && (
        <p className="text-xs text-center text-gray-400 italic">Trascina lo slider per indicare quale risposta ha esperti più autorevoli</p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

export function SurveyModal({ isOpen, onClose, evaluatorId }: SurveyModalProps) {
  const [step, setStep] = useState<SurveyStep>("select");
  const [pendingChats, setPendingChats] = useState<PendingChat[]>([]);
  const [evaluatedIds, setEvaluatedIds] = useState<Set<string>>(new Set());
  const [selectedChat, setSelectedChat] = useState<PendingChat | null>(null);
  const [chatDetails, setChatDetails] = useState<ChatDetails | null>(null);

  // A/B form state
  const [formState, setFormState] = useState<SurveyFormState>(getInitialSurveyFormState());
  const [localAbAssignment, setLocalAbAssignment] = useState<Record<string, string> | null>(null);
  const [currentCategory, setCurrentCategory] = useState(0);

  // Simple rating form state
  const [simpleFormState, setSimpleFormState] = useState<SimpleRatingFormState>(getInitialSimpleRatingFormState());

  const [baselineExperts, setBaselineExperts] = useState<Expert[]>([]);
  const [isLoadingBaselineExperts, setIsLoadingBaselineExperts] = useState(false);
  const [sampledCitationsA, setSampledCitationsA] = useState<Citation[]>([]);

  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mobileSimpleTab, setMobileSimpleTab] = useState<"response" | "form">("response");
  const [mobileABTab, setMobileABTab] = useState<"A" | "B" | "valuta">("A");


  // Group A/B questions by category (exclude overall_satisfaction - handled separately)
  const categories = SURVEY_QUESTIONS.filter(q => q.id !== "overall_satisfaction").reduce((acc, q) => {
    if (!acc.find((c) => c.name === q.category)) {
      acc.push({ name: q.category, questions: [] });
    }
    acc.find((c) => c.name === q.category)?.questions.push(q);
    return acc;
  }, [] as { name: string; questions: typeof SURVEY_QUESTIONS }[]);

  categories.push({
    name: "Valutazione Complessiva",
    questions: SURVEY_QUESTIONS.filter(q => q.id === "overall_satisfaction"),
  });

  // Get response A and B based on localAbAssignment
  const getResponseA = (): string => {
    if (!chatDetails || !localAbAssignment || !selectedChat) return chatDetails?.answer || "";
    return localAbAssignment["A"] === "system"
      ? chatDetails.answer
      : (selectedChat.baseline_answer || "");
  };

  const getResponseB = (): string => {
    if (!chatDetails || !localAbAssignment || !selectedChat) return "";
    return localAbAssignment["B"] === "system"
      ? chatDetails.answer
      : (selectedChat.baseline_answer || "");
  };

  // Load pending chats
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [pendingRes, evaluatedRes] = await Promise.all([
        getPendingChats(evaluatorId),
        getEvaluatedChatIds(evaluatorId),
      ]);
      setPendingChats(pendingRes.pending);
      setEvaluatedIds(new Set(evaluatedRes.chat_ids));
    } catch (err) {
      setError("Errore nel caricamento delle conversazioni");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [evaluatorId]);

  // Load chat details (system answer text)
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

  // Load baseline experts: deputies mentioned in baseline text with their authority scores.
  // Passes the baseline text in the POST body so the backend can always find names,
  // even for older chats where c.baseline_answer may be empty in Neo4j.
  const loadBaselineExperts = useCallback(async (chatId: string, baselineText: string) => {
    setIsLoadingBaselineExperts(true);
    setBaselineExperts([]);
    try {
      const res = await fetch(`${config.api.baseUrl}/history/${chatId}/baseline-experts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline_text: baselineText }),
      });
      if (!res.ok) throw new Error("Failed to load baseline experts");
      const data = await res.json();
      setBaselineExperts(data.experts ?? []);
    } catch (err) {
      console.error("Failed to load baseline experts:", err);
      setBaselineExperts([]);
    } finally {
      setIsLoadingBaselineExperts(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadData();
      setStep("select");
      setSelectedChat(null);
      setChatDetails(null);
      setBaselineExperts([]);
      setFormState(getInitialSurveyFormState());
      setSimpleFormState(getInitialSimpleRatingFormState());
      setLocalAbAssignment(null);
      setCurrentCategory(0);
      setSampledCitationsA([]);
    }
  }, [isOpen, loadData]);

  // Handle chat selection — branch on evaluation_type
  const handleSelectChat = async (chat: PendingChat) => {
    setSelectedChat(chat);
    setError(null);

    if (chat.evaluation_type === "ab") {
      // Generate a random A/B assignment for this session
      const assignment = Math.random() < 0.5
        ? { A: "system", B: "baseline" }
        : { A: "baseline", B: "system" };
      setLocalAbAssignment(assignment);
      setFormState(getInitialSurveyFormState());
      setCurrentCategory(0);
      setMobileABTab("A");
      setBaselineExperts([]);
      setStep("form");
      // Load system answer and baseline experts in parallel.
      // Pass the baseline text from the chat object (sourced from evaluation_set.json)
      // so the endpoint can always find deputy names regardless of Neo4j state.
      await Promise.all([
        loadChatDetails(chat.id),
        loadBaselineExperts(chat.id, chat.baseline_answer || ""),
      ]);
    } else {
      // Simple Likert rating
      setSimpleFormState(getInitialSimpleRatingFormState());
      setMobileSimpleTab("response");
      setStep("simple_form");
      await loadChatDetails(chat.id);
    }
  };

  // A/B form helpers
  const inferPreference = (a: number, b: number): "A" | "B" | "equal" | "" => {
    if (a === 0 || b === 0) return "";
    if (a > b) return "A";
    if (b > a) return "B";
    return "equal";
  };

  const handleABRatingChange = (
    dimension: ABDimension,
    field: keyof ABRating,
    value: number | string
  ) => {
    setFormState((prev) => {
      const cur = prev[dimension];
      const newA = field === "rating_a" ? (value as number) : cur.rating_a;
      const newB = field === "rating_b" ? (value as number) : cur.rating_b;
      return {
        ...prev,
        [dimension]: {
          ...cur,
          [field]: value,
          // Auto-infer preference when a numeric rating changes
          preference: (field === "rating_a" || field === "rating_b")
            ? inferPreference(newA, newB)
            : cur.preference,
        },
      };
    });
  };

  const isABRatingComplete = (rating: ABRating): boolean => {
    return rating.rating_a > 0 && rating.rating_b > 0;
  };

  const isCategoryComplete = (catIndex: number) => {
    const cat = categories[catIndex];
    if (cat.name === "Valutazione Complessiva") {
      return formState.overall_satisfaction_a > 0 &&
             formState.overall_satisfaction_b > 0;
    }
    return cat.questions.every((q) => {
      const rating = formState[q.id as ABDimension];
      return isABRatingComplete(rating);
    });
  };

  const isFormComplete = () => {
    const dimensionsComplete = AB_DIMENSIONS.every((dim) =>
      isABRatingComplete(formState[dim])
    );
    const overallComplete = formState.overall_satisfaction_a > 0 &&
                           formState.overall_satisfaction_b > 0;
    return dimensionsComplete && overallComplete;
  };

  const completionPercentage = () => {
    const total = AB_DIMENSIONS.length + 1;
    let filled = 0;
    for (const dim of AB_DIMENSIONS) {
      if (isABRatingComplete(formState[dim])) filled++;
    }
    if (formState.overall_satisfaction_a > 0 && formState.overall_satisfaction_b > 0) {
      filled++;
    }
    return Math.round((filled / total) * 100);
  };

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

  const handleGoToCitations = () => {
    if (!isFormComplete()) return;
    // Always use system citations (chatDetails.citations), ignoring A/B assignment.
    // Sample up to 3 random citations to keep the evaluation short.
    const allSystemCitations: Citation[] = chatDetails?.citations ?? [];
    const sampled = allSystemCitations.length <= 3
      ? allSystemCitations
      : [...allSystemCitations].sort(() => Math.random() - 0.5).slice(0, 3);
    setSampledCitationsA(sampled);
    if (formState.citation_evaluations_a.length === 0 && sampled.length > 0) {
      setFormState(prev => ({
        ...prev,
        citation_evaluations_a: sampled.map(c => getInitialCitationEvaluation(c.chunk_id)),
        citation_evaluations_b: [],
      }));
    }
    setStep("citations");
  };

  // Submit A/B survey
  const handleSubmit = async () => {
    if (!selectedChat || !isFormComplete()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const validCitEvalsA = formState.citation_evaluations_a.filter(
        ce => ce.relevance > 0 && ce.faithfulness > 0 && ce.informativeness > 0 && ce.attribution !== ""
      );
      const validCitEvalsB = formState.citation_evaluations_b.filter(
        ce => ce.relevance > 0 && ce.faithfulness > 0 && ce.informativeness > 0 && ce.attribution !== ""
      );

      // Compute baseline authority avg from baseline experts
      const baselineExpertList = baselineExperts.filter(e => e.authority_score > 0);
      const baselineAuthAvg = baselineExpertList.length > 0
        ? baselineExpertList.reduce((sum, e) => sum + e.authority_score, 0) / baselineExpertList.length
        : undefined;

      await createSurvey({
        chat_id: selectedChat.id,
        answer_quality: formState.answer_quality,
        answer_clarity: formState.answer_clarity,
        answer_completeness: formState.answer_completeness,
        citations_relevance: formState.citations_relevance,
        citations_accuracy: formState.citations_accuracy,
        balance_perception: formState.balance_perception,
        balance_fairness: formState.balance_fairness,
        source_relevance: formState.source_relevance,
        source_authority: formState.source_authority,
        source_coverage: formState.source_coverage,
        overall_satisfaction_a: formState.overall_satisfaction_a,
        overall_satisfaction_b: formState.overall_satisfaction_b,
        overall_preference: formState.overall_preference as "A" | "B" | "equal",
        would_recommend: formState.would_recommend,
        feedback_positive: formState.feedback_positive || undefined,
        feedback_improvement: formState.feedback_improvement || undefined,
        citation_evaluations_a: validCitEvalsA,
        citation_evaluations_b: validCitEvalsB,
        // Pass evaluation_set assignment for de-blinding
        ab_assignment: localAbAssignment || undefined,
        evaluation_set_topic: selectedChat.matched_topic || undefined,
        evaluator_id: evaluatorId || undefined,
        baseline_authority_avg: baselineAuthAvg,
      });

      setStep("success");
    } catch (err: any) {
      setError(err.message || "Errore nell'invio della valutazione");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Submit simple Likert rating
  const handleSimpleSubmit = async () => {
    if (!selectedChat) return;
    const { answer_clarity, answer_quality, balance_perception, balance_fairness } = simpleFormState;
    if (!answer_clarity || !answer_quality || !balance_perception || !balance_fairness) {
      setError("Compila tutte le valutazioni prima di inviare");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await createSimpleRating({
        chat_id: selectedChat.id,
        answer_clarity,
        answer_quality,
        balance_perception,
        balance_fairness,
        feedback: simpleFormState.feedback || undefined,
        evaluator_id: evaluatorId || undefined,
      });
      setStep("success");
    } catch (err: any) {
      setError(err.message || "Errore nell'invio della valutazione");
    } finally {
      setIsSubmitting(false);
    }
  };

  const isSimpleFormComplete = () => {
    const { answer_clarity, answer_quality, balance_perception, balance_fairness } = simpleFormState;
    return answer_clarity > 0 && answer_quality > 0 && balance_perception > 0 && balance_fairness > 0;
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

  // Render both responses as plain text with identical styling.
  // Strips citation markers and markdown syntax so both panels look the same
  // regardless of whether the source has markdown or is plain text.
  const renderContent = (text: string) => {
    const cleaned = text
      .replace(/\[«([^»]+)»\]\([^)]+\)/g, '"$1"') // [«quote»](url) → "quote"
      .replace(/\(leg\d+_[^)]+\)/g, "")            // remove (legXX_...) refs
      .replace(/\[CIT:[^\]]+\]/g, "")              // remove [CIT:...] markers
      .replace(/«([^»]+)»/g, '"$1"')               // bare «quote» → "quote"
      // Ensure heading lines are on their own paragraph (add surrounding newlines)
      .replace(/^(#{1,6}\s+.+)$/gm, "\n$1\n")
      .replace(/^#{1,6}\s+/gm, "")                 // strip ## prefix, keep text
      .replace(/\*\*([^*]+)\*\*/g, "$1")           // **bold** → plain
      .replace(/\*([^*]+)\*/g, "$1")               // *italic* → plain
      .replace(/^[-*]\s+/gm, "• ");                // - list → bullet

    const lines = cleaned.split("\n");
    const elements: React.ReactNode[] = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i].trim();
      if (!line) {
        // Collapse multiple blank lines into a single spacer
        if (elements.length > 0 && elements[elements.length - 1] !== null) {
          elements.push(<div key={`sp-${i}`} className="h-2" />);
        }
      } else {
        elements.push(
          <p key={i} className="text-sm text-foreground leading-relaxed mb-1">
            {line}
          </p>
        );
      }
      i++;
    }
    return <>{elements}</>;
  };

  // Determine dialog title based on step
  const dialogTitle = () => {
    switch (step) {
      case "simple_form": return "Valutazione Risposta";
      case "citations": return "Valutazione Citazioni";
      default: return "Valutazione A/B Blind";
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className={cn(
          "p-0 gap-0 overflow-hidden flex flex-col",
          (step === "form" || step === "citations") && "sm:!max-w-[95vw]"
        )}
        style={
          step === "form"
            ? { width: "1600px", maxWidth: "95vw", height: "95vh", maxHeight: "95vh" }
            : step === "simple_form"
            ? { width: "900px", maxWidth: "95vw", height: "90vh", maxHeight: "90vh" }
            : step === "citations"
            ? { width: "700px", maxWidth: "95vw", height: "95vh", maxHeight: "95vh" }
            : { maxWidth: "42rem", maxHeight: "90vh" }
        }
      >
        <DialogHeader className="px-6 py-4 border-b bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
          <DialogTitle className="flex items-center gap-2 text-lg">
            <ClipboardCheck className="w-5 h-5 text-blue-600" />
            {dialogTitle()}
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
          {step === "citations" && (
            <p className="text-sm text-gray-500 mt-1">
              Valuta ogni citazione singolarmente (opzionale - puoi saltare)
            </p>
          )}
        </DialogHeader>

        {/* Step: Select Chat */}
        {step === "select" && (
          <div className="flex flex-col h-[60vh]">
            <div className="px-6 py-3 bg-gray-50 dark:bg-gray-900/50 border-b">
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {evaluatorId ? (
                    <>Ciao <span className="font-semibold text-gray-800 dark:text-gray-200">{evaluatorId}</span> — seleziona una conversazione da valutare</>
                  ) : (
                    "Seleziona una conversazione da valutare"
                  )}
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
                      <p className="text-sm mt-1 text-center max-w-xs">
                        Non ci sono ancora conversazioni da valutare. Usa la chat per generarne.
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {pendingChats.map((chat) => (
                    <Card
                      key={chat.id}
                      className={cn(
                        "cursor-pointer transition-all duration-200 hover:shadow-md",
                        chat.evaluation_type === "ab"
                          ? "hover:border-blue-300 dark:hover:border-blue-700"
                          : "hover:border-purple-300 dark:hover:border-purple-700"
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
                          <div className="flex flex-col items-end gap-2 shrink-0">
                            <Badge variant="outline" className="text-xs whitespace-nowrap">
                              {formatDate(chat.timestamp)}
                            </Badge>
                            {chat.evaluation_type === "ab" ? (
                              <Badge className="text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200">
                                A/B
                                {chat.matched_topic && <span className="ml-1 opacity-70">· {chat.matched_topic}</span>}
                              </Badge>
                            ) : (
                              <Badge className="text-xs bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 border-purple-200">
                                <BarChart2 className="w-3 h-3 mr-1" />
                                Likert
                              </Badge>
                            )}
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
                <span>
                  {pendingChats.filter(c => c.evaluation_type === "ab").length} A/B
                  {" · "}
                  {pendingChats.filter(c => c.evaluation_type === "simple").length} Likert
                  {" da valutare"}
                </span>
                <span>{evaluatedIds.size} gia valutate</span>
              </div>
            </div>
          </div>
        )}

        {/* Step: A/B Survey Form */}
        {step === "form" && selectedChat && (
          <div className="flex flex-col flex-1 min-h-0">

            {/* ── MOBILE LAYOUT (hidden on md+) ── */}
            <div className="md:hidden flex flex-col flex-1 min-h-0">
              {/* Question header */}
              <div className="px-4 py-2.5 bg-blue-50 dark:bg-blue-950/30 border-b shrink-0">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100 line-clamp-2">
                  <span className="text-blue-600 dark:text-blue-400">Domanda:</span> {selectedChat.query}
                </p>
                {selectedChat.matched_topic && (
                  <p className="text-xs text-blue-500 mt-0.5">Confronto su: {selectedChat.matched_topic}</p>
                )}
              </div>

              {/* 3-tab bar */}
              <div className="flex shrink-0 border-b bg-white dark:bg-gray-950">
                {(["A", "B", "valuta"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setMobileABTab(tab)}
                    className={cn(
                      "flex-1 py-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px inline-flex items-center justify-center gap-1",
                      mobileABTab === tab
                        ? tab === "A"
                          ? "border-blue-500 text-blue-700 dark:text-blue-300"
                          : tab === "B"
                          ? "border-amber-500 text-amber-700 dark:text-amber-300"
                          : "border-indigo-500 text-indigo-700 dark:text-indigo-300"
                        : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                    )}
                  >
                    {tab === "A" && "Risposta A"}
                    {tab === "B" && "Risposta B"}
                    {tab === "valuta" && (
                      <>
                        Valuta
                        {completionPercentage() === 100 && <Check className="w-3.5 h-3.5 text-emerald-500" />}
                      </>
                    )}
                  </button>
                ))}
              </div>

              {/* Response tabs content */}
              {(mobileABTab === "A" || mobileABTab === "B") && (
                <ScrollArea className="flex-1 min-h-0 px-4 py-4">
                  {isLoadingDetails ? (
                    <div className="flex items-center justify-center h-40">
                      <Loader2 className={cn("w-6 h-6 animate-spin", mobileABTab === "A" ? "text-blue-500" : "text-amber-500")} />
                    </div>
                  ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                      {mobileABTab === "A" ? renderContent(getResponseA()) : renderContent(getResponseB())}
                    </div>
                  )}
                </ScrollArea>
              )}

              {/* Valuta tab content */}
              {mobileABTab === "valuta" && (
                <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
                  {/* Category progress: numbered dots + current category name */}
                  <div className="px-4 py-3 bg-white dark:bg-gray-950 border-b shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1.5 shrink-0">
                        {categories.map((_, idx) => (
                          <button
                            key={idx}
                            onClick={() => setCurrentCategory(idx)}
                            className={cn(
                              "w-6 h-6 rounded-full text-xs font-semibold transition-colors flex items-center justify-center",
                              idx === currentCategory
                                ? "bg-blue-500 text-white shadow-sm"
                                : isCategoryComplete(idx)
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 ring-2 ring-emerald-400 ring-offset-1"
                                : "bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                            )}
                          >
                            {isCategoryComplete(idx)
                              ? <Check className="w-3 h-3" />
                              : idx + 1}
                          </button>
                        ))}
                      </div>
                      <div className="flex items-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 min-w-0">
                        <span className="shrink-0">{CATEGORY_ICONS[categories[currentCategory]?.name]}</span>
                        <span className="truncate">{categories[currentCategory]?.name}</span>
                      </div>
                    </div>
                  </div>

                  <ScrollArea className="flex-1 min-h-0 px-4 py-4">
                    <div className="space-y-4">
                      {categories[currentCategory].name === "Autorità Esperti" && (
                        <div className="p-3 bg-indigo-50 dark:bg-indigo-950/30 rounded-lg border border-indigo-200 dark:border-indigo-800 text-xs text-indigo-700 dark:text-indigo-300">
                          <p className="font-semibold flex items-center gap-1.5 mb-1">
                            <UserCheck className="w-3.5 h-3.5" />
                            Valutazione autorità delle fonti
                          </p>
                          <p>Valuta la qualità e l'autorità delle fonti esperte citate nelle due risposte.</p>
                        </div>
                      )}
                      {categories[currentCategory].name !== "Valutazione Complessiva" ? (
                        categories[currentCategory].questions.map((question) => {
                          const dim = question.id as ABDimension;
                          const rating = formState[dim];
                          const isAuthority = categories[currentCategory].name === "Autorità Esperti";
                          return (
                            <div key={question.id} className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                              <div>
                                <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{question.question}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{question.description}</p>
                              </div>
                              {isAuthority ? (
                                <ComparativeSlider
                                  ratingA={rating.rating_a}
                                  ratingB={rating.rating_b}
                                  onChange={(ra, rb, pref) => setFormState(prev => ({
                                    ...prev,
                                    [dim]: { rating_a: ra, rating_b: rb, preference: pref },
                                  }))}
                                />
                              ) : (
                                <div className="space-y-2.5">
                                  <div className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold text-blue-600">Risposta A</span>
                                    <StarRating value={rating.rating_a} onChange={(val) => handleABRatingChange(dim, "rating_a", val)} size="md" />
                                  </div>
                                  <div className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold text-amber-600">Risposta B</span>
                                    <StarRating value={rating.rating_b} onChange={(val) => handleABRatingChange(dim, "rating_b", val)} size="md" />
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })
                      ) : (
                        <>
                          <div className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                            <p className="font-medium text-sm text-gray-900 dark:text-gray-100">Soddisfazione complessiva</p>
                            <div className="space-y-2.5">
                              <div className="flex flex-col gap-1">
                                <span className="text-xs font-semibold text-blue-600">Risposta A</span>
                                <StarRating value={formState.overall_satisfaction_a}
                                  onChange={(val) => setFormState(prev => ({
                                    ...prev,
                                    overall_satisfaction_a: val,
                                    overall_preference: inferPreference(val, prev.overall_satisfaction_b),
                                  }))} size="md" />
                              </div>
                              <div className="flex flex-col gap-1">
                                <span className="text-xs font-semibold text-amber-600">Risposta B</span>
                                <StarRating value={formState.overall_satisfaction_b}
                                  onChange={(val) => setFormState(prev => ({
                                    ...prev,
                                    overall_satisfaction_b: val,
                                    overall_preference: inferPreference(prev.overall_satisfaction_a, val),
                                  }))} size="md" />
                              </div>
                            </div>
                          </div>
                          <div className="p-4 bg-white dark:bg-gray-950 rounded-lg border">
                            <p className="font-medium text-sm text-gray-900 dark:text-gray-100 mb-3">
                              Consiglieresti questo sistema?
                            </p>
                            <div className="flex gap-3">
                              <Button type="button"
                                variant={formState.would_recommend ? "default" : "outline"}
                                onClick={() => setFormState(prev => ({ ...prev, would_recommend: true }))}
                                className={cn("flex-1", formState.would_recommend && "bg-emerald-600 hover:bg-emerald-700")}>
                                <ThumbsUp className="w-4 h-4 mr-1" /> Sì
                              </Button>
                              <Button type="button"
                                variant={!formState.would_recommend ? "default" : "outline"}
                                onClick={() => setFormState(prev => ({ ...prev, would_recommend: false }))}
                                className={cn("flex-1", !formState.would_recommend && "bg-gray-600 hover:bg-gray-700")}>
                                No
                              </Button>
                            </div>
                          </div>
                          <div className="p-4 bg-white dark:bg-gray-950 rounded-lg border space-y-4">
                            <div className="space-y-2">
                              <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Cosa ha funzionato bene? (opzionale)</label>
                              <Textarea placeholder="Aspetti positivi..." value={formState.feedback_positive}
                                onChange={(e) => setFormState(prev => ({ ...prev, feedback_positive: e.target.value }))}
                                className="min-h-[70px] resize-none" />
                            </div>
                            <div className="space-y-2">
                              <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Suggerimenti? (opzionale)</label>
                              <Textarea placeholder="Come migliorare..." value={formState.feedback_improvement}
                                onChange={(e) => setFormState(prev => ({ ...prev, feedback_improvement: e.target.value }))}
                                className="min-h-[70px] resize-none" />
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              )}

              {/* Mobile footer */}
              <div className="px-4 py-3 border-t bg-white dark:bg-gray-950 shrink-0">
                {error && (
                  <div className="mb-2 p-2 bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 text-xs rounded-lg flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" /> {error}
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <Button variant="ghost" size="sm"
                    onClick={() => {
                      if (mobileABTab !== "valuta") {
                        setStep("select");
                      } else if (currentCategory === 0) {
                        setMobileABTab("A");
                      } else {
                        goToPrevCategory();
                      }
                    }}>
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    {mobileABTab !== "valuta" ? "Indietro" : currentCategory === 0 ? "Risposte" : "Precedente"}
                  </Button>
                  {mobileABTab !== "valuta" ? (
                    <Button size="sm" onClick={() => setMobileABTab("valuta")}>
                      Valuta <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  ) : currentCategory < categories.length - 1 ? (
                    <Button size="sm" onClick={goToNextCategory} disabled={!isCategoryComplete(currentCategory)}>
                      Avanti <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  ) : (
                    <Button size="sm" onClick={handleGoToCitations} disabled={!isFormComplete()}
                      className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700">
                      Citazioni <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {/* ── DESKTOP LAYOUT (hidden on mobile) ── */}
            <div className="hidden md:flex flex-row flex-1 min-h-0">
              {/* Left Panel: Side-by-side A/B Responses */}
              <div className="md:w-3/5 md:border-r flex flex-col bg-white dark:bg-gray-950 min-h-0 overflow-hidden">
                <div className="px-4 py-3 bg-blue-50 dark:bg-blue-950/30 border-b">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-100 line-clamp-2">
                    <span className="text-blue-600 dark:text-blue-400">Domanda:</span> {selectedChat.query}
                  </p>
                  {selectedChat.matched_topic && (
                    <p className="text-xs text-blue-500 mt-0.5">Confronto su: {selectedChat.matched_topic}</p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">
                    Confronta le due risposte. Non sai quale sia il sistema avanzato e quale la baseline.
                  </p>
                </div>
                <div className="flex flex-1 min-h-0 overflow-hidden">
                  {categories[currentCategory]?.name === "Autorità Esperti" ? (
                    <AuthorityGroupComparisonPanel
                      expertsA={localAbAssignment?.["A"] === "system" ? (chatDetails?.experts ?? []) : baselineExperts}
                      expertsB={localAbAssignment?.["B"] === "system" ? (chatDetails?.experts ?? []) : baselineExperts}
                      isLoadingA={localAbAssignment?.["A"] === "system" ? isLoadingDetails : isLoadingBaselineExperts}
                      isLoadingB={localAbAssignment?.["B"] === "system" ? isLoadingDetails : isLoadingBaselineExperts}
                    />
                  ) : (
                    <>
                      <div className="flex w-1/2 border-r flex-col min-h-0">
                        <div className="px-3 py-2 bg-blue-100 dark:bg-blue-900/30 border-b text-center shrink-0">
                          <span className="font-semibold text-blue-700 dark:text-blue-300 text-sm">Risposta A</span>
                        </div>
                        <ScrollArea className="flex-1 px-3 py-3">
                          {isLoadingDetails ? (
                            <div className="flex items-center justify-center h-40">
                              <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                            </div>
                          ) : (
                            <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                              {renderContent(getResponseA())}
                            </div>
                          )}
                        </ScrollArea>
                      </div>
                      <div className="flex w-1/2 flex-col min-h-0">
                        <div className="px-3 py-2 bg-amber-100 dark:bg-amber-900/30 border-b text-center shrink-0">
                          <span className="font-semibold text-amber-700 dark:text-amber-300 text-sm">Risposta B</span>
                        </div>
                        <ScrollArea className="flex-1 px-3 py-3">
                          {isLoadingDetails ? (
                            <div className="flex items-center justify-center h-40">
                              <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                            </div>
                          ) : (
                            <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                              {renderContent(getResponseB())}
                            </div>
                          )}
                        </ScrollArea>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Right Panel: A/B Survey Form */}
              <div className="md:w-2/5 flex flex-col bg-gray-50 dark:bg-gray-900/30 min-h-0 overflow-hidden">
                {/* Category tabs (desktop: full names with icons, no overflow) */}
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
                      {isCategoryComplete(idx) && <Check className="w-3.5 h-3.5 text-emerald-500" />}
                    </button>
                  ))}
                </div>

                <ScrollArea className="flex-1 min-h-0 px-4 py-4">
                  <div className="space-y-5">
                    {categories[currentCategory].name !== "Valutazione Complessiva" ? (
                      categories[currentCategory].questions.map((question) => {
                        const dim = question.id as ABDimension;
                        const rating = formState[dim];
                        const isAuthority = categories[currentCategory].name === "Autorità Esperti";
                        return (
                          <div key={question.id} className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                            <div>
                              <p className="font-medium text-gray-900 dark:text-gray-100">{question.question}</p>
                              <p className="text-sm text-gray-500 dark:text-gray-400">{question.description}</p>
                            </div>
                            {isAuthority ? (
                              <ComparativeSlider
                                ratingA={rating.rating_a}
                                ratingB={rating.rating_b}
                                onChange={(ra, rb, pref) => setFormState(prev => ({
                                  ...prev,
                                  [dim]: { rating_a: ra, rating_b: rb, preference: pref },
                                }))}
                              />
                            ) : (
                              <>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm font-semibold text-blue-600 w-24">Risposta A</span>
                                  <StarRating value={rating.rating_a} onChange={(val) => handleABRatingChange(dim, "rating_a", val)} size="md" />
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm font-semibold text-amber-600 w-24">Risposta B</span>
                                  <StarRating value={rating.rating_b} onChange={(val) => handleABRatingChange(dim, "rating_b", val)} size="md" />
                                </div>
                              </>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <>
                        <div className="space-y-3 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                          <p className="font-medium text-gray-900 dark:text-gray-100">Soddisfazione complessiva</p>
                          <p className="text-sm text-gray-500 dark:text-gray-400">Valutazione generale dell'esperienza</p>
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold text-blue-600 w-24">Risposta A</span>
                            <StarRating value={formState.overall_satisfaction_a}
                              onChange={(val) => setFormState(prev => ({
                                ...prev,
                                overall_satisfaction_a: val,
                                overall_preference: inferPreference(val, prev.overall_satisfaction_b),
                              }))} size="md" />
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-semibold text-amber-600 w-24">Risposta B</span>
                            <StarRating value={formState.overall_satisfaction_b}
                              onChange={(val) => setFormState(prev => ({
                                ...prev,
                                overall_satisfaction_b: val,
                                overall_preference: inferPreference(prev.overall_satisfaction_a, val),
                              }))} size="md" />
                          </div>
                        </div>

                        <Separator className="my-4" />

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

                        <div className="space-y-4 p-4 bg-white dark:bg-gray-950 rounded-lg border">
                          <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Cosa ha funzionato bene? (opzionale)</label>
                            <Textarea placeholder="Descrivi gli aspetti positivi..." value={formState.feedback_positive}
                              onChange={(e) => setFormState(prev => ({ ...prev, feedback_positive: e.target.value }))}
                              className="min-h-[80px] resize-none" />
                          </div>
                          <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Suggerimenti per migliorare? (opzionale)</label>
                            <Textarea placeholder="Come potremmo migliorare il sistema..." value={formState.feedback_improvement}
                              onChange={(e) => setFormState(prev => ({ ...prev, feedback_improvement: e.target.value }))}
                              className="min-h-[80px] resize-none" />
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </ScrollArea>

                <div className="px-4 py-4 border-t bg-white dark:bg-gray-950">
                  {error && (
                    <div className="mb-3 p-2 bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 text-sm rounded-lg flex items-center gap-2">
                      <AlertCircle className="w-4 h-4" />
                      {error}
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <Button variant="ghost" onClick={() => currentCategory === 0 ? setStep("select") : goToPrevCategory()}>
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      {currentCategory === 0 ? "Indietro" : "Precedente"}
                    </Button>
                    {currentCategory < categories.length - 1 ? (
                      <Button onClick={goToNextCategory} disabled={!isCategoryComplete(currentCategory)}>
                        Avanti <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    ) : (
                      <Button onClick={handleGoToCitations} disabled={!isFormComplete()}
                        className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700">
                        Valuta Citazioni <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step: Simple Likert Form */}
        {step === "simple_form" && selectedChat && (
          <div className="flex flex-col flex-1 min-h-0">

            {/* ── MOBILE: tab layout ── */}
            <div className="md:hidden flex flex-col flex-1 min-h-0">
              {/* Question header */}
              <div className="px-4 py-2.5 bg-purple-50 dark:bg-purple-950/30 border-b shrink-0">
                <p className="text-sm font-medium text-purple-900 dark:text-purple-100 line-clamp-2">
                  <span className="text-purple-600 dark:text-purple-400">Domanda:</span> {selectedChat.query}
                </p>
              </div>

              {/* Tab bar */}
              <div className="flex shrink-0 border-b bg-white dark:bg-gray-950">
                <button
                  onClick={() => setMobileSimpleTab("response")}
                  className={cn(
                    "flex-1 py-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px",
                    mobileSimpleTab === "response"
                      ? "border-purple-500 text-purple-700 dark:text-purple-300"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  )}
                >
                  Risposta
                </button>
                <button
                  onClick={() => setMobileSimpleTab("form")}
                  className={cn(
                    "flex-1 py-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px inline-flex items-center justify-center gap-1.5",
                    mobileSimpleTab === "form"
                      ? "border-purple-500 text-purple-700 dark:text-purple-300"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  )}
                >
                  Valuta
                  {isSimpleFormComplete() && <Check className="w-3.5 h-3.5 text-emerald-500" />}
                </button>
              </div>

              {/* Tab content */}
              <ScrollArea className="flex-1 min-h-0">
                {mobileSimpleTab === "response" ? (
                  <div className="px-4 py-4">
                    {isLoadingDetails ? (
                      <div className="flex items-center justify-center h-40">
                        <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
                      </div>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                        {chatDetails ? renderContent(chatDetails.answer) : null}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="px-4 py-4 space-y-4">
                    {SIMPLE_DIMENSIONS.map((dim) => (
                      <div key={dim} className="p-4 bg-white dark:bg-gray-950 rounded-lg border space-y-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {SIMPLE_DIMENSION_LABELS[dim]}
                        </p>
                        <StarRating
                          value={simpleFormState[dim]}
                          onChange={(val) => setSimpleFormState(prev => ({ ...prev, [dim]: val }))}
                          size="lg"
                        />
                      </div>
                    ))}
                    <div className="p-4 bg-white dark:bg-gray-950 rounded-lg border space-y-2">
                      <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Commento libero (opzionale)
                      </label>
                      <Textarea
                        placeholder="Osservazioni sulla risposta..."
                        value={simpleFormState.feedback}
                        onChange={(e) => setSimpleFormState(prev => ({ ...prev, feedback: e.target.value }))}
                        className="min-h-[80px] resize-none"
                      />
                    </div>
                  </div>
                )}
              </ScrollArea>
            </div>

            {/* ── DESKTOP: side-by-side layout ── */}
            <div className="hidden md:flex flex-1 min-h-0">
              {/* Left: System Response */}
              <div className="w-1/2 border-r flex flex-col bg-white dark:bg-gray-950 min-h-0 overflow-hidden">
                <div className="px-4 py-2 bg-purple-50 dark:bg-purple-950/30 border-b shrink-0">
                  <p className="text-sm font-medium text-purple-900 dark:text-purple-100 line-clamp-2">
                    <span className="text-purple-600 dark:text-purple-400">Domanda:</span> {selectedChat.query}
                  </p>
                </div>
                <ScrollArea className="flex-1 px-4 py-4">
                  {isLoadingDetails ? (
                    <div className="flex items-center justify-center h-40">
                      <Loader2 className="w-6 h-6 animate-spin text-purple-500" />
                    </div>
                  ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                      {chatDetails ? renderContent(chatDetails.answer) : null}
                    </div>
                  )}
                </ScrollArea>
              </div>

              {/* Right: Simple Rating Form */}
              <div className="w-1/2 flex flex-col bg-gray-50 dark:bg-gray-900/30 min-h-0 overflow-hidden">
                <div className="px-4 py-3 border-b bg-white dark:bg-gray-950 shrink-0">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Valuta la risposta del sistema su 4 dimensioni
                  </p>
                </div>
                <ScrollArea className="flex-1 px-4 py-4">
                  <div className="space-y-4">
                    {SIMPLE_DIMENSIONS.map((dim) => (
                      <div key={dim} className="p-4 bg-white dark:bg-gray-950 rounded-lg border space-y-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {SIMPLE_DIMENSION_LABELS[dim]}
                        </p>
                        <StarRating
                          value={simpleFormState[dim]}
                          onChange={(val) => setSimpleFormState(prev => ({ ...prev, [dim]: val }))}
                          size="lg"
                        />
                      </div>
                    ))}
                    <div className="p-4 bg-white dark:bg-gray-950 rounded-lg border space-y-2">
                      <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Commento libero (opzionale)
                      </label>
                      <Textarea
                        placeholder="Osservazioni sulla risposta..."
                        value={simpleFormState.feedback}
                        onChange={(e) => setSimpleFormState(prev => ({ ...prev, feedback: e.target.value }))}
                        className="min-h-[80px] resize-none"
                      />
                    </div>
                  </div>
                </ScrollArea>
              </div>
            </div>

            {/* Footer — sempre visibile su mobile e desktop */}
            <div className="px-4 py-4 border-t bg-white dark:bg-gray-950 shrink-0">
              {error && (
                <div className="mb-3 p-2 bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 text-sm rounded-lg flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  {error}
                </div>
              )}
              <div className="flex items-center justify-between">
                <Button variant="ghost" onClick={() => setStep("select")}>
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Indietro
                </Button>
                <Button
                  onClick={handleSimpleSubmit}
                  disabled={!isSimpleFormComplete() || isSubmitting}
                  className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700"
                >
                  {isSubmitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Invia Valutazione
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Step: Citation Review */}
        {step === "citations" && (
          <div className="flex flex-col h-[80vh]">
            <CitationReviewStep
              citationsA={sampledCitationsA}
              citationsB={[]}
              responseTextA={getResponseA()}
              responseTextB={getResponseB()}
              evaluationsA={formState.citation_evaluations_a}
              evaluationsB={formState.citation_evaluations_b}
              onUpdateEvaluationA={(index, evaluation) => {
                setFormState(prev => {
                  const updated = [...prev.citation_evaluations_a];
                  updated[index] = evaluation;
                  return { ...prev, citation_evaluations_a: updated };
                });
              }}
              onUpdateEvaluationB={(index, evaluation) => {
                setFormState(prev => {
                  const updated = [...prev.citation_evaluations_b];
                  updated[index] = evaluation;
                  return { ...prev, citation_evaluations_b: updated };
                });
              }}
              onSubmit={handleSubmit}
              onSkip={() => {
                setFormState(prev => ({
                  ...prev,
                  citation_evaluations_a: [],
                  citation_evaluations_b: [],
                }));
                handleSubmit();
              }}
              onBack={() => {
                setStep("form");
                setCurrentCategory(categories.length - 1);
              }}
              isSubmitting={isSubmitting}
            />
            {error && (
              <div className="px-4 py-2 bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 text-sm flex items-center gap-2 border-t">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
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
              Il tuo feedback e prezioso per migliorare il sistema.
            </p>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => { setStep("select"); loadData(); }}>
                Valuta altra conversazione
              </Button>
              <Button onClick={onClose}>Chiudi</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
