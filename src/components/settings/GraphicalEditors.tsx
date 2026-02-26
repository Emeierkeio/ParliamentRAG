"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
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

const WEIGHT_LABELS: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; description: string }> = {
  profession: { label: "Professione", icon: Briefcase, description: "Contributo della professione pre-parlamentare all'authority score. Un parlamentare con background medico o giuridico ha expertise specifica per query di settore." },
  education: { label: "Istruzione", icon: GraduationCap, description: "Contributo del titolo di studio all'authority score. Lauree specialistiche e dottorati in materia rilevante incrementano il peso." },
  committee: { label: "Commissioni", icon: Users, description: "Contributo dell'appartenenza a commissioni parlamentari tematicamente rilevanti rispetto alla query. Più alta è la pertinenza semantica, maggiore il peso." },
  acts: { label: "Atti", icon: FileText, description: "Contributo al numero di atti parlamentari presentati (leggi, mozioni, interrogazioni), ponderati per recency tramite decadimento temporale esponenziale." },
  interventions: { label: "Interventi", icon: MessageSquare, description: "Contributo al numero di interventi in aula ponderati per recency. Parlamentari attivi e recenti ottengono score più alti rispetto a quelli inattivi." },
  role: { label: "Ruolo", icon: Shield, description: "Contributo del ruolo istituzionale (Presidente, Ministro, Capogruppo, Sottosegretario, ecc.). Ruoli apicali ricevono un boost di autorevolezza." },
};

