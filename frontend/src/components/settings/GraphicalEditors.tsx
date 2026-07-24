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
import { useLocale } from "next-intl";

// ─── Localized strings ───────────────────────────────────────

const STR = {
  it: {
    // Retrieval
    retrievalTitle: "Recupero Informazioni",
    retrievalDesc: "Parametri dei due canali di ricerca e del merger dei risultati",
    denseChannel: "Canale Denso — Embedding",
    topK: "Top-K Risultati",
    topKInfo: "Numero massimo di chunk recuperati per similarità semantica (embedding). Valori più alti aumentano il recall ma incrementano latenza e costo computazionale.",
    simThreshold: "Soglia Similarità",
    simThresholdInfo: "Soglia minima di similarità coseno per il canale denso. Chunk con similarità inferiore vengono scartati prima del ranking. Range tipico: 0.20–0.45.",
    graphChannel: "Canale Grafo — EuroVoc",
    minLexMatch: "Min Match Lessicale",
    minLexMatchInfo: "Numero minimo di keyword EuroVoc che devono matchare lessicalmente per includere un atto parlamentare nella ricerca grafo. Valore 1 = basta una keyword.",
    eurovocThreshold: "Soglia Semantica EuroVoc",
    eurovocThresholdInfo: "Soglia di similarità semantica per il matching EuroVoc. Controlla quanto strettamente il concetto EuroVoc deve corrispondere semanticamente alla query. Range tipico: 0.35–0.55.",
    graphChunkThreshold: "Soglia Chunk Grafo",
    graphChunkThresholdInfo: "Soglia minima di similarità per i chunk recuperati tramite traversata del grafo. Previene l'inclusione di chunk off-topic recuperati solo per co-firma di atti rilevanti.",
    maxActs: "Max Atti per Query",
    maxActsInfo: "Numero massimo di atti parlamentari da recuperare per query tramite il canale grafo. Limita il carico computazionale della traversata del grafo Neo4j.",
    mergerWeights: "Pesi Fusione — Merger",
    weightsMustSum: "I pesi devono sommare a 1.00",
    unitChunk: "chunk",
    unitKeyword: "keyword",
    unitActs: "atti",
    // Authority
    authorityTitle: "Authority Score",
    authorityDesc: "Pesi e soglie per il calcolo dello score di autorevolezza dei parlamentari",
    componentWeights: "Pesi Componenti",
    timeDecay: "Decadimento Temporale",
    actsHalfLife: "Half-life Atti",
    actsHalfLifeInfo: "Vita media in giorni per il decadimento temporale degli atti parlamentari. Un atto presentato 'half_life' giorni fa vale la metà di uno odierno. Valori bassi privilegiano l'attività recente.",
    speechesHalfLife: "Half-life Interventi",
    speechesHalfLifeInfo: "Vita media in giorni per il decadimento temporale degli interventi in aula. Interventi recenti pesano di più rispetto a quelli lontani nel tempo.",
    unitDays: "giorni",
    relevanceThresholds: "Soglie di Rilevanza",
    relevanceThresholdsDesc: "Similarità coseno minima tra l'embedding dell'atto/intervento e la query. Elementi sotto soglia vengono esclusi dal conteggio, indipendentemente dalla quantità.",
    actsRelevance: "Soglia Rilevanza Atti",
    actsRelevanceInfo: "Similarità coseno minima tra la descrizione dell'atto e la query per conteggiarlo nell'authority. Atti irrilevanti al topic non contribuiscono al punteggio. Range tipico: 0.20–0.35.",
    interventionsRelevance: "Soglia Rilevanza Interventi",
    interventionsRelevanceInfo: "Similarità coseno minima tra l'embedding dell'intervento e la query per conteggiarlo. Interventi off-topic non incrementano il punteggio del parlamentare. Range tipico: 0.20–0.35.",
    advancedParams: "Parametri Avanzati",
    maxComponentContribution: "Max Contributo Componente",
    maxComponentContributionInfo: "Contributo massimo (cap) che una singola componente può apportare all'authority score finale. Previene che un solo fattore (es. numero di interventi) domini completamente il punteggio.",
    // Generation
    generationTitle: "Generazione",
    generationDesc: "Modelli LLM della pipeline di generazione a 4 stadi",
    modelsSection: "Modelli LLM — Pipeline 4 Stadi",
    stageAnalyst: "Analista",
    stageWriter: "Scrittore",
    stageIntegrator: "Integratore",
    modelInfoAnalyst: "Stadio 1: decompone la query in claim tematici per partito. Task strutturato e ripetitivo — gpt-4.1-mini è sufficiente ed economico.",
    modelInfoWriter: "Stadio 2: scrive le sezioni per ogni gruppo parlamentare a partire dai chunk recuperati. Richiede alta qualità narrativa e fedeltà verbatim delle citazioni — gpt-4.1 raccomandato.",
    modelInfoIntegrator: "Stadio 3: integra le sezioni in un testo coerente e bilanciato. Lo Stadio 4 (Citation Surgeon) è deterministico e non usa LLM.",
    tempNote: "Temperatura e max token sono fissi per stadio, tarati nel codice (Analista 0.1, Scrittore 0.1, Integratore 0.0) per garantire citazioni verbatim riproducibili. Il cambio di modello è l'unica leva LLM con effetto reale ed è applicato a caldo alla prossima query.",
    positionBrief: "Position Brief",
    enabledM: "Abilitato",
    positionBriefInfo: "Fornisce allo scrittore un riassunto della posizione complessiva del gruppo parlamentare (top N chunk) prima che scriva la sezione. Migliora la coerenza ideologica delle citazioni selezionate.",
    maxChunksBrief: "Max Chunks Brief",
    maxChunksBriefInfo: "Numero di chunk inclusi nel brief di posizione. Più chunk forniscono più contesto ma aumentano i token in input e la latenza.",
    charsPerChunk: "Chars/Chunk",
    charsPerChunkInfo: "Numero massimo di caratteri per chunk nel brief. Tronca i chunk lunghi per mantenere il brief compatto.",
    contextChars: "Context Chars",
    contextCharsInfo: "Caratteri di contesto mostrati per ogni evidenza nel brief (testo circostante la citazione). Aiuta lo scrittore a capire il tono dell'intervento.",
    unitChar: "char",
    generationBehavior: "Comportamento Generazione",
    noEvidenceLabel: "Messaggio Assenza Evidenze",
    noEvidenceInfo: "Testo mostrato nella sezione del gruppo parlamentare quando non sono presenti interventi rilevanti nel corpus per quella query.",
    // Query Rewriting
    qrTitle: "Riscrittura Query",
    qrDesc: "Espansione automatica delle query brevi prima del retrieval",
    qrConfig: "Configurazione",
    enabledF: "Abilitata",
    qrEnabledInfo: "Se abilitata, le query brevi vengono riformulate e arricchite con termini correlati prima di essere inviate al retrieval. Migliora il recall per query ambigue o troppo sintetiche.",
    qrModel: "Modello",
    qrModelInfo: "Modello LLM usato per riscrivere le query. gpt-4.1-nano è raccomandato: è veloce, economico e sufficiente per questo task strutturato.",
    maxWords: "Max Parole per Riscrittura",
    maxWordsInfo: "Soglia massima di parole: query con un numero di parole uguale o inferiore vengono riscritte. Query già descrittive (più lunghe) vengono passate direttamente al retrieval.",
    unitWords: "parole",
  },
  en: {
    // Retrieval
    retrievalTitle: "Information Retrieval",
    retrievalDesc: "Parameters of the two retrieval channels and the result merger",
    denseChannel: "Dense Channel — Embedding",
    topK: "Top-K Results",
    topKInfo: "Maximum number of chunks retrieved by semantic similarity (embedding). Higher values increase recall but raise latency and computational cost.",
    simThreshold: "Similarity Threshold",
    simThresholdInfo: "Minimum cosine similarity threshold for the dense channel. Chunks with lower similarity are discarded before ranking. Typical range: 0.20–0.45.",
    graphChannel: "Graph Channel — EuroVoc",
    minLexMatch: "Min Lexical Match",
    minLexMatchInfo: "Minimum number of EuroVoc keywords that must match lexically to include a parliamentary act in the graph search. Value 1 = a single keyword is enough.",
    eurovocThreshold: "EuroVoc Semantic Threshold",
    eurovocThresholdInfo: "Semantic similarity threshold for EuroVoc matching. Controls how closely the EuroVoc concept must semantically match the query. Typical range: 0.35–0.55.",
    graphChunkThreshold: "Graph Chunk Threshold",
    graphChunkThresholdInfo: "Minimum similarity threshold for chunks retrieved via graph traversal. Prevents the inclusion of off-topic chunks retrieved only through co-signing of relevant acts.",
    maxActs: "Max Acts per Query",
    maxActsInfo: "Maximum number of parliamentary acts to retrieve per query through the graph channel. Limits the computational load of the Neo4j graph traversal.",
    mergerWeights: "Fusion Weights — Merger",
    weightsMustSum: "Weights must sum to 1.00",
    unitChunk: "chunks",
    unitKeyword: "keywords",
    unitActs: "acts",
    // Authority
    authorityTitle: "Authority Score",
    authorityDesc: "Weights and thresholds for computing the authority score of members of parliament",
    componentWeights: "Component Weights",
    timeDecay: "Time Decay",
    actsHalfLife: "Acts Half-life",
    actsHalfLifeInfo: "Half-life in days for the time decay of parliamentary acts. An act submitted 'half_life' days ago is worth half of one submitted today. Low values favor recent activity.",
    speechesHalfLife: "Speeches Half-life",
    speechesHalfLifeInfo: "Half-life in days for the time decay of floor speeches. Recent speeches weigh more than older ones.",
    unitDays: "days",
    relevanceThresholds: "Relevance Thresholds",
    relevanceThresholdsDesc: "Minimum cosine similarity between the act/speech embedding and the query. Items below the threshold are excluded from the count, regardless of quantity.",
    actsRelevance: "Acts Relevance Threshold",
    actsRelevanceInfo: "Minimum cosine similarity between the act description and the query for it to count towards authority. Acts irrelevant to the topic do not contribute to the score. Typical range: 0.20–0.35.",
    interventionsRelevance: "Speeches Relevance Threshold",
    interventionsRelevanceInfo: "Minimum cosine similarity between the speech embedding and the query for it to count. Off-topic speeches do not increase the member's score. Typical range: 0.20–0.35.",
    advancedParams: "Advanced Parameters",
    maxComponentContribution: "Max Component Contribution",
    maxComponentContributionInfo: "Maximum contribution (cap) a single component can bring to the final authority score. Prevents a single factor (e.g. number of speeches) from completely dominating the score.",
    // Generation
    generationTitle: "Generation",
    generationDesc: "LLM models of the 4-stage generation pipeline",
    modelsSection: "LLM Models — 4-Stage Pipeline",
    stageAnalyst: "Analyst",
    stageWriter: "Writer",
    stageIntegrator: "Integrator",
    modelInfoAnalyst: "Stage 1: decomposes the query into thematic claims per party. Structured, repetitive task — gpt-4.1-mini is sufficient and cost-effective.",
    modelInfoWriter: "Stage 2: writes the sections for each parliamentary group from the retrieved chunks. Requires high narrative quality and verbatim citation fidelity — gpt-4.1 recommended.",
    modelInfoIntegrator: "Stage 3: integrates the sections into a coherent, balanced text. Stage 4 (Citation Surgeon) is deterministic and does not use an LLM.",
    tempNote: "Temperature and max tokens are fixed per stage, tuned in code (Analyst 0.1, Writer 0.1, Integrator 0.0) to guarantee reproducible verbatim citations. Changing the model is the only LLM lever with real effect and is hot-applied on the next query.",
    positionBrief: "Position Brief",
    enabledM: "Enabled",
    positionBriefInfo: "Provides the writer with a summary of the parliamentary group's overall position (top N chunks) before it writes the section. Improves the ideological coherence of the selected citations.",
    maxChunksBrief: "Max Brief Chunks",
    maxChunksBriefInfo: "Number of chunks included in the position brief. More chunks provide more context but increase input tokens and latency.",
    charsPerChunk: "Chars/Chunk",
    charsPerChunkInfo: "Maximum number of characters per chunk in the brief. Truncates long chunks to keep the brief compact.",
    contextChars: "Context Chars",
    contextCharsInfo: "Context characters shown for each piece of evidence in the brief (text surrounding the citation). Helps the writer understand the tone of the speech.",
    unitChar: "chars",
    generationBehavior: "Generation Behavior",
    noEvidenceLabel: "No-Evidence Message",
    noEvidenceInfo: "Text shown in the parliamentary group's section when no relevant speeches are present in the corpus for that query.",
    // Query Rewriting
    qrTitle: "Query Rewriting",
    qrDesc: "Automatic expansion of short queries before retrieval",
    qrConfig: "Configuration",
    enabledF: "Enabled",
    qrEnabledInfo: "If enabled, short queries are reformulated and enriched with related terms before being sent to retrieval. Improves recall for ambiguous or overly terse queries.",
    qrModel: "Model",
    qrModelInfo: "LLM model used to rewrite queries. gpt-4.1-nano is recommended: fast, cheap and sufficient for this structured task.",
    maxWords: "Max Words for Rewriting",
    maxWordsInfo: "Maximum word threshold: queries with this many words or fewer are rewritten. Already descriptive (longer) queries are passed directly to retrieval.",
    unitWords: "words",
  },
} as const;

