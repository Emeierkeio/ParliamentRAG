/**
 * Shared constants for the ParliamentRAG frontend.
 */

// Suggested topics per lingua: le chip sono ANCHE le query inviate, quindi
// vanno nella lingua della UI (query inglese → risposta inglese, ecc.).
const TOPICS_BY_LOCALE: Record<string, readonly string[]> = {
  it: [
    "PNRR", "riforma sanitaria", "transizione energetica", "salario minimo",
    "conflitto in Ucraina", "riforma fiscale", "autonomia differenziata",
    "riforma della giustizia", "flussi migratori", "scuola e istruzione",
    "cambiamento climatico", "infrastrutture",
  ],
  en: [
    "PNRR", "healthcare reform", "energy transition", "minimum wage",
    "war in Ukraine", "tax reform", "differentiated autonomy",
    "justice reform", "migration flows", "school and education",
    "climate change", "infrastructure",
  ],
  fr: [
    "PNRR", "réforme de la santé", "transition énergétique", "salaire minimum",
    "guerre en Ukraine", "réforme fiscale", "autonomie différenciée",
    "réforme de la justice", "flux migratoires", "école et éducation",
    "changement climatique", "infrastructures",
  ],
  de: [
    "PNRR", "Gesundheitsreform", "Energiewende", "Mindestlohn",
    "Krieg in der Ukraine", "Steuerreform", "differenzierte Autonomie",
    "Justizreform", "Migrationsströme", "Schule und Bildung",
    "Klimawandel", "Infrastruktur",
  ],
  es: [
    "PNRR", "reforma sanitaria", "transición energética", "salario mínimo",
    "guerra en Ucrania", "reforma fiscal", "autonomía diferenciada",
    "reforma de la justicia", "flujos migratorios", "escuela y educación",
    "cambio climático", "infraestructuras",
  ],
  pt: [
    "PNRR", "reforma da saúde", "transição energética", "salário mínimo",
    "guerra na Ucrânia", "reforma fiscal", "autonomia diferenciada",
    "reforma da justiça", "fluxos migratórios", "escola e educação",
    "alterações climáticas", "infraestruturas",
  ],
};

export function getTopics(locale: string): readonly string[] {
  return TOPICS_BY_LOCALE[locale] ?? TOPICS_BY_LOCALE.it;
}

// Retrocompatibilità: default italiano
export const TOPICS = TOPICS_BY_LOCALE.it;
