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
  if (!progress) return null;

  const steps = config.ui.progressSteps;

  const getStepResult = (stepNumber: number) => {
    return progress.stepResults?.find(r => r.step === stepNumber);
  };

  // Text is already visible once step 7 result exists
  const textIsVisible = progress.stepResults?.some(r => r.step === 7);

  // After text is visible, the banner handles the status — hide the stepper
  if (textIsVisible) return null;

  const completedCount = Math.max(0, progress.currentStep - 1);
  const totalSteps = steps.length;
  const progressPercent = progress.isComplete
    ? 100
    : (completedCount / Math.max(1, totalSteps - 1)) * 100;

  const activeStep = steps[progress.currentStep - 1];

  return (
    <div className={cn("w-full max-w-3xl mx-auto px-4", className)}>
      {/* Mobile layout: compact current-step focus */}
      <div className="sm:hidden">
        {/* Current step hero */}
        <div className="flex items-center gap-3 mb-3">
          <div className="relative flex items-center justify-center h-10 w-10 shrink-0">
            {/* Circular progress ring */}
            <svg className="absolute inset-0 h-10 w-10 -rotate-90" viewBox="0 0 40 40">
              <circle
                cx="20" cy="20" r="17"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                className="text-muted/50"
              />
              <circle
                cx="20" cy="20" r="17"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 17}`}
                strokeDashoffset={`${2 * Math.PI * 17 * (1 - progressPercent / 100)}`}
                className="text-primary transition-all duration-500 ease-out"
              />
            </svg>
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-semibold text-foreground">
                {activeStep?.label || progress.stepLabel}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {progress.currentStep}/{totalSteps}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              {activeStep?.description || progress.stepDescription}
            </p>
          </div>
        </div>

        {/* Compact step dots */}
        <div className="flex items-center gap-1.5 px-1">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === progress.currentStep;
            const isComplete = stepNumber < progress.currentStep || progress.isComplete;

            return (
              <div
                key={step.id}
                className={cn(
                  "h-1.5 rounded-full transition-all duration-300 flex-1",
                  isComplete && "bg-primary",
                  isActive && "bg-primary/50",
                  !isComplete && !isActive && "bg-muted"
                )}
              />
            );
          })}
        </div>
      </div>

      {/* Desktop layout: full stepper */}
      <div className="hidden sm:block">
        {/* Progress bar */}
        <div className="relative mb-6 px-4">
          <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Steps */}
        <div className="flex justify-between items-start gap-1">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === progress.currentStep;
            const isComplete = stepNumber < progress.currentStep || progress.isComplete;
            const isPending = stepNumber > progress.currentStep;
            const stepResult = getStepResult(stepNumber);

            const stepIndicator = (
              <div
                className={cn(
                  "flex flex-col items-center gap-2 group min-w-0 transition-opacity duration-300",
                  isPending && "opacity-40"
                )}
              >
                <div
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-all duration-300",
                    isComplete && "bg-primary text-primary-foreground",
                    isActive && "bg-primary/20 text-primary ring-2 ring-primary/50",
                    isPending && "bg-muted text-muted-foreground"
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
                    "text-[10px] font-medium text-center leading-tight transition-colors duration-200",
                    "max-w-[70px] break-words line-clamp-2",
                    isActive ? "text-primary opacity-100" : "text-muted-foreground opacity-60 group-hover:opacity-100"
                  )}
                >
                  {step.label}
                </span>
              </div>
            );

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="cursor-pointer">
                    {stepIndicator}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{step.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {STEP_DESCRIPTIONS[stepNumber] || step.description}
                  </p>
                  {isComplete && stepResult && (
                    <p className="text-[11px] text-primary font-medium mt-1">
                      Risultato: {formatStepDetails(stepNumber, stepResult.result, stepResult.details)}
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

        {/* Current step description */}
        <div className="mt-4 text-center">
          <p className="text-sm font-medium text-foreground">
            {progress.stepLabel}
          </p>
          <p className="text-xs text-muted-foreground">
            {progress.stepDescription}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Completed progress stepper: shown after the response is done.
 * All steps appear as completed with hover tooltips showing what was done.
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

      {/* Desktop: full completed stepper */}
      <div className="hidden sm:block">
        <div className="flex justify-between items-start gap-1">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const tooltip = getStepTooltip(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="flex flex-col items-center gap-1.5 group min-w-0 cursor-pointer">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium transition-all group-hover:ring-2 group-hover:ring-primary/30">
                      <Check className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[9px] font-medium text-center leading-tight max-w-[65px] break-words line-clamp-2 text-muted-foreground group-hover:text-primary transition-colors">
                      {step.label}
                    </span>
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
