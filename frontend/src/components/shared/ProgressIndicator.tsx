"use client";

import { cn } from "@/lib/utils";
import { config } from "@/config";
import type { ProcessingProgress } from "@/types";
import { Check, Loader2, CheckCircle2 } from "lucide-react";
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

/** Format detailed result — uses the specific result string saved in stepResults */
function formatStepDetails(_step: number, result?: string, _details?: any): string {
  return result || "Completato";
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
    )}>
      <div className="mx-auto max-w-3xl px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 shrink-0">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <span className="text-xs font-semibold text-primary">Risposta pronta</span>
          </div>
          <div className="h-3 w-px bg-border/60" />
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground min-w-0">
            <Loader2 className="h-3 w-3 animate-spin shrink-0 text-muted-foreground/70" />
            <span className="truncate">{statusText}</span>
          </div>
        </div>
      </div>
    </div>
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
      {/* Mobile layout: compact dots */}
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
                    <p className="text-[11px] text-primary font-medium mt-1">
                      Risultato: {formatStepDetails(stepNumber, getStepResult(stepNumber)?.result, getStepResult(stepNumber)?.details)}
                    </p>
                  )}
                  {isActive && (
                    <p className="text-[11px] text-primary/70 font-medium mt-1 italic">In corso...</p>
                  )}
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>
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

        {/* Step circles only — no labels */}
        <div className="flex justify-between items-center">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === progress.currentStep;
            const isComplete = stepNumber < progress.currentStep;
            const isPending = stepNumber > progress.currentStep;
            const stepResult = getStepResult(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-all duration-300 cursor-pointer",
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
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {STEP_DESCRIPTIONS[stepNumber] || step.description}
                  </p>
                  {isComplete && (
                    <p className="text-[11px] text-primary font-medium mt-1">
                      Risultato: {formatStepDetails(stepNumber, stepResult?.result, stepResult?.details)}
                    </p>
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

  const getStepTooltip = (stepNumber: number) => {
    const stepResult = getStepResult(stepNumber);
    const step = steps[stepNumber - 1];
    if (!step) return null;

    return {
      description: STEP_DESCRIPTIONS[stepNumber] || step.description,
      result: formatStepDetails(stepNumber, stepResult?.result, stepResult?.details),
    };
  };

  return (
    <div className={cn("w-full", className)}>
      {/* Mobile: compact dots */}
      <div className="sm:hidden flex items-center gap-1.5 px-1">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const tooltip = getStepTooltip(stepNumber);
          return (
            <Tooltip key={step.id} delayDuration={0}>
              <TooltipTrigger asChild>
                <div className="h-1.5 rounded-full bg-primary flex-1 cursor-pointer" />
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[250px]">
                <p className="font-semibold text-xs">{step.label}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">{tooltip?.description}</p>
                <p className="text-[11px] text-primary font-medium mt-1">Risultato: {tooltip?.result}</p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>

      {/* Desktop: completed stepper with connecting line */}
      <div className="hidden sm:block">
        <div className="relative flex justify-between items-center">
          {/* Connecting line behind circles */}
          <div className="absolute left-4 right-4 top-1/2 -translate-y-1/2 h-0.5 bg-primary/30 rounded-full" />

          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const tooltip = getStepTooltip(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div
                    className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium cursor-pointer transition-all hover:ring-2 hover:ring-primary/30"
                  >
                    <Check className="h-3.5 w-3.5" />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{tooltip?.description}</p>
                  <p className="text-[11px] text-primary font-medium mt-1">Risultato: {tooltip?.result}</p>
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
