"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { config } from "@/config";
import type { ProcessingProgress } from "@/types";
import {
  Check,
  Loader2,
  CheckCircle2,
  Search,
  Landmark,
  Users,
  MessageSquare,
  BarChart3,
  Compass,
  PenTool,
  GitCompare,
  Target,
  Clock,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ProgressIndicatorProps {
  progress: ProcessingProgress | null;
  className?: string;
}

/** Short labels for mobile display (max ~5 chars) */
const STEP_SHORT_LABELS: Record<number, string> = {
  1: "Query",
  2: "Comm.",
  3: "Esperti",
  4: "Interv.",
  5: "Stats",
  6: "Bussola",
  7: "Testo",
  8: "Base",
  9: "Check",
};

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
  // Step 2: Commissioni — show commission name
  if (step === 2) {
    const topCommName = details?.commissioni?.[0]?.nome || details?.commissioni?.[0]?.name;
    if (topCommName) {
      return (
        <p className="text-[11px] text-primary font-medium mt-1">
          Commissione: {topCommName}
        </p>
      );
    }
    if (result) {
      return (
        <p className="text-[11px] text-primary font-medium mt-1">
          {result}
        </p>
      );
    }
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
                      <span className="lg:hidden">{STEP_SHORT_LABELS[stepNumber] || step.label}</span>
                      <span className="hidden lg:inline">{step.label}</span>
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
      {/* Mobile: progress bar with step labels */}
      <div className="sm:hidden w-full overflow-hidden">
        <div className="flex items-center gap-1 px-1 mb-2">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const stepResult = getStepResult(stepNumber);
            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="h-1.5 rounded-full bg-primary flex-1 min-w-0 cursor-pointer" />
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
        <div className="flex justify-between px-0.5 overflow-hidden w-full">
          {steps.map((step) => (
            <span
              key={step.id}
              className="text-[8px] leading-tight text-center text-primary/70 font-medium truncate flex-1 min-w-0 px-px"
            >
              {STEP_SHORT_LABELS[step.id] || step.label}
            </span>
          ))}
        </div>
      </div>

      {/* Desktop: completed stepper with connecting line and labels */}
      <div className="hidden sm:block">
        <div className="relative flex justify-between items-start">
          {/* Connecting line behind circles */}
          <div className="absolute left-4 right-4 top-[14px] h-0.5 bg-primary/30 rounded-full" />

          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const stepResult = getStepResult(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="flex flex-col items-center gap-1.5 cursor-pointer min-w-0 flex-1">
                    <div
                      className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium transition-all hover:ring-2 hover:ring-primary/30"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10px] leading-tight text-center text-primary font-medium truncate w-full px-0.5">
                      <span className="lg:hidden">{STEP_SHORT_LABELS[step.id] || step.label}</span>
                      <span className="hidden lg:inline">{step.label}</span>
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

/** Map step icon names to Lucide components */
const STEP_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  Search,
  Landmark,
  Users,
  MessageSquare,
  BarChart3,
  Compass,
  PenTool,
  GitCompare,
  CheckCircle2,
};

/** Feature cards shown to users while they wait in queue */
const SYSTEM_TOUR_FEATURES = [
  {
    icon: Search,
    title: "Ricerca semantica",
    desc: "Trova interventi per concetto, non solo per parola chiave esatta.",
  },
  {
    icon: Users,
    title: "Esperti per tema",
    desc: "Identifica i parlamentari con più autorità su ogni argomento.",
  },
  {
    icon: Compass,
    title: "Compasso ideologico",
    desc: "Visualizza il posizionamento dei gruppi parlamentari su qualsiasi tema.",
  },
  {
    icon: MessageSquare,
    title: "Citazioni verificate",
    desc: "Ogni affermazione è collegata al discorso originale in aula.",
  },
  {
    icon: BarChart3,
    title: "Bilancio maggioranza/opposizione",
    desc: "Controlla se la risposta è bilanciata tra i due schieramenti.",
  },
  {
    icon: Landmark,
    title: "Commissioni parlamentari",
    desc: "Scopri quale commissione è competente per ogni tema trattato.",
  },
] satisfies Array<{ icon: React.ComponentType<{ className?: string }>; title: string; desc: string }>;

interface ProgressFullPageProps {
  progress: ProcessingProgress;
  query?: string;
  className?: string;
}

/**
 * Full-page progress view shown during pipeline processing (steps 1-6).
 * Uses the entire available space to explain what each step does and why.
 */
export function ProgressFullPage({ progress, query, className }: ProgressFullPageProps) {
  // Client-side elapsed counter: starts from backend value, increments every second
  const [localElapsed, setLocalElapsed] = useState(progress.elapsedSeconds ?? 0);

  useEffect(() => {
    if (!progress.isWaiting) return;
    setLocalElapsed(progress.elapsedSeconds ?? 0);
    const interval = setInterval(() => setLocalElapsed(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, [progress.isWaiting, progress.elapsedSeconds]);

  // currentStep: 0 = connecting — first SSE event not yet received
  if (!progress.isWaiting && progress.currentStep === 0) {
    return (
      <div className={cn(
        "flex items-center justify-center w-full min-h-[50vh] md:min-h-[60vh]",
        className
      )}>
        <Loader2 className="h-6 w-6 animate-spin text-primary/30" />
      </div>
    );
  }

  if (progress.isWaiting) {
    const pos = progress.queuePosition;
    const active = progress.activeCount ?? 0;
    const displaySlots = Math.min(active, 4);
    const extraActive = active > 4 ? active - 4 : 0;

    const formatElapsed = (s: number) =>
      s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;

    return (
      <div className={cn(
        "flex flex-col items-center justify-center w-full min-h-[50vh] md:min-h-[60vh] py-10 px-6 text-center",
        className
      )}>

        {/* Pulsing clock icon */}
        <div className="relative mb-7">
          <div className="absolute -inset-4 rounded-full bg-amber-400/15 animate-ping" />
          <div className="absolute -inset-2 rounded-full bg-amber-400/10 animate-pulse" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 shadow-sm">
            <Clock className="h-8 w-8" />
          </div>
        </div>

        {/* Title */}
        <h2 className="text-lg font-semibold text-foreground mb-1.5">
          Sistema al completo
        </h2>
        <p className="text-sm text-muted-foreground max-w-xs mb-7">
          {pos !== undefined
            ? <>Sei il <span className="font-semibold text-amber-600">#{pos}</span> in lista d&apos;attesa. Verrai elaborato automaticamente appena si libera uno slot.</>
            : "La tua richiesta è in coda. Verrai elaborato non appena si libera un posto."
          }
        </p>

        {/* Visual queue */}
        <div className="flex items-end gap-3 mb-7">
          {/* Active slots */}
          {displaySlots > 0 && (
            <div className="flex items-end gap-2">
              {Array.from({ length: displaySlots }).map((_, i) => (
                <div key={i} className="flex flex-col items-center gap-1.5">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 border border-primary/20">
                    <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  </div>
                  <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">In corso</span>
                </div>
              ))}
              {extraActive > 0 && (
                <div className="flex flex-col items-center gap-1.5">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-muted border border-border text-muted-foreground text-xs font-semibold">
                    +{extraActive}
                  </div>
                  <span className="text-[9px] font-medium text-muted-foreground uppercase tracking-wide">In corso</span>
                </div>
              )}
            </div>
          )}

          {/* Arrow divider */}
          {active > 0 && (
            <div className="flex flex-col items-center gap-1.5 pb-4">
              <svg width="20" height="12" viewBox="0 0 20 12" className="text-muted-foreground/30 fill-current">
                <path d="M13.5 0L20 6l-6.5 6V8H0V4h13.5V0z" />
              </svg>
            </div>
          )}

          {/* User's waiting slot — pulsing amber */}
          <div className="flex flex-col items-center gap-1.5">
            <div className="relative">
              <div className="absolute inset-0 rounded-xl bg-amber-400/30 animate-pulse" />
              <div className="relative flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 border-2 border-amber-400 ring-4 ring-amber-400/20">
                {pos !== undefined ? (
                  <span className="text-sm font-bold text-amber-700">#{pos}</span>
                ) : (
                  <Clock className="h-5 w-5 text-amber-600" />
                )}
              </div>
            </div>
            <span className="text-[9px] font-semibold text-amber-600 uppercase tracking-wide">Tu</span>
          </div>
        </div>

        {/* Elapsed time */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-5">
          <div className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span>In attesa da <span className="font-semibold tabular-nums">{formatElapsed(localElapsed)}</span></span>
        </div>

        {/* Reassuring note */}
        <p className="text-xs text-muted-foreground/60 max-w-xs leading-relaxed mb-10">
          Non chiudere la pagina — la richiesta è registrata e verrà eseguita automaticamente.
        </p>

        {/* System tour while waiting */}
        <div className="w-full max-w-lg border-t border-border/30 pt-7">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/50 mb-4 text-center">
            Nel frattempo, scopri cosa puoi fare
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {SYSTEM_TOUR_FEATURES.map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.title}
                  className="flex flex-col gap-2 rounded-xl bg-muted/40 border border-border/40 px-3 py-3 text-left hover:bg-muted/70 transition-colors"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground leading-tight">{feat.title}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{feat.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  const steps = config.ui.progressSteps;
  const currentStepConfig = steps.find(s => s.id === progress.currentStep);
  const completedCount = Math.max(0, progress.currentStep - 1);
  const progressPercent = (completedCount / Math.max(1, steps.length - 1)) * 100;

  const getStepResult = (stepNumber: number) => {
    return progress.stepResults?.find(r => r.step === stepNumber);
  };

  const ActiveIcon = currentStepConfig?.icon ? STEP_ICONS[currentStepConfig.icon] : Loader2;

  return (
    <div className={cn("flex flex-col md:flex-row gap-0 md:gap-8 w-full min-h-[50vh] md:min-h-[60vh] py-4 md:py-6 px-3 md:px-8", className)}>

      {/* ===== MOBILE LAYOUT ===== */}
      <div className="md:hidden flex flex-col items-center w-full">
        {/* Mobile progress dots */}
        <div className="w-full mb-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] text-muted-foreground">Analisi in corso</span>
            <span className="text-[11px] font-medium text-primary">
              {progress.currentStep} / {steps.length}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {steps.map((step, index) => {
              const stepNumber = index + 1;
              const isActive = stepNumber === progress.currentStep;
              const isComplete = stepNumber < progress.currentStep;
              return (
                <div
                  key={step.id}
                  className={cn(
                    "h-1 rounded-full transition-all duration-300 flex-1",
                    isComplete && "bg-primary",
                    isActive && "bg-primary/50",
                    !isComplete && !isActive && "bg-muted"
                  )}
                />
              );
            })}
          </div>
        </div>

        {/* Mobile active step card */}
        {currentStepConfig && (
          <div className="w-full text-center space-y-4">
            {/* Icon */}
            <div className="flex justify-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 text-primary ring-3 ring-primary/5">
                {ActiveIcon ? (
                  <ActiveIcon className="h-7 w-7" />
                ) : (
                  <Loader2 className="h-7 w-7 animate-spin" />
                )}
              </div>
            </div>

            {/* Title */}
            <div>
              <p className="text-[11px] font-medium text-primary/60 uppercase tracking-wider mb-0.5">
                Step {progress.currentStep}
              </p>
              <h2 className="text-lg font-semibold text-foreground">
                {currentStepConfig.label}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {currentStepConfig.description}
              </p>
            </div>

            {/* Why */}
            <div className="bg-muted/40 rounded-xl px-4 py-3 text-left">
              <p className="text-[13px] text-muted-foreground leading-relaxed">
                {currentStepConfig.whyDescription}
              </p>
            </div>

            {/* Loading */}
            <div className="flex items-center justify-center gap-2 text-sm text-primary/70">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>In corso...</span>
            </div>
          </div>
        )}

        {/* Mobile completed results */}
        {progress.stepResults && progress.stepResults.length > 0 && (
          <div className="w-full mt-5 pt-4 border-t border-border/30">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/60 mb-2">
              Risultati ottenuti
            </p>
            <div className="space-y-1.5">
              {progress.stepResults.map((sr) => (
                <div key={sr.step} className="flex items-start gap-2">
                  <Check className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[13px] font-medium text-foreground">{sr.label}</span>
                    {sr.result && (
                      <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{sr.result}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mobile objective */}
        <div className="w-full mt-5 pt-4 border-t border-border/30">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Target className="h-3 w-3 text-primary/60" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/60">
              Obiettivo finale
            </p>
          </div>
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            Generare un&apos;analisi bilanciata delle posizioni di tutti i gruppi parlamentari, con citazioni verificate dai discorsi in aula.
          </p>
        </div>
      </div>

      {/* ===== DESKTOP LAYOUT ===== */}
      {/* LEFT SIDEBAR: Step list + Objective */}
      <div className="hidden md:block w-64 lg:w-72 shrink-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-4">
          Pipeline di analisi
        </p>

        {/* Vertical step list */}
        <div className="space-y-1">
          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const isActive = stepNumber === progress.currentStep;
            const isComplete = stepNumber < progress.currentStep;
            const isPending = stepNumber > progress.currentStep;

            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-300",
                  isActive && "bg-primary/10",
                  isComplete && "opacity-80",
                  isPending && "opacity-30"
                )}
              >
                {/* Step indicator */}
                <div
                  className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium transition-all duration-300",
                    isComplete && "bg-primary text-primary-foreground",
                    isActive && "bg-primary/20 text-primary ring-2 ring-primary/40",
                    isPending && "bg-muted text-muted-foreground"
                  )}
                >
                  {isComplete ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : isActive ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    stepNumber
                  )}
                </div>

                {/* Label + short result */}
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      "text-sm leading-tight truncate transition-all duration-300",
                      isComplete && "text-primary font-medium",
                      isActive && "text-primary font-semibold",
                      isPending && "text-muted-foreground"
                    )}
                  >
                    {step.label}
                  </p>
                  {isComplete && getStepResult(stepNumber)?.result && (
                    <p className="text-[11px] text-muted-foreground truncate mt-0.5">
                      {getStepResult(stepNumber)!.result}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Objective */}
        <div className="mt-6 pt-5 border-t border-border/40">
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-3.5 w-3.5 text-primary/60" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60">
              Obiettivo
            </p>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Generare un&apos;analisi bilanciata delle posizioni di tutti i gruppi parlamentari, con citazioni verificate dai discorsi in aula.
          </p>
        </div>
      </div>

      {/* DESKTOP MAIN AREA: Active step detail */}
      <div className="hidden md:flex flex-1 flex-col items-center justify-center">
        {/* Progress bar */}
        <div className="w-full max-w-lg mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Progresso</span>
            <span className="text-xs font-medium text-primary">
              {progress.currentStep} / {steps.length}
            </span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Active step card */}
        {currentStepConfig && (
          <div className="w-full max-w-lg text-center space-y-5">
            {/* Icon */}
            <div className="flex justify-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-4 ring-primary/5">
                {ActiveIcon ? (
                  <ActiveIcon className="h-8 w-8" />
                ) : (
                  <Loader2 className="h-8 w-8 animate-spin" />
                )}
              </div>
            </div>

            {/* Step title */}
            <div>
              <p className="text-xs font-medium text-primary/60 uppercase tracking-wider mb-1">
                Step {progress.currentStep}
              </p>
              <h2 className="text-xl lg:text-2xl font-semibold text-foreground">
                {currentStepConfig.label}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                {currentStepConfig.description}
              </p>
            </div>

            {/* Why description */}
            <div className="bg-muted/40 rounded-xl px-6 py-4 text-left">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {currentStepConfig.whyDescription}
              </p>
            </div>

            {/* Loading indicator */}
            <div className="flex items-center justify-center gap-2 text-sm text-primary/70">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>In corso...</span>
            </div>
          </div>
        )}

        {/* Completed results summary */}
        {progress.stepResults && progress.stepResults.length > 0 && (
          <div className="w-full max-w-lg mt-8 pt-6 border-t border-border/30">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-3">
              Risultati ottenuti
            </p>
            <div className="space-y-2">
              {progress.stepResults.map((sr) => (
                <div key={sr.step} className="flex items-start gap-2.5">
                  <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-foreground">{sr.label}</span>
                    {sr.result && (
                      <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{sr.result}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
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