type Lang = "it" | "en";

function useLang(): Lang {
  const locale = useLocale();
  return locale === "it" ? "it" : "en";
}

// ─── Shared helpers ──────────────────────────────────────────

const WEIGHT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  profession: Briefcase,
  education: GraduationCap,
  committee: Users,
  acts: FileText,
  interventions: MessageSquare,
  role: Shield,
};

const WEIGHT_LABELS: Record<Lang, Record<string, { label: string; description: string }>> = {
  it: {
    profession: { label: "Professione", description: "Contributo della professione pre-parlamentare all'authority score. Un parlamentare con background medico o giuridico ha expertise specifica per query di settore." },
    education: { label: "Istruzione", description: "Contributo del titolo di studio all'authority score. Lauree specialistiche e dottorati in materia rilevante incrementano il peso." },
    committee: { label: "Commissioni", description: "Contributo dell'appartenenza a commissioni parlamentari tematicamente rilevanti rispetto alla query. Più alta è la pertinenza semantica, maggiore il peso." },
    acts: { label: "Atti", description: "Contributo al numero di atti parlamentari presentati (leggi, mozioni, interrogazioni), ponderati per recency tramite decadimento temporale esponenziale." },
    interventions: { label: "Interventi", description: "Contributo al numero di interventi in aula ponderati per recency. Parlamentari attivi e recenti ottengono score più alti rispetto a quelli inattivi." },
    role: { label: "Ruolo", description: "Contributo del ruolo istituzionale (Presidente, Ministro, Capogruppo, Sottosegretario, ecc.). Ruoli apicali ricevono un boost di autorevolezza." },
  },
  en: {
    profession: { label: "Profession", description: "Contribution of the pre-parliamentary profession to the authority score. A member with a medical or legal background has specific expertise for domain queries." },
    education: { label: "Education", description: "Contribution of the educational qualification to the authority score. Specialized degrees and PhDs in a relevant field increase the weight." },
    committee: { label: "Committees", description: "Contribution of membership in parliamentary committees thematically relevant to the query. The higher the semantic relevance, the greater the weight." },
    acts: { label: "Acts", description: "Contribution of the number of parliamentary acts submitted (bills, motions, interpellations), weighted for recency via exponential time decay." },
    interventions: { label: "Speeches", description: "Contribution of the number of floor speeches weighted for recency. Active, recent members obtain higher scores than inactive ones." },
    role: { label: "Role", description: "Contribution of the institutional role (President, Minister, Group Leader, Undersecretary, etc.). Top-level roles receive an authority boost." },
  },
};

