"use client";

import { cn } from "@/lib/utils";
import { config } from "@/config";
import type { ProcessingProgress } from "@/types";
import { Check, Loader2 } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ProgressIndicatorProps {
  progress: ProcessingProgress | null;
  className?: string;
}

export function ProgressIndicator({ progress, className }: ProgressIndicatorProps) {
  if (!progress) return null;

  const steps = config.ui.progressSteps;

  // Trova il risultato per uno step specifico
  const getStepResult = (stepNumber: number) => {
    return progress.stepResults?.find(r => r.step === stepNumber);
  };

  return (
    <div className={cn("w-full max-w-3xl mx-auto px-4", className)}>
      {/* Progress bar */}
      <div className="relative mb-6 px-4">
        <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
            style={{
              // Calculation: (currentStep - 1) / (totalSteps - 1) keeps it aligned with circle centers
              // We add a safety check for totalSteps <= 1 to avoid division by zero
              width: progress.isComplete 
                ? "100%" 
                : `${((progress.currentStep - 1) / (Math.max(1, progress.totalSteps - 1))) * 100}%`,
            }}
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
              {/* Step indicator circle */}
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

              {/* Label */}
              <span
                className={cn(
                  "text-[9px] font-medium text-center leading-tight transition-colors duration-200",
                  "max-w-[60px] break-words line-clamp-2",
                  isActive ? "text-primary opacity-100" : "text-muted-foreground opacity-60 group-hover:opacity-100"
                )}
              >
                {step.label}
              </span>
            </div>
          );

          // Mostra tooltip solo per step completati con risultati
          if (isComplete && stepResult) {
            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="cursor-pointer">
                    {stepIndicator}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[200px]">
                  <p className="font-medium text-xs">{stepResult.label}</p>
                  <p className="text-xs text-muted-foreground">{stepResult.result}</p>
                </TooltipContent>
              </Tooltip>
            );
          }

          return <div key={step.id}>{stepIndicator}</div>;
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
