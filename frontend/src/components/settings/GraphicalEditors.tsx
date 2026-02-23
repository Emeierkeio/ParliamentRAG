"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
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
  Info,
} from "lucide-react";
import type { SystemConfig } from "@/lib/api";

// ─── Shared helpers ──────────────────────────────────────────

const WEIGHT_LABELS: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; description: string }> = {
  profession: { label: "Professione", icon: Briefcase, description: "Contributo della professione pre-parlamentare all'authority score. Un parlamentare con background medico o giuridico ha expertise specifica." },
  education: { label: "Istruzione", icon: GraduationCap, description: "Contributo del titolo di studio all'authority score. Lauree specialistiche e dottorati incrementano il peso." },
  committee: { label: "Commissioni", icon: Users, description: "Contributo dell'appartenenza a commissioni parlamentari tematicamente rilevanti alla query. Più alta è la pertinenza, maggiore il peso." },
  acts: { label: "Atti", icon: FileText, description: "Contributo al numero di atti parlamentari presentati (leggi, mozioni, interrogazioni), ponderati per recency tramite decadimento temporale." },
  interventions: { label: "Interventi", icon: MessageSquare, description: "Contributo al numero di interventi in aula ponderati per recency. Parlamentari attivi e recenti ottengono score più alti." },
  role: { label: "Ruolo", icon: Shield, description: "Contributo del ruolo istituzionale (Presidente, Ministro, Capogruppo, ecc.). Ruoli apicali ricevono un boost di autorevolezza." },
};

const MERGER_LABELS: Record<string, { label: string; description: string }> = {
  relevance: { label: "Rilevanza", description: "Peso del punteggio di similarità coseno tra l'embedding della query e quello del chunk. È il segnale di pertinenza base." },
  diversity: { label: "Diversità", description: "Penalizza i chunk dello stesso speaker per evitare che un singolo parlamentare domini i risultati, garantendo varietà di voci." },
  coverage: { label: "Copertura", description: "Premia la rappresentazione di più gruppi parlamentari nel ranking finale, favorendo la visione multi-partito." },
  authority: { label: "Autorità", description: "Ripondera i chunk in base all'authority score del parlamentare che ha pronunciato il discorso (expertise, ruolo, atti presentati)." },
  salience: { label: "Salienza", description: "Preferisce testi politicamente sostanziali rispetto a testi procedurali (es. 'Grazie Presidente, ha facoltà di parlare')." },
};

// ─── InfoPopover ─────────────────────────────────────────────

function InfoPopover({ text }: { text: string }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground/60 hover:text-primary transition-colors focus:outline-none"
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 text-xs leading-relaxed" side="top" align="start">
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
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  icon?: React.ComponentType<{ className?: string }>;
  info?: string;
  step?: number;
  min?: number;
  max?: number;
}) {
  return (
    <div className="flex items-center gap-3">
      {Icon && <Icon className="h-4 w-4 text-muted-foreground shrink-0" />}
      <div className="w-28 flex items-center gap-1 shrink-0">
        <Label className="text-sm">{label}</Label>
        {info && <InfoPopover text={info} />}
      </div>
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

// ─── LabelWithInfo ────────────────────────────────────────────

function LabelWithInfo({ children, info }: { children: React.ReactNode; info: string }) {
  return (
    <div className="flex items-center gap-1">
      <Label className="text-xs text-muted-foreground">{children}</Label>
      <InfoPopover text={info} />
    </div>
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
            <LabelWithInfo info="Numero massimo di chunk recuperati dal canale denso (embedding). Valori più alti aumentano il recall ma incrementano latenza e costo.">
              Dense Top-K
            </LabelWithInfo>
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
            <LabelWithInfo info="Soglia minima di cosine similarity per il canale denso. Chunk con similarità inferiore vengono scartati prima del ranking. Abbassarla aumenta il recall ma può introdurre rumore.">
              Soglia Similarità Dense
            </LabelWithInfo>
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
            <LabelWithInfo info="Numero minimo di keyword EuroVoc che devono matchare lessicalmente per includere un atto parlamentare nella ricerca grafo. Valore 1 = basta una keyword.">
              Graph Min Match Lessicale
            </LabelWithInfo>
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
            <LabelWithInfo info="Soglia di similarità semantica per il matching EuroVoc nel canale grafo. Controlla quanto strettamente il concetto EuroVoc deve corrispondere semanticamente alla query.">
              Soglia Semantica Graph
            </LabelWithInfo>
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
                info={meta?.description}
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
              info={meta?.description}
              onChange={(v) => updateWeight(key, v)}
              icon={meta?.icon}
            />
          );
        })}

        <Separator />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-1">
              <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                Half-life Atti (giorni)
              </Label>
              <InfoPopover text="Vita media in giorni per il decadimento temporale degli atti parlamentari. Un atto presentato 'half_life' giorni fa vale la metà di uno odierno. Valori bassi privilegiano l'attività recente." />
            </div>
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
            <div className="flex items-center gap-1">
              <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                Half-life Interventi (giorni)
              </Label>
              <InfoPopover text="Vita media in giorni per il decadimento temporale degli interventi in aula. Interventi recenti pesano di più nell'authority score rispetto a quelli lontani nel tempo." />
            </div>
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
            <LabelWithInfo info="Contributo massimo (cap) che una singola componente può apportare all'authority score finale. Previene che un solo fattore (es. numero di interventi) domini completamente il punteggio.">
              Max Contributo Componente
            </LabelWithInfo>
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

