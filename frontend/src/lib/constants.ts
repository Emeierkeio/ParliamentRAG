/**
 * Shared constants for the ParliamentRAG frontend.
 */

// Suggested topics per lingua: le chip sono ANCHE le query inviate, quindi
// vanno nella lingua della UI (query inglese → risposta inglese, ecc.).
const TOPICS_BY_LOCALE: Record<string, readonly string[]> = {
  it: [
    "PNRR", "riforma sanitaria", "transizione energetica", "salario minimo",
    "conflitto in Ucraina", "autonomia differenziata",
    "riforma della giustizia", "flussi migratori",       ],
  en: [
    "PNRR", "healthcare reform", "energy transition", "minimum wage",
    "war in Ukraine", "differentiated autonomy",
    "justice reform", "migration flows",       ],
  fr: [
    "PNRR", "réforme de la santé", "transition énergétique", "salaire minimum",
    "guerre en Ukraine", "autonomie différenciée",
    "réforme de la justice", "flux migratoires",       ],
  de: [
    "PNRR", "Gesundheitsreform", "Energiewende", "Mindestlohn",
    "Krieg in der Ukraine", "differenzierte Autonomie",
    "Justizreform", "Migrationsströme",       ],
  es: [
    "PNRR", "reforma sanitaria", "transición energética", "salario mínimo",
    "guerra en Ucrania", "autonomía diferenciada",
    "reforma de la justicia", "flujos migratorios",       ],
  pt: [
    "PNRR", "reforma da saúde", "transição energética", "salário mínimo",
    "guerra na Ucrânia", "autonomia diferenciada",
    "reforma da justiça", "fluxos migratórios",       ],
};

export function getTopics(locale: string): readonly string[] {
  return TOPICS_BY_LOCALE[locale] ?? TOPICS_BY_LOCALE.it;
}

// Retrocompatibilità: default italiano
export const TOPICS = TOPICS_BY_LOCALE.it;
