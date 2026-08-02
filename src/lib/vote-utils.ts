import type { VoteInfo } from "@/types/timeline";

/* La Camera pubblica le sedute recenti con label generico ("Votazione") e
   descrizione corta ("EM 6.21"); i label ricchi ("Votazione Emendamento
   1.104 PDL n. 0080") arrivano solo al consolidamento del dataset. Quando
   il subject da solo non dice nulla, il titolo unisce subject e
   descrizione. */
const GENERIC_SUBJECT = /^votazione( finale)?\.?$/i;

export function voteTitle(vote: VoteInfo): string | null {
  const subject = vote.subject?.trim() || null;
  const description = vote.description?.trim() || null;
  if (subject && !GENERIC_SUBJECT.test(subject)) return subject;
  if (subject && description) return `${subject} · ${description}`;
  return subject ?? description;
}

/* Il dataset non ha un campo "tipo di deliberazione": si classifica da
   subject/descrizione (più il flag finalVote), pattern osservati sia nei
   label consolidati sia nelle sigle delle sedute recenti. */
const KIND_PATTERNS: Array<[RegExp, string]> = [
  [/VOTO FINALE|VOTAZIONE FINALE/, "final"],
  [/FIDUCIA/, "confidence"],
  [/SUBEMENDAMENTO|EMENDAMENTO|\bEM\.?\s*\d|ART\.\s*AGG|ARTICOLO AGGIUNTIVO/, "amendment"],
  [/ARTICOLO|\bART\.?\s*\d/, "article"],
  [/ORDINE DEL GIORNO|\bODG\b/, "agenda"],
  [/RISOLUZIONE/, "resolution"],
  [/MOZIONE/, "motion"],
  [/PREGIUDIZIALE|SOSPENSIVA/, "preliminary"],
];

export function voteKind(vote: VoteInfo): string | null {
  if (vote.final_vote) return "final";
  const s = `${vote.subject ?? ""} ${vote.description ?? ""}`.toUpperCase();
  for (const [re, kind] of KIND_PATTERNS) if (re.test(s)) return kind;
  return null;
}

/* Chiavi i18n (namespace Timeline) per le etichette dei tipi. */
export const KIND_LABEL_KEYS: Record<string, string> = {
  final: "voteKindFinal",
  confidence: "voteKindConfidence",
  amendment: "voteKindAmendment",
  article: "voteKindArticle",
  agenda: "voteKindAgenda",
  resolution: "voteKindResolution",
  motion: "voteKindMotion",
  preliminary: "voteKindPreliminary",
};
