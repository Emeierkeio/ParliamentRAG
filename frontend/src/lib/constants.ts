/**
 * Shared constants for the ParliamentRAG frontend.
 */

export const TOPICS = [
  "PNRR", "riforma sanitaria", "transizione energetica", "salario minimo",
  "conflitto in Ucraina", "riforma fiscale", "autonomia differenziata",
  "riforma della giustizia", "flussi migratori", "scuola e istruzione",
  "cambiamento climatico", "infrastrutture",
] as const;

// Trending topics of the XVIII legislature (2018-2022)
export const TOPICS_18 = [
  "reddito di cittadinanza", "quota 100", "emergenza Covid-19",
  "green pass e obbligo vaccinale", "decreti sicurezza",
  "taglio dei parlamentari", "PNRR", "riforma della prescrizione",
  "flussi migratori", "TAV Torino-Lione", "ex Ilva", "superbonus 110%",
] as const;

export const TOPICS_BY_LEGISLATURE: Record<18 | 19, readonly string[]> = {
  18: TOPICS_18,
  19: TOPICS,
};
