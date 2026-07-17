"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { useTranslations } from "next-intl";
import {
  Scale,
  Search,
  Sparkles,
  Zap,
  Clock,
  Target,
  Users,
  Briefcase,
  GraduationCap,
  FileText,
  MessageSquare,
  Shield,
  TrendingUp,
  BookOpen,
  Info,
  Network,
  Layers,
  SlidersHorizontal,
  Filter,
  Wand2,
  Settings2,
  CheckCircle2,
  BarChart3,
  PenLine,
  Bot,
  RefreshCcw,
} from "lucide-react";
import type { SystemConfig } from "@/lib/api";

// ─── Shared helpers ──────────────────────────────────────────

const WEIGHT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  profession: Briefcase,
  education: GraduationCap,
  committee: Users,
  acts: FileText,
  interventions: MessageSquare,
  role: Shield,
};

const MERGER_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  relevance: Target,
  diversity: Sparkles,
  coverage: Users,
  authority: Scale,
  salience: TrendingUp,
};

// ─── SubSection container ────────────────────────────────────

function SubSection({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-lg border bg-muted/20 p-3 space-y-3 ${className ?? ""}`}>
      <div className="flex items-center gap-1.5">
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</span>
      </div>
      {children}
    </div>
  );
}

// ─── ToggleSwitch ─────────────────────────────────────────────

function ToggleSwitch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={[
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        checked ? "bg-primary" : "bg-input",
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
      ].join(" ")}
    >
      <span
        className={[
          "pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform",
          checked ? "translate-x-4" : "translate-x-0",
        ].join(" ")}
      />
      {label && (
        <span className="sr-only">{label}</span>
      )}
    </button>
  );
}

// ─── InfoPopover ─────────────────────────────────────────────

function InfoPopover({ text }: { text: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground/50 hover:text-primary transition-colors focus:outline-none"
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-72 text-xs leading-relaxed" side="top" align="start">
        {text}
      </PopoverContent>
    </Popover>
  );
}

// ─── WeightSlider ─────────────────────────────────────────────

function WeightSlider({
  label,
  value,
  onChange,
  icon: Icon,
  info,
  step = 0.05,
  min = 0,
  max = 1,
  disabled,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  icon?: React.ComponentType<{ className?: string }>;
  info?: string;
  step?: number;
  min?: number;
  max?: number;
  disabled?: boolean;
}) {
  const percent = Math.round(((value - min) / (max - min)) * 100);
  return (
    <div className={`flex items-center gap-3 ${disabled ? "opacity-50" : ""}`}>
      {Icon && <Icon className="h-4 w-4 text-muted-foreground shrink-0" />}
      <div className="w-28 flex items-center gap-1 shrink-0">
        <Label className="text-sm leading-tight">{label}</Label>
        {info && <InfoPopover text={info} />}
      </div>
      <div className="flex-1 relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="weight-slider w-full cursor-pointer disabled:cursor-not-allowed"
          style={{
            ['--slider-fill' as string]: `${percent}%`,
          }}
        />
      </div>
      <Input
        type="number"
        step={step}
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={(e) => {
          const v = parseFloat(e.target.value);
          if (!isNaN(v)) onChange(v);
        }}
        className="w-20 text-center text-sm h-8"
      />
    </div>
  );
}

// ─── WeightSumBadge ───────────────────────────────────────────

function WeightSumBadge({ weights }: { weights: Record<string, number> }) {
  const sum = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(sum - 1.0) < 0.02;
  return (
    <Badge
      variant={isValid ? "default" : "destructive"}
      className="text-xs font-mono tabular-nums"
    >
      Σ = {sum.toFixed(2)}
    </Badge>
  );
}

// ─── LabelWithInfo ────────────────────────────────────────────

function LabelWithInfo({ children, info }: { children: React.ReactNode; info: string }) {
  return (
    <div className="flex items-center gap-1">
      <Label className="text-xs text-muted-foreground leading-tight">{children}</Label>
      <InfoPopover text={info} />
    </div>
  );
}

// ─── FieldWithUnit ────────────────────────────────────────────

function FieldWithUnit({
  label,
  info,
  unit,
  children,
}: {
  label: React.ReactNode;
  info: string;
  unit?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <LabelWithInfo info={info}>{label}</LabelWithInfo>
      <div className="flex items-center gap-2">
        {children}
        {unit && <span className="text-xs text-muted-foreground whitespace-nowrap">{unit}</span>}
      </div>
    </div>
  );
}

// ─── Retrieval Editor ────────────────────────────────────────

interface RetrievalEditorProps {
  data: SystemConfig["retrieval"];
  onChange: (data: SystemConfig["retrieval"]) => void;
}

export function RetrievalEditor({ data, onChange }: RetrievalEditorProps) {
  const t = useTranslations("GraphicalEditors");

  const update = (patch: Partial<SystemConfig["retrieval"]>) => {
    onChange({ ...data, ...patch });
  };

  const updateMergerWeight = (key: string, value: number) => {
    onChange({ ...data, merger_weights: { ...data.merger_weights, [key]: value } });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-blue-100 dark:bg-blue-950">
            <Search className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          </div>
          {t("retrieval.title")}
        </CardTitle>
        <CardDescription>{t("retrieval.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Dense Channel */}
        <SubSection icon={Zap} title={t("retrieval.denseChannel")}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={t("retrieval.topKResults")}
              info={t("retrieval.topKResultsInfo")}
              unit={t("generation.chunkUnit")}
            >
              <Input
                type="number" min={10} max={1000}
                value={data.dense_top_k}
                onChange={(e) => update({ dense_top_k: parseInt(e.target.value) || 200 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("retrieval.similarityThreshold")}
              info={t("retrieval.similarityThresholdInfo")}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.dense_similarity_threshold}
                onChange={(e) => update({ dense_similarity_threshold: parseFloat(e.target.value) || 0.3 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
          </div>
        </SubSection>

        {/* Graph Channel */}
        <SubSection icon={Network} title={t("retrieval.graphChannel")}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={t("retrieval.minLexicalMatch")}
              info={t("retrieval.minLexicalMatchInfo")}
              unit={t("queryRewriting.keywordUnit")}
            >
              <Input
                type="number" min={1} max={10}
                value={data.graph_lexical_min_match}
                onChange={(e) => update({ graph_lexical_min_match: parseInt(e.target.value) || 1 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("retrieval.semanticThreshold")}
              info={t("retrieval.semanticThresholdInfo")}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.graph_semantic_threshold}
                onChange={(e) => update({ graph_semantic_threshold: parseFloat(e.target.value) || 0.4 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("retrieval.graphChunkThreshold")}
              info={t("retrieval.graphChunkThresholdInfo")}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.graph_chunk_similarity_threshold}
                onChange={(e) => update({ graph_chunk_similarity_threshold: parseFloat(e.target.value) || 0.3 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("retrieval.maxActsPerQuery")}
              info={t("retrieval.maxActsPerQueryInfo")}
              unit={t("queryRewriting.actsUnit")}
            >
              <Input
                type="number" min={10} max={500}
                value={data.graph_max_acts_per_query}
                onChange={(e) => update({ graph_max_acts_per_query: parseInt(e.target.value) || 100 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
          </div>
        </SubSection>

        {/* Merger Weights */}
        <SubSection icon={Layers} title={t("retrieval.mergerWeights")}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{t("retrieval.weightsSumNote")}</span>
            <WeightSumBadge weights={data.merger_weights} />
          </div>
          <div className="space-y-2">
            {Object.entries(data.merger_weights).map(([key, value]) => {
              const Icon = MERGER_ICONS[key];
              return (
                <WeightSlider
                  key={key}
                  label={t(`mergerLabels.${key}.label`)}
                  value={value}
                  info={t(`mergerLabels.${key}.description`)}
                  onChange={(v) => updateMergerWeight(key, v)}
                  icon={Icon}
                />
              );
            })}
          </div>
        </SubSection>

      </CardContent>
    </Card>
  );
}

// ─── Authority Editor ────────────────────────────────────────

interface AuthorityEditorProps {
  data: SystemConfig["authority"];
  onChange: (data: SystemConfig["authority"]) => void;
}

export function AuthorityEditor({ data, onChange }: AuthorityEditorProps) {
  const t = useTranslations("GraphicalEditors");

  const updateWeight = (key: string, value: number) => {
    onChange({ ...data, weights: { ...data.weights, [key]: value } });
  };

  const updateField = (patch: Partial<SystemConfig["authority"]>) => {
    onChange({ ...data, ...patch });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-amber-100 dark:bg-amber-950">
            <Scale className="h-4 w-4 text-amber-600 dark:text-amber-400" />
          </div>
          {t("authority.title")}
        </CardTitle>
        <CardDescription>{t("authority.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Component Weights */}
        <SubSection icon={BarChart3} title={t("authority.componentWeights")}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{t("retrieval.weightsSumNote")}</span>
            <WeightSumBadge weights={data.weights} />
          </div>
          <div className="space-y-2">
            {Object.entries(data.weights).map(([key, value]) => {
              const Icon = WEIGHT_ICONS[key];
              return (
                <WeightSlider
                  key={key}
                  label={t(`weightLabels.${key}.label`)}
                  value={value}
                  info={t(`weightLabels.${key}.description`)}
                  onChange={(v) => updateWeight(key, v)}
                  icon={Icon}
                />
              );
            })}
          </div>
        </SubSection>

        {/* Time Decay */}
        <SubSection icon={Clock} title={t("authority.timeDecay")}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={t("authority.halfLifeActs")}
              info={t("authority.halfLifeActsInfo")}
              unit={t("authority.days")}
            >
              <Input
                type="number" min={30} max={3650}
                value={data.time_decay_acts_half_life}
                onChange={(e) => updateField({ time_decay_acts_half_life: parseInt(e.target.value) || 365 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("authority.halfLifeInterventions")}
              info={t("authority.halfLifeInterventionsInfo")}
              unit={t("authority.days")}
            >
              <Input
                type="number" min={30} max={3650}
                value={data.time_decay_speeches_half_life}
                onChange={(e) => updateField({ time_decay_speeches_half_life: parseInt(e.target.value) || 180 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
          </div>
        </SubSection>

        {/* Relevance Thresholds */}
        <SubSection icon={Filter} title={t("authority.relevanceThresholds")}>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t("authority.relevanceThresholdsDescription")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={t("authority.actsRelevanceThreshold")}
              info={t("authority.actsRelevanceThresholdInfo")}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.acts_relevance_threshold}
                onChange={(e) => updateField({ acts_relevance_threshold: parseFloat(e.target.value) || 0.25 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("authority.interventionsRelevanceThreshold")}
              info={t("authority.interventionsRelevanceThresholdInfo")}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.interventions_relevance_threshold}
                onChange={(e) => updateField({ interventions_relevance_threshold: parseFloat(e.target.value) || 0.25 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
          </div>
        </SubSection>

        {/* Advanced */}
        <SubSection icon={Settings2} title={t("authority.advanced")}>
          <FieldWithUnit
            label={t("authority.maxComponentContribution")}
            info={t("authority.maxComponentContributionInfo")}
          >
            <Input
              type="number" step={0.05} min={0} max={1}
              value={data.max_component_contribution}
              onChange={(e) => updateField({ max_component_contribution: parseFloat(e.target.value) || 0.8 })}
              className="h-8 w-28"
            />
          </FieldWithUnit>
        </SubSection>

      </CardContent>
    </Card>
  );
}

// ─── Generation Editor ───────────────────────────────────────

interface GenerationEditorProps {
  data: SystemConfig["generation"];
  onChange: (data: SystemConfig["generation"]) => void;
}

const MODEL_OPTIONS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"];

const STAGE_KEYS = ["analyst", "writer", "integrator"] as const;

export function GenerationEditor({ data, onChange }: GenerationEditorProps) {
  const t = useTranslations("GraphicalEditors");

  const updateModel = (stage: string, model: string) => {
    onChange({ ...data, models: { ...data.models, [stage]: model } });
  };

  const updateParams = (patch: Partial<typeof data.parameters>) => {
    onChange({ ...data, parameters: { ...data.parameters, ...patch } });
  };

  const updatePositionBrief = (key: keyof typeof data.position_brief, value: number | boolean) => {
    onChange({ ...data, position_brief: { ...data.position_brief, [key]: value } });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-purple-100 dark:bg-purple-950">
            <Zap className="h-4 w-4 text-purple-600 dark:text-purple-400" />
          </div>
          {t("generation.title")}
        </CardTitle>
        <CardDescription>{t("generation.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Models */}
        <SubSection icon={Bot} title={t("generation.llmModels")}>
          <div className="space-y-2.5">
            {Object.entries(data.models).map(([stage, model]) => (
              <div key={stage} className="flex items-center gap-3">
                <div className="w-28 flex items-center gap-1 shrink-0">
                  <Label className="text-sm">
                    {t(`generation.${stage}`)}
                  </Label>
                  <InfoPopover text={t(`modelInfo.${stage}`)} />
                </div>
                <select
                  value={model}
                  onChange={(e) => updateModel(stage, e.target.value)}
                  className="flex-1 h-8 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {MODEL_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </SubSection>

        {/* LLM Parameters */}
        <SubSection icon={SlidersHorizontal} title={t("generation.llmParameters")}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <FieldWithUnit
              label={t("generation.maxTokenOutput")}
              info={t("generation.maxTokenOutputInfo")}
              unit={t("generation.tokenUnit")}
            >
              <Input
                type="number" min={500} max={16000} step={500}
                value={data.parameters.max_tokens}
                onChange={(e) => updateParams({ max_tokens: parseInt(e.target.value) || 4000 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("generation.temperature")}
              info={t("generation.temperatureInfo")}
            >
              <Input
                type="number" min={0} max={2} step={0.1}
                value={data.parameters.temperature}
                onChange={(e) => updateParams({ temperature: parseFloat(e.target.value) || 0.3 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("generation.topP")}
              info={t("generation.topPInfo")}
            >
              <Input
                type="number" min={0} max={1} step={0.05}
                value={data.parameters.top_p}
                onChange={(e) => updateParams({ top_p: parseFloat(e.target.value) || 1.0 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
          </div>
        </SubSection>

        {/* Position Brief */}
        <SubSection icon={BookOpen} title={t("generation.positionBrief")}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">{t("generation.enabled")}</span>
              <InfoPopover text={t("generation.enabledInfo")} />
            </div>
            <ToggleSwitch
              checked={data.position_brief.enabled}
              onChange={(v) => updatePositionBrief("enabled", v)}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <FieldWithUnit
              label={t("generation.maxChunksBrief")}
              info={t("generation.maxChunksBriefInfo")}
              unit={t("generation.chunkUnit")}
            >
              <Input
                type="number" min={1} max={20}
                value={data.position_brief.max_chunks}
                onChange={(e) => updatePositionBrief("max_chunks", parseInt(e.target.value) || 5)}
                className="h-8 flex-1"
                disabled={!data.position_brief.enabled}
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("generation.charsPerChunk")}
              info={t("generation.charsPerChunkInfo")}
              unit={t("generation.charUnit")}
            >
              <Input
                type="number" min={50} max={1000} step={50}
                value={data.position_brief.chars_per_chunk}
                onChange={(e) => updatePositionBrief("chars_per_chunk", parseInt(e.target.value) || 200)}
                className="h-8 flex-1"
                disabled={!data.position_brief.enabled}
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={t("generation.contextChars")}
              info={t("generation.contextCharsInfo")}
              unit={t("generation.charUnit")}
            >
              <Input
                type="number" min={100} max={2000} step={100}
                value={data.position_brief.context_chars}
                onChange={(e) => updatePositionBrief("context_chars", parseInt(e.target.value) || 500)}
                className="h-8 flex-1"
                disabled={!data.position_brief.enabled}
              />
            </FieldWithUnit>
          </div>
        </SubSection>

        {/* Behavior */}
        <SubSection icon={PenLine} title={t("generation.generationBehavior")}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">{t("generation.crossSynthesis")}</span>
              <InfoPopover text={t("generation.crossSynthesisInfo")} />
            </div>
            <ToggleSwitch
              checked={data.enable_synthesis}
              onChange={(v) => onChange({ ...data, enable_synthesis: v })}
            />
          </div>
          <div className="space-y-1.5">
            <LabelWithInfo info={t("generation.noEvidenceMessageInfo")}>
              {t("generation.noEvidenceMessage")}
            </LabelWithInfo>
            <Textarea
              value={data.no_evidence_message}
              onChange={(e) => onChange({ ...data, no_evidence_message: e.target.value })}
              className="text-sm min-h-[60px] resize-none"
              rows={2}
            />
          </div>
        </SubSection>

      </CardContent>
    </Card>
  );
}

// ─── Query Rewriting Editor ───────────────────────────────────

interface QueryRewritingEditorProps {
  data: SystemConfig["query_rewriting"];
  onChange: (data: SystemConfig["query_rewriting"]) => void;
}

const QR_MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"];

export function QueryRewritingEditor({ data, onChange }: QueryRewritingEditorProps) {
  const t = useTranslations("GraphicalEditors");

  const update = (patch: Partial<SystemConfig["query_rewriting"]>) => {
    onChange({ ...data, ...patch });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-green-100 dark:bg-green-950">
            <RefreshCcw className="h-4 w-4 text-green-600 dark:text-green-400" />
          </div>
          {t("queryRewriting.title")}
        </CardTitle>
        <CardDescription>{t("queryRewriting.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <SubSection icon={Wand2} title={t("queryRewriting.configuration")}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">{t("queryRewriting.enabled")}</span>
              <InfoPopover text={t("queryRewriting.enabledInfo")} />
            </div>
            <ToggleSwitch
              checked={data.enabled}
              onChange={(v) => update({ enabled: v })}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <LabelWithInfo info={t("queryRewriting.modelInfo")}>
                {t("queryRewriting.model")}
              </LabelWithInfo>
              <select
                value={data.model}
                onChange={(e) => update({ model: e.target.value })}
                disabled={!data.enabled}
                className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {QR_MODEL_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <FieldWithUnit
              label={t("queryRewriting.maxWords")}
              info={t("queryRewriting.maxWordsInfo")}
              unit={t("queryRewriting.wordsUnit")}
            >
              <Input
                type="number" min={1} max={20}
                value={data.max_query_words}
                disabled={!data.enabled}
                onChange={(e) => update({ max_query_words: parseInt(e.target.value) || 5 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
          </div>
        </SubSection>
      </CardContent>
    </Card>
  );
}
