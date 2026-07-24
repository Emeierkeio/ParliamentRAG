"use client";

import { useState, useEffect } from "react";
import { useTranslations } from 'next-intl';
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

/** Render rich step result details based on step type */
function StepResultDetails({ step, result, details, tPi }: { step: number; result?: string; details?: Record<string, unknown>; tPi: ReturnType<typeof useTranslations> }) {
  // Step 2: Commissioni — show commission name
  if (step === 2) {
    const commList = Array.isArray(details?.commissioni) ? details.commissioni as Array<Record<string, unknown>> : [];
    const topComm = commList[0];
    const topCommName = topComm ? (typeof topComm.nome === "string" ? topComm.nome : typeof topComm.name === "string" ? topComm.name : undefined) : undefined;
    if (topCommName) {
      return (
        <p className="text-[11px] text-primary font-medium mt-1">
          {tPi('stepResultCommissione')}: {topCommName}
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

  // Default: show result string; nothing to add when the step produced no result
  if (!result) return null;
  return (
    <p className="text-[11px] text-primary font-medium mt-1">
      {tPi('stepResultResult')}: {result}
    </p>
  );
}

/**
 * Sticky banner shown after the response text is visible (step 7+).
 * Rendered separately in ChatArea as a sticky element.
 */
export function ProgressBanner({ progress, className }: ProgressIndicatorProps) {
  const tPi = useTranslations('ProgressIndicator');
  if (!progress) return null;

  const textIsVisible = progress.stepResults?.some(r => r.step === 7);
  if (!textIsVisible || progress.isComplete) return null;

  const statusText = progress.currentStep <= 7
    ? tPi('writingCompletion')
    : tPi('waiting');

  return (
    <div className={cn(
      "sticky top-0 z-20 w-full bg-background/95 backdrop-blur-md border-b border-primary/10",
      "animate-in slide-in-from-top-2 duration-300",
      className
    )}></div>
  );
}

export function ProgressIndicator({ progress, className }: ProgressIndicatorProps) {
  const tPi = useTranslations('ProgressIndicator');
  const tPs = useTranslations('ProgressSteps');

  if (!progress || progress.isComplete) return null;

  const steps = config.ui.progressSteps;

  const getStepLabel = (id: number) => tPs(`step${id}.label` as Parameters<typeof tPs>[0]);
  const getStepDescription = (id: number) => tPs(`step${id}.description` as Parameters<typeof tPs>[0]);
  const getStepShortLabel = (id: number) => tPi(`shortLabels.${id}` as Parameters<typeof tPi>[0]);

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
                  <p className="font-semibold text-xs">{getStepLabel(step.id)}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {getStepDescription(step.id)}
                  </p>
                  {isComplete && (
                    <StepResultDetails step={stepNumber} result={getStepResult(stepNumber)?.result} details={getStepResult(stepNumber)?.details} tPi={tPi} />
                  )}
                  {isActive && (
                    <p className="text-[11px] text-primary/70 font-medium mt-1 italic">{tPi('inProgress')}</p>
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
                      <span className="lg:hidden">{getStepShortLabel(step.id)}</span>
                      <span className="hidden lg:inline">{getStepLabel(step.id)}</span>
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{getStepLabel(step.id)}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {getStepDescription(step.id)}
                  </p>
                  {isComplete && (
                    <StepResultDetails step={stepNumber} result={stepResult?.result} details={stepResult?.details} tPi={tPi} />
                  )}
                  {isActive && (
                    <p className="text-[11px] text-primary/70 font-medium mt-1 italic">
                      {tPi('inProgress')}
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
  const tPi = useTranslations('ProgressIndicator');
  const tPs = useTranslations('ProgressSteps');

  if (!progress) return null;

  const steps = config.ui.progressSteps;

  const getStepLabel = (id: number) => tPs(`step${id}.label` as Parameters<typeof tPs>[0]);
  const getStepDescription = (id: number) => tPs(`step${id}.description` as Parameters<typeof tPs>[0]);
  const getStepShortLabel = (id: number) => tPi(`shortLabels.${id}` as Parameters<typeof tPi>[0]);

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
                  <p className="font-semibold text-xs">{getStepLabel(step.id)}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {getStepDescription(step.id)}
                  </p>
                  <StepResultDetails step={stepNumber} result={stepResult?.result} details={stepResult?.details} tPi={tPi} />
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
              {getStepShortLabel(step.id)}
            </span>
          ))}
        </div>
      </div>

      {/* Desktop: completed stepper with connecting line and labels */}
      <div className="hidden sm:block">
        <div className="relative flex justify-between items-start">
          {/* Connecting line behind circles: spans first→last circle center */}
          <div
            className="absolute top-[13px] h-0.5 bg-primary/25 rounded-full"
            style={{
              left: `calc(100% / ${steps.length} / 2)`,
              right: `calc(100% / ${steps.length} / 2)`,
            }}
          />

          {steps.map((step, index) => {
            const stepNumber = index + 1;
            const stepResult = getStepResult(stepNumber);

            return (
              <Tooltip key={step.id} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div className="group flex flex-col items-center gap-1.5 cursor-pointer min-w-0 flex-1">
                    <div
                      className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium transition-all group-hover:ring-2 group-hover:ring-primary/30"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-[10px] leading-tight text-center text-muted-foreground font-medium truncate w-full px-0.5 transition-colors group-hover:text-primary">
                      <span className="lg:hidden">{getStepShortLabel(step.id)}</span>
                      <span className="hidden lg:inline">{getStepLabel(step.id)}</span>
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-[280px]">
                  <p className="font-semibold text-xs">{getStepLabel(step.id)}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {getStepDescription(step.id)}
                  </p>
                  <StepResultDetails step={stepNumber} result={stepResult?.result} details={stepResult?.details} tPi={tPi} />
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
  CheckCircle2,
};

/** Map step icon names to Lucide components (moved up) */
type SystemTourFeature = { icon: React.ComponentType<{ className?: string }>; titleKey: string; descKey: string };

const SYSTEM_TOUR_FEATURES_CONFIG: SystemTourFeature[] = [
  { icon: Search, titleKey: "tourSemanticSearch", descKey: "tourSemanticSearchDesc" },
  { icon: Users, titleKey: "tourExpertsPerTopic", descKey: "tourExpertsPerTopicDesc" },
  { icon: Compass, titleKey: "tourIdeologicalCompass", descKey: "tourIdeologicalCompassDesc" },
  { icon: MessageSquare, titleKey: "tourVerifiedCitations", descKey: "tourVerifiedCitationsDesc" },
  { icon: BarChart3, titleKey: "tourBalance", descKey: "tourBalanceDesc" },
  { icon: Landmark, titleKey: "tourCommittees", descKey: "tourCommitteesDesc" },
];

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
  const tPi = useTranslations('ProgressIndicator');
  const tPs = useTranslations('ProgressSteps');

  const getStepLabel = (id: number) => tPs(`step${id}.label` as Parameters<typeof tPs>[0]);
  const getStepDescription = (id: number) => tPs(`step${id}.description` as Parameters<typeof tPs>[0]);
  const getStepWhyDescription = (id: number) => tPs(`step${id}.whyDescription` as Parameters<typeof tPs>[0]);

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
    const ahead = progress.aheadCount;
    const active = progress.activeCount ?? 0;

    const formatElapsed = (s: number) =>
      s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;

    // Estimated wait: ~45s per slot ahead (rough average pipeline time)
    const estimatedSec = ahead != null && ahead > 0 ? ahead * 45 : null;
    const formatEstimate = (s: number) =>
      s < 60 ? `~${s}s` : `~${Math.ceil(s / 60)} min`;

    const isNext = ahead === 0;

    return (
      <div className={cn(
        "flex flex-col items-center justify-center w-full min-h-[50vh] md:min-h-[60vh] py-10 px-6 text-center",
        className
      )}>

        {/* Icon */}
        <div className="relative mb-6">
          {isNext ? (
            <>
              <div className="absolute -inset-3 rounded-full bg-green-400/20 animate-pulse" />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-green-50 border border-green-200 text-green-600 shadow-sm">
                <Clock className="h-8 w-8" />
              </div>
            </>
          ) : (
            <>
              <div className="absolute -inset-4 rounded-full bg-amber-400/10 animate-ping" style={{ animationDuration: "2s" }} />
              <div className="absolute -inset-2 rounded-full bg-amber-400/8 animate-pulse" />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 shadow-sm">
                <Clock className="h-8 w-8" />
              </div>
            </>
          )}
        </div>

        {/* Primary message */}
        {isNext ? (
          <>
            <h2 className="[font-family:var(--font-display)] text-xl font-semibold tracking-tight text-green-700 mb-1">
              {tPi('youreNext')}
            </h2>
            <p className="text-sm text-muted-foreground max-w-xs mb-6">
              {tPi('youreNextDesc')}
            </p>
          </>
        ) : ahead != null ? (
          <>
            <h2 className="[font-family:var(--font-display)] text-xl font-semibold tracking-tight text-foreground mb-1">
              {tPi('systemFull')}
            </h2>
            <p className="text-sm text-muted-foreground max-w-xs mb-6">
              {ahead === 1
                ? <><span className="font-semibold text-amber-600">{tPi('systemFullOneAhead', { ahead })}</span></>
                : <><span className="font-semibold text-amber-600">{tPi('systemFullManyAhead', { ahead })}</span></>
              }
              {" "}{tPi('systemFullWillProcess')}
            </p>
          </>
        ) : (
          <>
            <h2 className="[font-family:var(--font-display)] text-xl font-semibold tracking-tight text-foreground mb-1">
              {tPi('systemFull')}
            </h2>
            <p className="text-sm text-muted-foreground max-w-xs mb-6">
              {tPi('systemFullQueued')}
            </p>
          </>
        )}

        {/* Queue visualizer: people ahead → arrow → YOU */}
        {(ahead != null || active > 0) && (
          <div className="flex items-center gap-2 mb-6">
            {/* Ahead slots (max 5 shown) */}
            {ahead != null && ahead > 0 && (() => {
              const show = Math.min(ahead, 5);
              const extra = ahead > 5 ? ahead - 5 : 0;
              return (
                <div className="flex items-center gap-1.5">
                  {Array.from({ length: show }).map((_, i) => (
                    <div key={i} className="flex flex-col items-center gap-1">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted border border-border/60">
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      </div>
                      <span className="text-[8px] text-muted-foreground/60 uppercase tracking-wide">{tPi('waitingSlot')}</span>
                    </div>
                  ))}
                  {extra > 0 && (
                    <div className="flex flex-col items-center gap-1">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted border border-border/60 text-muted-foreground text-xs font-semibold">
                        +{extra}
                      </div>
                      <span className="text-[8px] text-muted-foreground/60 uppercase tracking-wide">{tPi('waitingSlot')}</span>
                    </div>
                  )}
                  {/* Arrow */}
                  <svg width="16" height="10" viewBox="0 0 20 12" className="mx-1 text-muted-foreground/30 fill-current shrink-0">
                    <path d="M13.5 0L20 6l-6.5 6V8H0V4h13.5V0z" />
                  </svg>
                </div>
              );
            })()}

            {/* Active processing slots */}
            {active > 0 && (() => {
              const showActive = Math.min(active, 3);
              const extraActive = active > 3 ? active - 3 : 0;
              return (
                <div className="flex items-center gap-1.5">
                  {Array.from({ length: showActive }).map((_, i) => (
                    <div key={i} className="flex flex-col items-center gap-1">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 border border-primary/20">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                      </div>
                      <span className="text-[8px] text-primary/60 uppercase tracking-wide font-medium">{tPi('processingSlot')}</span>
                    </div>
                  ))}
                  {extraActive > 0 && (
                    <div className="flex flex-col items-center gap-1">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 text-primary text-xs font-semibold">
                        +{extraActive}
                      </div>
                      <span className="text-[8px] text-primary/60 uppercase tracking-wide font-medium">{tPi('processingSlot')}</span>
                    </div>
                  )}
                  {/* Arrow to user */}
                  <svg width="16" height="10" viewBox="0 0 20 12" className="mx-1 text-muted-foreground/30 fill-current shrink-0">
                    <path d="M13.5 0L20 6l-6.5 6V8H0V4h13.5V0z" />
                  </svg>
                </div>
              );
            })()}

            {/* User slot */}
            <div className="flex flex-col items-center gap-1">
              <div className={cn(
                "relative flex h-10 w-10 items-center justify-center rounded-xl border-2 ring-4",
                isNext
                  ? "bg-green-50 border-green-400 ring-green-400/20"
                  : "bg-amber-50 border-amber-400 ring-amber-400/20"
              )}>
                {!isNext && <div className="absolute inset-0 rounded-xl bg-amber-400/20 animate-pulse" />}
                {pos !== undefined ? (
                  <span className={cn("relative text-xs font-bold", isNext ? "text-green-700" : "text-amber-700")}>
                    #{pos}
                  </span>
                ) : (
                  <Clock className="h-4 w-4 text-amber-600" />
                )}
              </div>
              <span className={cn(
                "text-[8px] font-semibold uppercase tracking-wide",
                isNext ? "text-green-600" : "text-amber-600"
              )}>{tPi('you')}</span>
            </div>
          </div>
        )}

        {/* Stats row */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground mb-5">
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span>{tPi('waitingFor')} <span className="font-semibold tabular-nums">{formatElapsed(localElapsed)}</span></span>
          </div>
          {estimatedSec != null && (
            <>
              <div className="h-3 w-px bg-border" />
              <div className="flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                <span>{tPi('estimate')}: <span className="font-semibold tabular-nums">{formatEstimate(estimatedSec)}</span></span>
              </div>
            </>
          )}
        </div>

        {/* Reassuring note */}
        <p className="text-xs text-muted-foreground/50 max-w-xs leading-relaxed mb-10">
          {tPi('dontClose')}
        </p>

        {/* System tour while waiting */}
        <div className="w-full max-w-lg border-t border-border/30 pt-7">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/50 mb-4 text-center">
            {tPi('discoverWhileWaiting')}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {SYSTEM_TOUR_FEATURES_CONFIG.map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.titleKey}
                  className="flex flex-col gap-2 rounded-xl bg-muted/40 border border-border/40 px-3 py-3 text-left hover:bg-muted/70 transition-colors"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground leading-tight">{tPi(feat.titleKey as Parameters<typeof tPi>[0])}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{tPi(feat.descKey as Parameters<typeof tPi>[0])}</p>
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
            <span className="text-[11px] text-muted-foreground">{tPi('analysisInProgress')}</span>
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
              <h2 className="[font-family:var(--font-display)] text-xl font-semibold tracking-tight text-foreground">
                {getStepLabel(currentStepConfig.id)}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {getStepDescription(currentStepConfig.id)}
              </p>
            </div>

            {/* Why */}
            <div className="bg-muted/40 rounded-xl px-4 py-3 text-left">
              <p className="text-[13px] text-muted-foreground leading-relaxed">
                {getStepWhyDescription(currentStepConfig.id)}
              </p>
            </div>

            {/* Loading */}
            <div className="flex items-center justify-center gap-2 text-sm text-primary/70">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{tPi('inProgress')}</span>
            </div>
          </div>
        )}

        {/* Mobile completed results */}
        {progress.stepResults && progress.stepResults.length > 0 && (
          <div className="w-full mt-5 pt-4 border-t border-border/30">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/60 mb-2">
              {tPi('resultsObtained')}
            </p>
            <div className="space-y-1.5">
              {[...progress.stepResults].sort((a, b) => a.step - b.step).map((sr) => (
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
              {tPi('finalObjective')}
            </p>
          </div>
          <p className="text-[13px] text-muted-foreground leading-relaxed">
            {tPi('objectiveText')}
          </p>
        </div>
      </div>

      {/* ===== DESKTOP LAYOUT ===== */}
      {/* LEFT SIDEBAR: Step list + Objective */}
      <div className="hidden md:block w-64 lg:w-72 shrink-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-4">
          {tPi('analysisPipeline')}
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
                    {getStepLabel(step.id)}
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
              {tPi('objective')}
            </p>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {tPi('objectiveText')}
          </p>
        </div>
      </div>

      {/* DESKTOP MAIN AREA: Active step detail */}
      <div className="hidden md:flex flex-1 flex-col items-center justify-center">
        {/* Progress bar */}
        <div className="w-full max-w-lg mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">{tPi('progress')}</span>
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
              <h2 className="[font-family:var(--font-display)] text-2xl lg:text-[1.75rem] font-semibold tracking-tight text-foreground">
                {getStepLabel(currentStepConfig.id)}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                {getStepDescription(currentStepConfig.id)}
              </p>
            </div>

            {/* Why description */}
            <div className="bg-muted/40 rounded-xl px-6 py-4 text-left">
              <p className="text-sm text-muted-foreground leading-relaxed">
                {getStepWhyDescription(currentStepConfig.id)}
              </p>
            </div>

            {/* Loading indicator */}
            <div className="flex items-center justify-center gap-2 text-sm text-primary/70">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{tPi('inProgress')}</span>
            </div>
          </div>
        )}

        {/* Completed results summary */}
        {progress.stepResults && progress.stepResults.length > 0 && (
          <div className="w-full max-w-lg mt-8 pt-6 border-t border-border/30">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 mb-3">
              {tPi('resultsObtained')}
            </p>
            <div className="space-y-2">
              {[...progress.stepResults].sort((a, b) => a.step - b.step).map((sr) => (
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