const MERGER_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  relevance: Target,
  diversity: Sparkles,
  coverage: Users,
  authority: Scale,
  salience: TrendingUp,
};

const MERGER_LABELS: Record<Lang, Record<string, { label: string; description: string }>> = {
  it: {
    relevance: { label: "Rilevanza", description: "Peso della similarità coseno tra embedding query ed embedding chunk. È il segnale primario di pertinenza tematica." },
    diversity: { label: "Diversità", description: "Penalizza chunk dello stesso speaker per evitare che un singolo parlamentare domini i risultati, garantendo varietà di voci." },
    coverage: { label: "Copertura", description: "Premia la rappresentazione di più gruppi parlamentari nel ranking finale, favorendo la visione multi-partito." },
    authority: { label: "Autorità", description: "Ripondera i chunk in base all'authority score del parlamentare (expertise, ruolo, atti). Nota: la vera authority ranking avviene post-merge." },
    salience: { label: "Salienza", description: "Preferisce testi politicamente sostanziali rispetto a testi procedurali (es. 'Grazie Presidente, ha facoltà di parlare')." },
  },
  en: {
    relevance: { label: "Relevance", description: "Weight of the cosine similarity between the query embedding and the chunk embedding. It is the primary signal of topical relevance." },
    diversity: { label: "Diversity", description: "Penalizes chunks from the same speaker to prevent a single member from dominating the results, ensuring a variety of voices." },
    coverage: { label: "Coverage", description: "Rewards the representation of multiple parliamentary groups in the final ranking, favoring a multi-party view." },
    authority: { label: "Authority", description: "Re-weights chunks based on the member's authority score (expertise, role, acts). Note: the actual authority ranking happens post-merge." },
    salience: { label: "Salience", description: "Prefers politically substantive texts over procedural ones (e.g. 'Thank you Mr. President, you have the floor')." },
  },
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
  const lang = useLang();
  const S = STR[lang];
  const mergerLabels = MERGER_LABELS[lang];

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
          {S.retrievalTitle}
        </CardTitle>
        <CardDescription>{S.retrievalDesc}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Dense Channel */}
        <SubSection icon={Zap} title={S.denseChannel}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={S.topK}
              info={S.topKInfo}
              unit={S.unitChunk}
            >
              <Input
                type="number" min={10} max={1000}
                value={data.dense_top_k}
                onChange={(e) => update({ dense_top_k: parseInt(e.target.value) || 200 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={S.simThreshold}
              info={S.simThresholdInfo}
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
        <SubSection icon={Network} title={S.graphChannel}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={S.minLexMatch}
              info={S.minLexMatchInfo}
              unit={S.unitKeyword}
            >
              <Input
                type="number" min={1} max={10}
                value={data.graph_lexical_min_match}
                onChange={(e) => update({ graph_lexical_min_match: parseInt(e.target.value) || 1 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={S.eurovocThreshold}
              info={S.eurovocThresholdInfo}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.graph_semantic_threshold}
                onChange={(e) => update({ graph_semantic_threshold: parseFloat(e.target.value) || 0.4 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={S.graphChunkThreshold}
              info={S.graphChunkThresholdInfo}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.graph_chunk_similarity_threshold}
                onChange={(e) => update({ graph_chunk_similarity_threshold: parseFloat(e.target.value) || 0.3 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={S.maxActs}
              info={S.maxActsInfo}
              unit={S.unitActs}
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
        <SubSection icon={Layers} title={S.mergerWeights}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{S.weightsMustSum}</span>
            <WeightSumBadge weights={data.merger_weights} />
          </div>
          <div className="space-y-2">
            {Object.entries(data.merger_weights).map(([key, value]) => {
              const meta = mergerLabels[key];
              return (
                <WeightSlider
                  key={key}
                  label={meta?.label || key}
                  value={value}
                  info={meta?.description}
                  onChange={(v) => updateMergerWeight(key, v)}
                  icon={MERGER_ICONS[key]}
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
  const lang = useLang();
  const S = STR[lang];
  const weightLabels = WEIGHT_LABELS[lang];

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
          {S.authorityTitle}
        </CardTitle>
        <CardDescription>{S.authorityDesc}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Component Weights */}
        <SubSection icon={BarChart3} title={S.componentWeights}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{S.weightsMustSum}</span>
            <WeightSumBadge weights={data.weights} />
          </div>
          <div className="space-y-2">
            {Object.entries(data.weights).map(([key, value]) => {
              const meta = weightLabels[key];
              return (
                <WeightSlider
                  key={key}
                  label={meta?.label || key}
                  value={value}
                  info={meta?.description}
                  onChange={(v) => updateWeight(key, v)}
                  icon={WEIGHT_ICONS[key]}
                />
              );
            })}
          </div>
        </SubSection>

        {/* Time Decay */}
        <SubSection icon={Clock} title={S.timeDecay}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={S.actsHalfLife}
              info={S.actsHalfLifeInfo}
              unit={S.unitDays}
            >
              <Input
                type="number" min={30} max={3650}
                value={data.time_decay_acts_half_life}
                onChange={(e) => updateField({ time_decay_acts_half_life: parseInt(e.target.value) || 365 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={S.speechesHalfLife}
              info={S.speechesHalfLifeInfo}
              unit={S.unitDays}
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
        <SubSection icon={Filter} title={S.relevanceThresholds}>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {S.relevanceThresholdsDesc}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldWithUnit
              label={S.actsRelevance}
              info={S.actsRelevanceInfo}
            >
              <Input
                type="number" step={0.05} min={0} max={1}
                value={data.acts_relevance_threshold}
                onChange={(e) => updateField({ acts_relevance_threshold: parseFloat(e.target.value) || 0.25 })}
                className="h-8 flex-1"
              />
            </FieldWithUnit>
            <FieldWithUnit
              label={S.interventionsRelevance}
              info={S.interventionsRelevanceInfo}
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
        <SubSection icon={Settings2} title={S.advancedParams}>
          <FieldWithUnit
            label={S.maxComponentContribution}
            info={S.maxComponentContributionInfo}
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

const MODEL_OPTIONS = [
  "gpt-4.1",
  "gpt-4.1-mini",
  "gpt-4.1-nano",
  "gpt-4o",
  "gpt-4o-mini",
  "gpt-4-turbo",
  "gpt-3.5-turbo",
];

export function GenerationEditor({ data, onChange }: GenerationEditorProps) {
  const lang = useLang();
  const S = STR[lang];

  const modelInfo: Record<string, string> = {
    analyst: S.modelInfoAnalyst,
    writer: S.modelInfoWriter,
    integrator: S.modelInfoIntegrator,
  };

  const updateModel = (stage: string, model: string) => {
    onChange({ ...data, models: { ...data.models, [stage]: model } });
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
          {S.generationTitle}
        </CardTitle>
        <CardDescription>{S.generationDesc}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">

        {/* Models */}
        <SubSection icon={Bot} title={S.modelsSection}>
          <div className="space-y-2.5">
            {Object.entries(data.models).map(([stage, model]) => (
              <div key={stage} className="flex items-center gap-3">
                <div className="w-28 flex items-center gap-1 shrink-0">
                  <Label className="text-sm">
                    {stage === "analyst" ? S.stageAnalyst : stage === "writer" ? S.stageWriter : S.stageIntegrator}
                  </Label>
                  {modelInfo[stage] && <InfoPopover text={modelInfo[stage]} />}
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
            <p className="text-[11px] text-muted-foreground leading-relaxed pt-1">
              {S.tempNote}
            </p>
          </div>
        </SubSection>

        {/* Position Brief */}
        <SubSection icon={BookOpen} title={S.positionBrief}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">{S.enabledM}</span>
              <InfoPopover text={S.positionBriefInfo} />
            </div>
            <ToggleSwitch
              checked={data.position_brief.enabled}
              onChange={(v) => updatePositionBrief("enabled", v)}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <FieldWithUnit
              label={S.maxChunksBrief}
              info={S.maxChunksBriefInfo}
              unit={S.unitChunk}
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
              label={S.charsPerChunk}
              info={S.charsPerChunkInfo}
              unit={S.unitChar}
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
              label={S.contextChars}
              info={S.contextCharsInfo}
              unit={S.unitChar}
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
        <SubSection icon={PenLine} title={S.generationBehavior}>
          <div className="space-y-1.5">
            <LabelWithInfo info={S.noEvidenceInfo}>
              {S.noEvidenceLabel}
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

const QR_MODEL_OPTIONS = ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"];

export function QueryRewritingEditor({ data, onChange }: QueryRewritingEditorProps) {
  const lang = useLang();
  const S = STR[lang];

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
          {S.qrTitle}
        </CardTitle>
        <CardDescription>{S.qrDesc}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <SubSection icon={Wand2} title={S.qrConfig}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <span className="text-sm">{S.enabledF}</span>
              <InfoPopover text={S.qrEnabledInfo} />
            </div>
            <ToggleSwitch
              checked={data.enabled}
              onChange={(v) => update({ enabled: v })}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <LabelWithInfo info={S.qrModelInfo}>
                {S.qrModel}
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
              label={S.maxWords}
              info={S.maxWordsInfo}
              unit={S.unitWords}
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
