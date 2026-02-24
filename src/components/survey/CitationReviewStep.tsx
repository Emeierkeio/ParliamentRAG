"use client";

import React, { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  HelpCircle,
  Quote,
  User,
  Calendar,
  Users,
  AlertTriangle,
  Scissors,
  UserX,
  Copy,
  Send,
  SkipForward,
  FileText,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { StarRating } from "./StarRating";
import type { Citation } from "@/types/chat";
import {
  type CitationEvaluation,
  CITATION_ISSUES,
  getInitialCitationEvaluation,
} from "@/types/survey";

interface CitationReviewStepProps {
  citationsA: Citation[];
  citationsB: Citation[];
  responseTextA: string;
  responseTextB: string;
  evaluationsA: CitationEvaluation[];
  evaluationsB: CitationEvaluation[];
  onUpdateEvaluationA: (index: number, evaluation: CitationEvaluation) => void;
  onUpdateEvaluationB: (index: number, evaluation: CitationEvaluation) => void;
  onSubmit: () => void;
  onSkip: () => void;
  onBack: () => void;
  isSubmitting: boolean;
}

const ISSUE_ICONS: Record<string, React.ReactNode> = {
  none: <Check className="w-3.5 h-3.5" />,
  out_of_context: <AlertTriangle className="w-3.5 h-3.5" />,
  truncated: <Scissors className="w-3.5 h-3.5" />,
  wrong_attribution: <UserX className="w-3.5 h-3.5" />,
  duplicate: <Copy className="w-3.5 h-3.5" />,
  unverifiable: <HelpCircle className="w-3.5 h-3.5" />,
};

function isCitationEvalComplete(ev: CitationEvaluation): boolean {
  return ev.relevance > 0 && ev.faithfulness > 0 && ev.informativeness > 0 && ev.attribution !== "";
}

/**
 * Extract the context paragraph from the response text where a citation is used.
 * Citations appear as [«quote»](evidence_id) or (evidence_id) in the text.
 * Returns the surrounding paragraph with the citation highlighted.
 */
function extractCitationContext(
  responseText: string,
  chunkId: string
): { before: string; citation: string; after: string } | null {
  if (!responseText || !chunkId) return null;

  // Find the citation in the text: [«quote»](chunk_id) or (chunk_id)
  // Pattern 1: markdown link format [«...»](chunk_id)
  const linkPattern = new RegExp(
    `\\[«([^»]*)»\\]\\(${escapeRegExp(chunkId)}\\)`,
    "g"
  );
  // Pattern 2: bare reference (chunk_id)
  const barePattern = new RegExp(
    `\\(${escapeRegExp(chunkId)}\\)`,
    "g"
  );

  let match = linkPattern.exec(responseText);
  let matchedText = "";
  let matchStart = -1;

  if (match) {
    matchedText = match[0];
    matchStart = match.index;
  } else {
    match = barePattern.exec(responseText);
    if (match) {
      matchedText = match[0];
      matchStart = match.index;
    }
  }

  if (matchStart === -1) return null;

  // Extract surrounding context: find the paragraph boundaries
  const lines = responseText.split("\n");
  let charCount = 0;
  let contextLines: string[] = [];
  let foundLineIdx = -1;

  for (let i = 0; i < lines.length; i++) {
    const lineStart = charCount;
    const lineEnd = charCount + lines[i].length;

    if (matchStart >= lineStart && matchStart < lineEnd + 1) {
      foundLineIdx = i;
      break;
    }
    charCount = lineEnd + 1; // +1 for \n
  }

  if (foundLineIdx === -1) return null;

  // Get 1 line before and 1 line after for context
  const startLine = Math.max(0, foundLineIdx - 1);
  const endLine = Math.min(lines.length - 1, foundLineIdx + 1);
  const contextText = lines.slice(startLine, endLine + 1).join("\n");

  // Find the match position within the context
  const matchInContext = contextText.indexOf(matchedText);
  if (matchInContext === -1) {
    return { before: contextText, citation: "", after: "" };
  }

  return {
    before: contextText.slice(0, matchInContext),
    citation: matchedText,
    after: contextText.slice(matchInContext + matchedText.length),
  };
}

function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Clean citation text for display: extract quote from [«quote»](id) format */
function formatCitationDisplay(citationText: string): string {
  const quoteMatch = citationText.match(/\[«([^»]*)»\]\([^)]+\)/);
  if (quoteMatch) return `«${quoteMatch[1]}»`;
  return citationText;
}