const MODEL_INFO: Record<string, string> = {
  analyst: "Stadio 1: decompone la query in claim tematici per partito. Usa gpt-4o-mini per efficienza, è un task strutturato e ripetitivo.",
  writer: "Stadio 2: scrive le sezioni per ogni gruppo parlamentare a partire dai chunk recuperati. Richiede alta qualità narrativa.",
  integrator: "Stadio 3: integra le sezioni in un testo coerente e bilanciato. Lo Stadio 4 (Citation Surgeon) è deterministico e non usa LLM.",
};

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
              <div className="w-28 flex items-center gap-1 shrink-0">
                <Label className="text-sm">
                  {stage === "analyst" ? "Analista" : stage === "writer" ? "Scrittore" : "Integratore"}
                </Label>
                {MODEL_INFO[stage] && <InfoPopover text={MODEL_INFO[stage]} />}
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

        <Separator />

        <div className="space-y-2">
          <span className="text-sm font-medium">Parametri LLM</span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-1">
                <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Hash className="h-3 w-3" />
                  Max Tokens
                </Label>
                <InfoPopover text="Numero massimo di token generati per risposta LLM. Valori più alti producono risposte più lunghe ma aumentano costo e latenza. 4000 è adeguato per sezioni partito dettagliate." />
              </div>
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
              <div className="flex items-center gap-1">
                <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Thermometer className="h-3 w-3" />
                  Temperature
                </Label>
                <InfoPopover text="Controlla la casualità dell'output LLM. 0 = completamente deterministico, 2 = molto creativo/casuale. Per analisi politica si raccomanda 0.2–0.4 per output precisi e riproducibili." />
              </div>
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
              <LabelWithInfo info="Nucleus sampling: a ogni passo il modello considera solo i token la cui probabilità cumulativa è ≤ Top-P. 1.0 = nessuna restrizione. Valori minori (es. 0.9) escludono le scelte meno probabili.">
                Top-P
              </LabelWithInfo>
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
            <div className="flex items-center gap-1.5">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Position Brief</span>
              <InfoPopover text="Fornisce allo scrittore un riassunto della posizione complessiva del gruppo parlamentare (top N chunk) prima che scriva la sezione. Migliora la coerenza ideologica delle citazioni selezionate." />
            </div>
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
              <LabelWithInfo info="Numero di chunk inclusi nel brief di posizione. Un numero maggiore fornisce più contesto allo scrittore ma aumenta i token in input.">
                Max Chunks Brief
              </LabelWithInfo>
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
              <LabelWithInfo info="Numero massimo di caratteri per chunk nel position brief. Tronca i chunk lunghi per mantenere il brief compatto e non sovraccaricare il contesto LLM.">
                Chars/Chunk
              </LabelWithInfo>
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
              <LabelWithInfo info="Caratteri di contesto mostrati per ogni elemento di evidenza nel brief (testo circostante la citazione). Più contesto aiuta lo scrittore a capire il tono e il significato dell'intervento.">
                Context Chars
              </LabelWithInfo>
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
