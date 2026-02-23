"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
  Thermometer,
  Hash,
  BookOpen,
} from "lucide-react";
import type { SystemConfig } from "@/lib/api";

// ─── Shared helpers ──────────────────────────────────────────

const WEIGHT_LABELS: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  profession: { label: "Professione", icon: Briefcase },
  education: { label: "Istruzione", icon: GraduationCap },
  committee: { label: "Commissioni", icon: Users },
  acts: { label: "Atti", icon: FileText },
  interventions: { label: "Interventi", icon: MessageSquare },
  role: { label: "Ruolo", icon: Shield },
};

const MERGER_LABELS: Record<string, { label: string; description: string }> = {
  relevance: { label: "Rilevanza", description: "Score di similarità base" },
  diversity: { label: "Diversità", description: "Penalizza dominanza stesso speaker" },
  coverage: { label: "Copertura", description: "Premia copertura partiti" },
  authority: { label: "Autorità", description: "Pesa l'autorevolezza" },
  salience: { label: "Salienza", description: "Preferisce testi politicamente sostanziali" },
};

function WeightSlider({
  label,
  value,
  onChange,
  icon: Icon,
  step = 0.05,
  min = 0,
  max = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  icon?: React.ComponentType<{ className?: string }>;
  step?: number;
  min?: number;
  max?: number;
}) {
  return (
    <div className="flex items-center gap-3">
      {Icon && <Icon className="h-4 w-4 text-muted-foreground shrink-0" />}
      <Label className="w-28 text-sm shrink-0">{label}</Label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="flex-1 h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
      />
      <Input
        type="number"
        step={step}
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const v = parseFloat(e.target.value);
          if (!isNaN(v)) onChange(v);
        }}
        className="w-20 text-center text-sm h-8"
      />
    </div>
  );
}

function WeightSumBadge({ weights }: { weights: Record<string, number> }) {
  const sum = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(sum - 1.0) < 0.02;
  return (
    <Badge variant={isValid ? "default" : "destructive"} className="text-xs">
      Somma: {sum.toFixed(2)}
    </Badge>
  );
}

// ─── Retrieval Editor ────────────────────────────────────────

interface RetrievalEditorProps {
  data: SystemConfig["retrieval"];
  onChange: (data: SystemConfig["retrieval"]) => void;
}

