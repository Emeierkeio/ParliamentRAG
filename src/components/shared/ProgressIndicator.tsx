"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { config } from "@/config";
import type { ProcessingProgress } from "@/types";
import { Check, Loader2, CheckCircle2, Search, Landmark, Users, MessageSquareText, BarChart3, Compass, PenTool, FlaskConical, ShieldCheck, Target } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ProgressIndicatorProps {
  progress: ProcessingProgress | null;
  className?: string;
}

/** Shared step descriptions for tooltips */
const STEP_DESCRIPTIONS: Record<number, string> = {
  1: "Classifica la domanda dell'utente per identificare il tema principale",
  2: "Identifica la commissione parlamentare più pertinente al tema",
  3: "Seleziona i parlamentari con maggiore autorità sul tema per ciascuna coalizione",
  4: "Recupera gli interventi parlamentari più rilevanti dal database vettoriale",
  5: "Calcola le percentuali di rappresentazione maggioranza/opposizione",
  6: "Analizza il posizionamento ideologico dei gruppi parlamentari sul tema",
  7: "Genera la sintesi finale bilanciata con citazioni verificate",
  8: "Genera una risposta di confronto per la valutazione A/B",
  9: "Completa la verifica finale e salva in cronologia",
};

/** Render rich step result details based on step type */
function StepResultDetails({ step, result, details }: { step: number; result?: string; details?: any }) {
  // Step 2: Commissioni — show commission names with scores and keywords
  if (step === 2 && details?.commissioni?.length > 0) {
    return (
      <div className="mt-1.5 space-y-1.5">
        {details.commissioni.map((c: any, i: number) => (
          <div key={i} className="text-[11px]">
            <p className="text-primary font-medium leading-snug">{c.nome || c.name}</p>
            <div className="flex items-center gap-2 mt-0.5 text-muted-foreground">
              {c.score != null && <span>Score: {c.score}</span>}
              {c.matched_keywords?.length > 0 && (
                <span>Keywords: {c.matched_keywords.join(", ")}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Default: show result string
  return (
    <p className="text-[11px] text-primary font-medium mt-1">
      Risultato: {result || "Completato"}
    </p>
  );
}

/**
 * Sticky banner shown after the response text is visible (step 7+).
 * Rendered separately in ChatArea as a sticky element.
 */
export function ProgressBanner({ progress, className }: ProgressIndicatorProps) {
  if (!progress) return null;

  const textIsVisible = progress.stepResults?.some(r => r.step === 7);
  if (!textIsVisible || progress.isComplete) return null;

  const statusText = progress.currentStep <= 7
    ? "Completamento scrittura..."
    : progress.currentStep === 8
      ? "Generazione risposta di confronto per la valutazione..."
      : "Finalizzazione...";

  return (
    <div className={cn(
      "sticky top-0 z-20 w-full bg-background/95 backdrop-blur-md border-b border-primary/10",
      "animate-in slide-in-from-top-2 duration-300",
      className
    )}></div>
  );
}

export function ProgressIndicator({ progress, className }: ProgressIndicatorProps) {
  if (!progress || progress.isComplete) return null;

  const steps = config.ui.progressSteps;

  const getStepResult = (stepNumber: number) => {
    return progress.stepResults?.find(r => r.step === stepNumber);
  };

  const completedCount = Math.max(0, progress.currentStep - 1);
  const totalSteps = steps.length;
  const progressPercent = (completedCount / Math.max(1, totalSteps - 1)) * 100;

  return (
    <div className={cn("w-full max-w-3xl mx-auto", className)}>
      {/* Mobile layout: compact bars with active step label */}
      <div className="sm:hidden">
        <div className="flex items-center gap-1.5 px-1">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === progress.currentStep;
            const isComplete = stepNumber < progress.currentStep;

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div
                    className={cn(
                      "h-1.5 rounded-full transition-all duration-300 flex-1 cursor-pointer",
                      isComplete && "bg-primary",
                      isActive && "bg-primary/50",
                      !isComplete && !isActive && "bg-muted"
                    )}
                  />
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[250px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {STEP_DESCRIPTIONS[stepNumber] || step.description}
                  </p>
                  {isComplete && (
                    <StepResultDetails step={stepNumber} result={getStepResult(stepNumber)?.result} details={getStepResult(stepNumber)?.details} />
                  )}
                  {isActive && (
                    <p className="text-[11px] text-primary/70 font-medium mt-1 italic">In corso...</p>
                  )}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
        <p className="text-[10px] text-primary font-medium mt-1.5 px-1 truncate">
          {steps[progress.currentStep - 1]?.label}
        </p>
      </div>

      {/* Desktop layout: circles only with progress bar */}
      <div className="hidden sm:block">
        {/* Progress bar */}
        <div className="relative mb-4">
          <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Step circles with labels */}
        <div className="flex justify-between items-start">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === progress.currentStep;
            const isComplete = stepNumber < progress.currentStep;
            const isPending = stepNumber > progress.currentStep;
            const stepResult = getStepResult(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="flex flex-col items-center gap-1.5 cursor-pointer min-w-0 flex-1">
                    <div
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-all duration-300",
                        isComplete && "bg-primary text-primary-foreground",
                        isActive && "bg-primary/20 text-primary ring-2 ring-primary/50",
                        isPending && "bg-muted text-muted-foreground opacity-40"
                      )}
                    >
                      {isComplete ? (
                        <Check className="h-4 w-4" />
                      ) : isActive ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        stepNumber
                      )}
                    </div>
                    <span
                      className={cn(
                        "text-[10px] leading-tight text-center truncate w-full px-0.5 transition-all duration-300",
                        isComplete && "text-primary font-medium",
                        isActive && "text-primary font-semibold",
                        isPending && "text-muted-foreground opacity-40"
                      )}
                    >
                      {step.label}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {STEP_DESCRIPTIONS[stepNumber] || step.description}
                  </p>
                  {isComplete && (
                    <StepResultDetails step={stepNumber} result={stepResult?.result} details={stepResult?.details} />
                  )}
                  {isActive && (
                    <p className="text-[11px] text-primary/70 font-medium mt-1 italic">
                      In corso...
                    </p>
                  )}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * Completed progress stepper: shown after the response is done.
 * All steps appear as completed with hover tooltips showing what was done.
 * A connecting line runs behind the circles.
 */
export function CompletedProgressStepper({ progress, className }: ProgressIndicatorProps) {
  if (!progress) return null;

  const steps = config.ui.progressSteps;

  const getStepResult = (stepNumber: number) => {
    return progress.stepResults?.find(r => r.step === stepNumber);
  };

  return (
    <div className={cn("w-full", className)}>
      {/* Mobile: circles with labels (matching desktop) */}
      <div className="sm:hidden">
        <div className="relative flex justify-between items-start">
          {/* Connecting line behind circles */}
          <div className="absolute left-3 right-3 top-[11px] -translate-y-1/2 h-0.5 bg-primary/30 rounded-full" />

          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const stepResult = getStepResult(stepNumber);
            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="relative z-10 flex flex-col items-center gap-1 cursor-pointer min-w-0 flex-1">
                    <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
                      <Check className="h-3 w-3" />
                    </div>
                    <span className="text-[8px] leading-tight text-center truncate w-full px-0.5 text-primary font-medium">
                      {step.label}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[250px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {STEP_DESCRIPTIONS[stepNumber] || step.description}
                  </p>
                  <StepResultDetails step={stepNumber} result={stepResult?.result} details={stepResult?.details} />
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </div>

      {/* Desktop: completed stepper with connecting line */}
      <div className="hidden sm:block">
        <div className="relative flex justify-between items-start">
          {/* Connecting line behind circles */}
          <div className="absolute left-4 right-4 top-[14px] -translate-y-1/2 h-0.5 bg-primary/30 rounded-full" />

          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const stepResult = getStepResult(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="relative z-10 flex flex-col items-center gap-1.5 cursor-pointer min-w-0 flex-1">
                    <div
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium transition-all hover:ring-2 hover:ring-primary/30"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10px] leading-tight text-center truncate w-full px-0.5 text-primary font-medium">
                      {step.label}
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {STEP_DESCRIPTIONS[stepNumber] || step.description}
                  </p>
                  <StepResultDetails step={stepNumber} result={stepResult?.result} details={stepResult?.details} />
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Compact version for inline display
export function ProgressIndicatorCompact({ progress }: ProgressIndicatorProps) {
  if (!progress) return null;

  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin text-primary" />
      <span>
        {progress.stepLabel} ({progress.currentStep}/{progress.totalSteps})
      </span>
    </div>
  );
}

/** Rich step metadata for the activity panel */
const STEP_DETAILS: Record<number, { doing: string; why: string; icon: React.ComponentType<{ className?: string }> }> = {
  1: {
    doing: "Classifico la tua domanda per identificare il tema principale e le parole chiave",
    why: "Permette di indirizzare la ricerca verso le commissioni e i deputati più pertinenti",
    icon: Search,
  },
  2: {
    doing: "Cerco le commissioni parlamentari che hanno discusso questo tema",
    why: "Le commissioni sono il cuore del lavoro legislativo: qui avvengono i dibattiti più tecnici e approfonditi",
    icon: Landmark,
  },
  3: {
    doing: "Identifico i parlamentari con maggiore autorità sul tema, bilanciando maggioranza e opposizione",
    why: "Garantisce che la risposta includa voci autorevoli di entrambi gli schieramenti",
    icon: Users,
  },
  4: {
    doing: "Recupero gli interventi parlamentari più rilevanti dal database",
    why: "Questi sono i discorsi reali pronunciati in aula o in commissione, la base fattuale della risposta",
    icon: MessageSquareText,
  },
  5: {
    doing: "Calcolo le metriche di bilanciamento tra le coalizioni",
    why: "Assicura che la risposta finale rappresenti equamente maggioranza e opposizione",
    icon: BarChart3,
  },
  6: {
    doing: "Analizzo il posizionamento ideologico dei gruppi parlamentari su questo tema",
    why: "Permette di visualizzare graficamente dove si collocano i partiti sugli assi tematici rilevanti",
    icon: Compass,
  },
  7: {
    doing: "Scrivo la sintesi finale combinando tutti gli interventi raccolti",
    why: "Tutte le informazioni raccolte vengono trasformate in una risposta coerente e bilanciata",
    icon: PenTool,
  },
  8: {
    doing: "Genero una risposta di confronto senza il sistema RAG",
    why: "Servirà per la valutazione A/B: confrontare la qualità della risposta RAG con una risposta standard",
    icon: FlaskConical,
  },
  9: {
    doing: "Verifico la completezza e salvo in cronologia",
    why: "Ultimo controllo di qualità prima di mostrare il risultato finale",
    icon: ShieldCheck,
  },
};

/**
 * Full-page activity panel shown during pipeline processing.
 * Fills the empty space below the stepper with rich step descriptions.
 */
export function PipelineActivityPanel({ progress, className }: ProgressIndicatorProps) {
  if (!progress || progress.isComplete) return null;

  const steps = config.ui.progressSteps;
  const currentStep = progress.currentStep;
  const currentDetails = STEP_DETAILS[currentStep];

  const getStepResult = (stepNumber: number) =>
    progress.stepResults?.find(r => r.step === stepNumber);

  return (
    <div className={cn("w-full max-w-3xl mx-auto mt-8 animate-in fade-in-0 duration-500", className)}>
      {/* Obiettivo finale */}
      <div className="flex items-center gap-3 rounded-xl bg-primary/5 border border-primary/10 px-5 py-3.5 mb-8">
        <Target className="h-5 w-5 text-primary shrink-0" />
        <p className="text-sm text-foreground/80">
          <span className="font-semibold text-foreground">Obiettivo:</span>{" "}
          Generare una risposta bilanciata analizzando gli interventi di maggioranza e opposizione
        </p>
      </div>

      {/* Step attivo corrente */}
      {currentDetails && (
        <div className="relative rounded-2xl border border-primary/20 bg-card shadow-lg overflow-hidden mb-8">
          {/* Accent bar */}
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary/60 via-primary to-primary/60" />
          <div className="p-6 sm:p-8">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <currentDetails.icon className="h-6 w-6" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-primary/70">
                    Step {currentStep} di {steps.length}
                  </span>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary/60" />
                </div>
                <h3 className="text-lg font-bold text-foreground mb-2">
                  {steps[currentStep - 1]?.label}
                </h3>
                <p className="text-sm text-foreground/80 leading-relaxed mb-3">
                  {currentDetails.doing}
                </p>
                <div className="flex items-start gap-2 rounded-lg bg-muted/50 px-3.5 py-2.5">
                  <span className="text-xs font-semibold text-muted-foreground shrink-0 mt-0.5">Perché?</span>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {currentDetails.why}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Timeline: step completati + futuri */}
      <div className="space-y-0">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isActive = stepNumber === currentStep;
          const isComplete = stepNumber < currentStep;
          const isPending = stepNumber > currentStep;
          const details = STEP_DETAILS[stepNumber];
          const stepResult = getStepResult(stepNumber);

          if (isActive) return null; // Already shown above

          return (
            <div key={step.id} className="flex items-start gap-4 relative">
              {/* Vertical line */}
              {index < steps.length - 1 && (
                <div className={cn(
                  "absolute left-[15px] top-8 bottom-0 w-px",
                  isComplete ? "bg-primary/30" : "bg-border"
                )} />
              )}

              {/* Circle */}
              <div className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium z-10 transition-all",
                isComplete && "bg-primary text-primary-foreground",
                isPending && "bg-muted text-muted-foreground/40 border border-border"
              )}>
                {isComplete ? (
                  <Check className="h-4 w-4" />
                ) : (
                  stepNumber
                )}
              </div>

              {/* Content */}
              <div className={cn(
                "flex-1 min-w-0 pb-5",
                isPending && "opacity-40"
              )}>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={cn(
                    "text-sm font-semibold",
                    isComplete && "text-foreground",
                    isPending && "text-muted-foreground"
                  )}>
                    {step.label}
                  </span>
                  {isComplete && details && (
                    <details.icon className="h-3.5 w-3.5 text-primary/50" />
                  )}
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {details?.doing || step.description}
                </p>
                {isComplete && stepResult?.result && (
                  <p className="text-xs text-primary font-medium mt-1.5 bg-primary/5 rounded-md px-2.5 py-1.5 inline-block">
                    {stepResult.result}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