const MERGER_LABELS: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; description: string }> = {
  relevance: { label: "Rilevanza", icon: Target, description: "Peso della similarità coseno tra embedding query ed embedding chunk. È il segnale primario di pertinenza tematica." },
  diversity: { label: "Diversità", icon: Sparkles, description: "Penalizza chunk dello stesso speaker per evitare che un singolo parlamentare domini i risultati, garantendo varietà di voci." },
  coverage: { label: "Copertura", icon: Users, description: "Premia la rappresentazione di più gruppi parlamentari nel ranking finale, favorendo la visione multi-partito." },
  authority: { label: "Autorità", icon: Scale, description: "Ripondera i chunk in base all'authority score del parlamentare (expertise, ruolo, atti). Nota: la vera authority ranking avviene post-merge." },
  salience: { label: "Salienza", icon: TrendingUp, description: "Preferisce testi politicamente sostanziali rispetto a testi procedurali (es. 'Grazie Presidente, ha facoltà di parlare')." },
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
          className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-primary disabled:cursor-not-allowed"
          style={{
            background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${percent}%, hsl(var(--muted)) ${percent}%, hsl(var(--muted)) 100%)`,
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
          Recupero Informazioni
        </CardTitle>
        <CardDescription>Parametri dei due canali di ricerca e del merger dei risultati</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Dense Channel */}
        <SubSection icon={Zap} title="Canale Denso — Embedding">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label="Top-K Risultati"
              info="Numero massimo di chunk recuperati per similarità semantica (embedding). Valori più alti aumentano il recall ma incrementano latenza e costo computazionale."
              unit="chunk"
            >
              <Input
                type="number" min={10} max={1000}
                value={data.dense_top_k}
                onChange={(e) => update({ dense_top_k: parseInt(e.target.value) || 200 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Soglia Similarità"
              info="Soglia minima di similarità coseno per il canale denso. Chunk con similarità inferiore vengono scartati prima del ranking. Range tipico: 0.20–0.45."
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
        <SubSection icon={Network} title="Canale Grafo — EuroVoc">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label="Min Match Lessicale"
              info="Numero minimo di keyword EuroVoc che devono matchare lessicalmente per includere un atto parlamentare nella ricerca grafo. Valore 1 = basta una keyword."
              unit="keyword"
            >
              <Input
                type="number" min={1} max={10}
                value={data.graph_lexical_min_match}
                onChange={(e) => update({ graph_lexical_min_match: parseInt(e.target.value) || 1 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Soglia Semantica EuroVoc"
              info="Soglia di similarità semantica per il matching EuroVoc. Controlla quanto strettamente il concetto EuroVoc deve corrispondere semanticamente alla query. Range tipico: 0.35–0.55."
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.graph_semantic_threshold}
                onChange={(e) => update({ graph_semantic_threshold: parseFloat(e.target.value) || 0.4 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Soglia Chunk Grafo"
              info="Soglia minima di similarità per i chunk recuperati tramite traversata del grafo. Previene l'inclusione di chunk off-topic recuperati solo per co-firma di atti rilevanti."
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.graph_chunk_similarity_threshold}
                onChange={(e) => update({ graph_chunk_similarity_threshold: parseFloat(e.target.value) || 0.3 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Max Atti per Query"
              info="Numero massimo di atti parlamentari da recuperare per query tramite il canale grafo. Limita il carico computazionale della traversata del grafo Neo4j."
              unit="atti"
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
        <SubSection icon={Layers} title="Pesi Fusione — Merger">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">I pesi devono sommare a 1.00</span>
            <WeightSumBadge weights={data.merger_weights} />
          </div>
          <div className="space-y-2">
            {Object.entries(data.merger_weights).map(([key, value]) => {
              const meta = MERGER_LABELS[key];
              return (
                <WeightSlider
                  key={key}
                  label={meta?.label || key}
                  value={value}
                  info={meta?.description}
                  onChange={(v) => updateMergerWeight(key, v)}
                  icon={meta?.icon}
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
          Authority Score
        </CardTitle>
        <CardDescription>Pesi e soglie per il calcolo dello score di autorevolezza dei parlamentari</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Component Weights */}
        <SubSection icon={BarChart3} title="Pesi Componenti">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">I pesi devono sommare a 1.00</span>
            <WeightSumBadge weights={data.weights} />
          </div>
          <div className="space-y-2">
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
          </div>
        </SubSection>

        {/* Time Decay */}
        <SubSection icon={Clock} title="Decadimento Temporale">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label="Half-life Atti"
              info="Vita media in giorni per il decadimento temporale degli atti parlamentari. Un atto presentato 'half_life' giorni fa vale la metà di uno odierno. Valori bassi privilegiano l'attività recente."
              unit="giorni"
            >
              <Input
                type="number" min={30} max={3650}
                value={data.time_decay_acts_half_life}
                onChange={(e) => updateField({ time_decay_acts_half_life: parseInt(e.target.value) || 365 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Half-life Interventi"
              info="Vita media in giorni per il decadimento temporale degli interventi in aula. Interventi recenti pesano di più rispetto a quelli lontani nel tempo."
              unit="giorni"
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
        <SubSection icon={Filter} title="Soglie di Rilevanza">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Similarità coseno minima tra l'embedding dell'atto/intervento e la query. Elementi sotto soglia vengono esclusi dal conteggio, indipendentemente dalla quantità.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label="Soglia Rilevanza Atti"
              info="Similarità coseno minima tra la descrizione dell'atto e la query per conteggiarlo nell'authority. Atti irrilevanti al topic non contribuiscono al punteggio. Range tipico: 0.20–0.35."
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.acts_relevance_threshold}
                onChange={(e) => updateField({ acts_relevance_threshold: parseFloat(e.target.value) || 0.25 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Soglia Rilevanza Interventi"
              info="Similarità coseno minima tra l'embedding dell'intervento e la query per conteggiarlo. Interventi off-topic non incrementano il punteggio del parlamentare. Range tipico: 0.20–0.35."
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
        <SubSection icon={Settings2} title="Parametri Avanzati">
          <FieldWithUnit
            label="Max Contributo Componente"
            info="Contributo massimo (cap) che una singola componente può apportare all'authority score finale. Previene che un solo fattore (es. numero di interventi) domini completamente il punteggio."
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

const MODEL_INFO: Record<string, string> = {
  analyst: "Stadio 1: decompone la query in claim tematici per partito. Task strutturato e ripetitivo — gpt-4o-mini è sufficiente ed economico.",
  writer: "Stadio 2: scrive le sezioni per ogni gruppo parlamentare a partire dai chunk recuperati. Richiede alta qualità narrativa e coerenza ideologica.",
  integrator: "Stadio 3: integra le sezioni in un testo coerente e bilanciato. Lo Stadio 4 (Citation Surgeon) è deterministico e non usa LLM.",
};

export function GenerationEditor({ data, onChange }: GenerationEditorProps) {
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
          Generazione
        </CardTitle>
        <CardDescription>Modelli LLM e parametri della pipeline di generazione a 4 stadi</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Models */}
        <SubSection icon={Bot} title="Modelli LLM — Pipeline 4 Stadi">
          <div className="space-y-2.5">
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
        </SubSection>

        {/* LLM Parameters */}
        <SubSection icon={SlidersHorizontal} title="Parametri LLM">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <FieldWithUnit
              label="Max Token Output"
              info="Numero massimo di token generati per risposta. Aumentare per risposte più lunghe, ridurre per contenere i costi."
              unit="token"
            >
              <Input
                type="number" min={500} max={16000} step={500}
                value={data.parameters.max_tokens}
                onChange={(e) => updateParams({ max_tokens: parseInt(e.target.value) || 4000 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Temperatura"
              info="Creatività/randomicità del modello. 0 = deterministico e preciso, 1 = creativo e variabile. Per testi analitici 0.2–0.4 è ottimale."
            >
              <Input
                type="number" min={0} max={2} step={0.1}
                value={data.parameters.temperature}
                onChange={(e) => updateParams({ temperature: parseFloat(e.target.value) || 0.3 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label="Top-P (nucleus)"
              info="Nucleus sampling: considera solo i token con probabilità cumulativa fino a Top-P. 1.0 = nessun filtraggio. Abbassare a 0.9–0.95 per output più focalizzati."
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
        <SubSection icon={BookOpen} title="Position Brief">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">Abilitato</span>
              <InfoPopover text="Fornisce allo scrittore un riassunto della posizione complessiva del gruppo parlamentare (top N chunk) prima che scriva la sezione. Migliora la coerenza ideologica delle citazioni selezionate." />
            </div>
            <ToggleSwitch
              checked={data.position_brief.enabled}
              onChange={(v) => updatePositionBrief("enabled", v)}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <FieldWithUnit
              label="Max Chunks Brief"
              info="Numero di chunk inclusi nel brief di posizione. Più chunk forniscono più contesto ma aumentano i token in input e la latenza."
              unit="chunk"
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
              label="Chars/Chunk"
              info="Numero massimo di caratteri per chunk nel brief. Tronca i chunk lunghi per mantenere il brief compatto."
              unit="char"
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
              label="Context Chars"
              info="Caratteri di contesto mostrati per ogni evidenza nel brief (testo circostante la citazione). Aiuta lo scrittore a capire il tono dell'intervento."
              unit="char"
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
        <SubSection icon={PenLine} title="Comportamento Generazione">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">Sintesi Trasversale</span>
              <InfoPopover text="Abilita la sezione 'Analisi Trasversale' (Stadio 3.5): identifica pattern cross-party, convergenze e divergenze tra i gruppi parlamentari. Aumenta la lunghezza e il costo della risposta." />
            </div>
            <ToggleSwitch
              checked={data.enable_synthesis}
              onChange={(v) => onChange({ ...data, enable_synthesis: v })}
            />
          </div>
          <div className="space-y-1.5">
            <LabelWithInfo info="Testo mostrato nella sezione del gruppo parlamentare quando non sono presenti interventi rilevanti nel corpus per quella query.">
              Messaggio Assenza Evidenze
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
          Riscrittura Query
        </CardTitle>
        <CardDescription>Espansione automatica delle query brevi prima del retrieval</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <SubSection icon={Wand2} title="Configurazione">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">Abilitata</span>
              <InfoPopover text="Se abilitata, le query brevi vengono riformulate e arricchite con termini correlati prima di essere inviate al retrieval. Migliora il recall per query ambigue o troppo sintetiche." />
            </div>
            <ToggleSwitch
              checked={data.enabled}
              onChange={(v) => update({ enabled: v })}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <LabelWithInfo info="Modello LLM usato per riscrivere le query. gpt-4o-mini è raccomandato: è veloce, economico e sufficiente per questo task strutturato.">
                Modello
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
              label="Max Parole per Riscrittura"
              info="Soglia massima di parole: query con un numero di parole uguale o inferiore vengono riscritte. Query già descrittive (più lunghe) vengono passate direttamente al retrieval."
              unit="parole"
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