export function CitationReviewStep({
  citationsA,
  citationsB,
  responseTextA,
  responseTextB,
  evaluationsA,
  evaluationsB,
  onUpdateEvaluationA,
  onUpdateEvaluationB,
  onSubmit,
  onSkip,
  onBack,
  isSubmitting,
}: CitationReviewStepProps) {
  const [currentIndexA, setCurrentIndexA] = useState(0);

  const citations = citationsA;
  const evaluations = evaluationsA;
  const responseText = responseTextA;
  const currentIndex = currentIndexA;
  const setCurrentIndex = setCurrentIndexA;
  const onUpdateEvaluation = onUpdateEvaluationA;

  const currentCitation = citations[currentIndex];
  const currentEvaluation = evaluations[currentIndex];

  // Extract context from the response text for the current citation
  const citationContext = useMemo(() => {
    if (!currentCitation) return null;
    return extractCitationContext(responseText, currentCitation.chunk_id);
  }, [responseText, currentCitation]);

  const completedA = evaluationsA.filter(isCitationEvalComplete).length;
  const totalCitations = citationsA.length;
  const totalCompleted = completedA;

  const hasCitations = citationsA.length > 0;

  const updateField = <K extends keyof CitationEvaluation>(
    field: K,
    value: CitationEvaluation[K]
  ) => {
    if (!currentEvaluation) return;
    onUpdateEvaluation(currentIndex, {
      ...currentEvaluation,
      [field]: value,
    });
  };

  const toggleIssue = (issueId: string) => {
    if (!currentEvaluation) return;
    const current = currentEvaluation.issues;
    if (issueId === "none") {
      onUpdateEvaluation(currentIndex, {
        ...currentEvaluation,
        issues: current.includes("none") ? [] : ["none"],
      });
      return;
    }
    const withoutNone = current.filter((i) => i !== "none");
    const updated = withoutNone.includes(issueId)
      ? withoutNone.filter((i) => i !== issueId)
      : [...withoutNone, issueId];
    onUpdateEvaluation(currentIndex, {
      ...currentEvaluation,
      issues: updated,
    });
  };

  if (!hasCitations) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6 py-12">
        <Quote className="w-12 h-12 text-gray-300 mb-4" />
        <h3 className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
          Nessuna citazione da valutare
        </h3>
        <p className="text-sm text-gray-500 mb-6 text-center max-w-sm">
          Le risposte selezionate non contengono citazioni parlamentari individuabili.
        </p>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onBack}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            Indietro
          </Button>
          <Button onClick={onSubmit} disabled={isSubmitting}>
            <Send className="w-4 h-4 mr-2" />
            Invia Valutazione
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with progress */}
      <div className="px-4 py-3 border-b bg-white dark:bg-gray-950">
        <div className="flex items-center justify-between mb-3">
          <Badge className="h-8 px-3 bg-blue-600 text-white text-sm">
            Risposta A
          </Badge>
          <span className="text-sm text-gray-500">
            Totale: {totalCompleted}/{totalCitations}
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-300"
            style={{ width: totalCitations > 0 ? `${(totalCompleted / totalCitations) * 100}%` : "0%" }}
          />
        </div>
      </div>

      {citations.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <p className="text-sm">Nessuna citazione da valutare</p>
        </div>
      ) : (
        <>
          {/* Citation navigation dots */}
          <div className="px-4 py-2 border-b bg-gray-50 dark:bg-gray-900/30 flex items-center gap-1.5 overflow-x-auto">
            <span className="text-xs text-gray-500 mr-2 whitespace-nowrap">
              Citazione {currentIndex + 1} di {citations.length}
            </span>
            {citations.map((_, idx) => {
              const ev = evaluations[idx];
              const isComplete = ev && isCitationEvalComplete(ev);
              return (
                <button
                  key={idx}
                  onClick={() => setCurrentIndex(idx)}
                  className={cn(
                    "w-7 h-7 rounded-full text-xs font-medium transition-all flex items-center justify-center flex-shrink-0",
                    idx === currentIndex
                      ? "bg-blue-600 text-white ring-2 ring-blue-300"
                      : isComplete
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                      : "bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
                  )}
                >
                  {isComplete ? <Check className="w-3.5 h-3.5" /> : idx + 1}
                </button>
              );
            })}
          </div>

          {/* Citation context + evaluation form */}
          <ScrollArea className="flex-1 px-4 py-4">
            {currentCitation && currentEvaluation && (
              <div className="space-y-4">

                {/* Section 1: How the citation is used in the generated response */}
                <Card className="border-l-4 border-l-blue-500">
                  <CardContent className="p-4 space-y-2">
                    <div className="flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300">
                      <FileText className="w-4 h-4" />
                      Come appare nella risposta generata
                    </div>

                    {citationContext ? (
                      <div className="bg-blue-50 dark:bg-blue-950/20 rounded-lg p-3 text-sm leading-relaxed">
                        <p className="text-gray-700 dark:text-gray-300">
                          <span>{citationContext.before}</span>
                          <span className="bg-yellow-200 dark:bg-yellow-800/50 px-1 py-0.5 rounded font-medium text-gray-900 dark:text-yellow-200">
                            {formatCitationDisplay(citationContext.citation)}
                          </span>
                          <span>{citationContext.after}</span>
                        </p>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 italic">
                        Contesto non trovato nel testo della risposta per questo riferimento.
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* Section 2: Original source / citation metadata */}
                <Card className="border-l-4 border-l-indigo-500">
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-2 text-sm font-medium text-indigo-700 dark:text-indigo-300">
                      <BookOpen className="w-4 h-4" />
                      Fonte originale
                    </div>

                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <User className="w-4 h-4 text-indigo-600" />
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {currentCitation.deputy_first_name} {currentCitation.deputy_last_name}
                        </span>
                      </div>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-xs",
                          currentCitation.coalition === "maggioranza"
                            ? "border-blue-300 text-blue-700 bg-blue-50"
                            : "border-orange-300 text-orange-700 bg-orange-50"
                        )}
                      >
                        {currentCitation.coalition}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5" />
                        {currentCitation.group}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        {currentCitation.date}
                      </span>
                    </div>

                    {currentCitation.debate && (
                      <p className="text-xs text-gray-400 italic">
                        {currentCitation.debate}
                      </p>
                    )}

                    {/* Original quote text from source */}
                    {(currentCitation.quote_text || currentCitation.text) && (
                      <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 border-l-2 border-gray-300">
                        <div className="flex items-start gap-2">
                          <Quote className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                          <p className="text-sm text-gray-700 dark:text-gray-300 italic leading-relaxed">
                            {currentCitation.quote_text || currentCitation.text}
                          </p>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Section 3: Evaluation form */}
                <Card>
                  <CardContent className="p-4 space-y-5">
                    {/* Relevance */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          Pertinenza
                        </label>
                        <span className="text-xs text-gray-400">
                          La citazione e rilevante nel contesto in cui e usata?
                        </span>
                      </div>
                      <StarRating
                        value={currentEvaluation.relevance}
                        onChange={(val) => updateField("relevance", val)}
                        size="md"
                      />
                    </div>

                    {/* Faithfulness */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          Fedelta
                        </label>
                        <span className="text-xs text-gray-400">
                          Il testo nella risposta e fedele alla fonte originale?
                        </span>
                      </div>
                      <StarRating
                        value={currentEvaluation.faithfulness}
                        onChange={(val) => updateField("faithfulness", val)}
                        size="md"
                      />
                    </div>

                    {/* Informativeness */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          Valore informativo
                        </label>
                        <span className="text-xs text-gray-400">
                          La citazione aggiunge informazione utile alla risposta?
                        </span>
                      </div>
                      <StarRating
                        value={currentEvaluation.informativeness}
                        onChange={(val) => updateField("informativeness", val)}
                        size="md"
                      />
                    </div>

                    {/* Attribution */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Attribuzione
                      </label>
                      <p className="text-xs text-gray-400">
                        Deputato, gruppo e data sono corretti?
                      </p>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant={currentEvaluation.attribution === "correct" ? "default" : "outline"}
                          onClick={() => updateField("attribution", "correct")}
                          className={cn(
                            "h-8 text-xs flex-1",
                            currentEvaluation.attribution === "correct" && "bg-emerald-600 hover:bg-emerald-700"
                          )}
                        >
                          <Check className="w-3.5 h-3.5 mr-1" />
                          Corretta
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant={currentEvaluation.attribution === "incorrect" ? "default" : "outline"}
                          onClick={() => updateField("attribution", "incorrect")}
                          className={cn(
                            "h-8 text-xs flex-1",
                            currentEvaluation.attribution === "incorrect" && "bg-red-600 hover:bg-red-700"
                          )}
                        >
                          <X className="w-3.5 h-3.5 mr-1" />
                          Errata
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant={currentEvaluation.attribution === "unverifiable" ? "default" : "outline"}
                          onClick={() => updateField("attribution", "unverifiable")}
                          className={cn(
                            "h-8 text-xs flex-1",
                            currentEvaluation.attribution === "unverifiable" && "bg-gray-600 hover:bg-gray-700"
                          )}
                        >
                          <HelpCircle className="w-3.5 h-3.5 mr-1" />
                          N/V
                        </Button>
                      </div>
                    </div>

                    {/* Issue tags */}
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        Segnalazione problemi
                      </label>
                      <div className="flex flex-wrap gap-2">
                        {CITATION_ISSUES.map((issue) => {
                          const isSelected = currentEvaluation.issues.includes(issue.id);
                          return (
                            <button
                              key={issue.id}
                              type="button"
                              onClick={() => toggleIssue(issue.id)}
                              className={cn(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border",
                                isSelected
                                  ? issue.id === "none"
                                    ? "bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-700"
                                    : "bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700"
                                  : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50 dark:bg-gray-900 dark:text-gray-400 dark:border-gray-700 dark:hover:bg-gray-800"
                              )}
                            >
                              {ISSUE_ICONS[issue.id]}
                              {issue.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </ScrollArea>

          {/* Navigation footer */}
          <div className="px-4 py-3 border-t bg-white dark:bg-gray-950">
            <div className="flex items-center justify-between">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (currentIndex > 0) {
                    setCurrentIndex(currentIndex - 1);
                  } else {
                    onBack();
                  }
                }}
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                {currentIndex === 0 ? "Indietro" : "Precedente"}
              </Button>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={onSkip}>
                  <SkipForward className="w-4 h-4 mr-1" />
                  Salta
                </Button>

                {currentIndex < citations.length - 1 ? (
                  <Button
                    size="sm"
                    onClick={() => setCurrentIndex(currentIndex + 1)}
                  >
                    Prossima
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={onSubmit}
                    disabled={isSubmitting}
                    className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                  >
                    <Send className="w-4 h-4 mr-2" />
                    Invia Valutazione
                  </Button>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