export function RetrievalEditor({ data, onChange }: RetrievalEditorProps) {
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
          <Search className="h-4 w-4 text-primary" />
          Retrieval
        </CardTitle>
        <CardDescription>Parametri di ricerca e fusione dei risultati</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Dense Top-K</Label>
            <Input
              type="number"
              min={10}
              max={1000}
              value={data.dense_top_k}
              onChange={(e) => update({ dense_top_k: parseInt(e.target.value) || 200 })}
              className="h-8"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Soglia Similarità Dense</Label>
            <Input
              type="number"
              step={0.05}
              min={0}
              max={1}
              value={data.dense_similarity_threshold}
              onChange={(e) => update({ dense_similarity_threshold: parseFloat(e.target.value) || 0.3 })}
              className="h-8"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Graph Min Match Lessicale</Label>
            <Input
              type="number"
              min={1}
              max={10}
              value={data.graph_lexical_min_match}
              onChange={(e) => update({ graph_lexical_min_match: parseInt(e.target.value) || 1 })}
              className="h-8"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Soglia Semantica Graph</Label>
            <Input
              type="number"
              step={0.05}
              min={0}
              max={1}
              value={data.graph_semantic_threshold}
              onChange={(e) => update({ graph_semantic_threshold: parseFloat(e.target.value) || 0.4 })}
              className="h-8"
            />
          </div>
        </div>

        <Separator />

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Pesi Merger</span>
            <WeightSumBadge weights={data.merger_weights} />
          </div>
          {Object.entries(data.merger_weights).map(([key, value]) => {
            const meta = MERGER_LABELS[key];
            return (
              <WeightSlider
                key={key}
                label={meta?.label || key}
                value={value}
                onChange={(v) => updateMergerWeight(key, v)}
                icon={key === "authority" ? Scale : key === "coverage" ? Users : key === "diversity" ? Sparkles : key === "salience" ? TrendingUp : Target}
              />
            );
          })}
        </div>
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
          <Scale className="h-4 w-4 text-primary" />
          Authority Score
        </CardTitle>
        <CardDescription>Pesi per il calcolo dello score di autorevolezza</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Pesi Componenti</span>
          <WeightSumBadge weights={data.weights} />
        </div>

        {Object.entries(data.weights).map(([key, value]) => {
          const meta = WEIGHT_LABELS[key];
          return (
            <WeightSlider
              key={key}
              label={meta?.label || key}
              value={value}
              onChange={(v) => updateWeight(key, v)}
              icon={meta?.icon}
            />
          );
        })}

        <Separator />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Clock className="h-3 w-3" />
              Half-life Atti (giorni)
            </Label>
            <Input
              type="number"
              min={30}
              max={3650}
              value={data.time_decay_acts_half_life}
              onChange={(e) => updateField({ time_decay_acts_half_life: parseInt(e.target.value) || 365 })}
              className="h-8"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Clock className="h-3 w-3" />
              Half-life Interventi (giorni)
            </Label>
            <Input
              type="number"
              min={30}
              max={3650}
              value={data.time_decay_speeches_half_life}
              onChange={(e) => updateField({ time_decay_speeches_half_life: parseInt(e.target.value) || 180 })}
              className="h-8"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Max Contributo Componente</Label>
            <Input
              type="number"
              step={0.05}
              min={0}
              max={1}
              value={data.max_component_contribution}
              onChange={(e) => updateField({ max_component_contribution: parseFloat(e.target.value) || 0.8 })}
              className="h-8"
            />
          </div>
        </div>
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

export function GenerationEditor({ data, onChange }: GenerationEditorProps) {
  const updateModel = (stage: string, model: string) => {
    onChange({ ...data, models: { ...data.models, [stage]: model } });
  };

  const updateParam = (key: keyof typeof data.parameters, value: number) => {
    onChange({ ...data, parameters: { ...data.parameters, [key]: value } });
  };

  const updatePositionBrief = (key: keyof typeof data.position_brief, value: number | boolean) => {
    onChange({ ...data, position_brief: { ...data.position_brief, [key]: value } });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Zap className="h-4 w-4 text-primary" />
          Generazione
        </CardTitle>
        <CardDescription>Modelli LLM per la pipeline di generazione a 4 stadi</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {Object.entries(data.models).map(([stage, model]) => (
            <div key={stage} className="flex items-center gap-3">
              <Label className="w-28 text-sm capitalize shrink-0">
                {stage === "analyst" ? "Analista" : stage === "writer" ? "Scrittore" : "Integratore"}
              </Label>
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

        <Separator />

        <div className="space-y-2">
          <span className="text-sm font-medium">Parametri LLM</span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                <Hash className="h-3 w-3" />
                Max Tokens
              </Label>
              <Input
                type="number"
                min={100}
                max={16000}
                step={100}
                value={data.parameters.max_tokens}
                onChange={(e) => updateParam("max_tokens", parseInt(e.target.value) || 4000)}
                className="h-8"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                <Thermometer className="h-3 w-3" />
                Temperature
              </Label>
              <Input
                type="number"
                min={0}
                max={2}
                step={0.05}
                value={data.parameters.temperature}
                onChange={(e) => updateParam("temperature", parseFloat(e.target.value) || 0.3)}
                className="h-8"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Top-P</Label>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={data.parameters.top_p}
                onChange={(e) => updateParam("top_p", parseFloat(e.target.value) || 1.0)}
                className="h-8"
              />
            </div>
          </div>
        </div>

        <Separator />

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium flex items-center gap-1.5">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              Position Brief
            </span>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={data.position_brief.enabled}
                onChange={(e) => updatePositionBrief("enabled", e.target.checked)}
                className="h-4 w-4 rounded border-input accent-primary"
              />
              <span className="text-xs text-muted-foreground">Abilitato</span>
            </label>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Max Chunks Brief</Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={data.position_brief.max_chunks}
                onChange={(e) => updatePositionBrief("max_chunks", parseInt(e.target.value) || 5)}
                className="h-8"
                disabled={!data.position_brief.enabled}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Chars/Chunk</Label>
              <Input
                type="number"
                min={50}
                max={1000}
                step={50}
                value={data.position_brief.chars_per_chunk}
                onChange={(e) => updatePositionBrief("chars_per_chunk", parseInt(e.target.value) || 200)}
                className="h-8"
                disabled={!data.position_brief.enabled}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Context Chars</Label>
              <Input
                type="number"
                min={100}
                max={2000}
                step={100}
                value={data.position_brief.context_chars}
                onChange={(e) => updatePositionBrief("context_chars", parseInt(e.target.value) || 500)}
                className="h-8"
                disabled={!data.position_brief.enabled}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
