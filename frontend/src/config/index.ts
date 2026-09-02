/**
 * Configurazione centralizzata dell'applicazione
 * Modifica questi valori per personalizzare il comportamento del frontend
 */

// Palette-dato dei gruppi parlamentari: UNICA sorgente per tutta l'app
// (compass, ranking, hemicycle, grafo, badge). Vietato ridefinire questi
// hex altrove — vedi DESIGN_SYSTEM.md.
export const PARTY_PALETTE = {
  FDI: { color: "#1F4E8C", abbrev: "FdI" },
  PD: { color: "#C6342C", abbrev: "PD" },
  M5S: { color: "#E3B505", abbrev: "M5S" },
  LEGA: { color: "#157F45", abbrev: "Lega" },
  FI: { color: "#2E9BD6", abbrev: "FI" },
  AVS: { color: "#7CA644", abbrev: "AVS" },
  AZIONE: { color: "#E8720C", abbrev: "Az" },
  IV: { color: "#C42B7A", abbrev: "IV" },
  NM: { color: "#4A6FA5", abbrev: "NM" },
  MISTO: { color: "#8A8A8A", abbrev: "Misto" },
  GOVERNO: { color: "#54428E", abbrev: "Gov" },
} as const;

export const config = {
  // App metadata
  app: {
    name: "ParliamentRAG",
    description: "Sistema RAG per l'analisi bilanciata dei dibattiti parlamentari italiani",
    version: "1.0.0",
  },

  // API Configuration
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "/api",
    timeout: 30000,
  },

  // UI Configuration
  ui: {
    // Sidebar
    sidebar: {
      defaultCollapsed: false,
      width: {
        expanded: 280,
        collapsed: 72,
      },
    },

    // Chat
    chat: {
      maxMessageLength: 4000,
    },

    // Progress steps for RAG pipeline (synced with backend main.py)
    // Labels and descriptions are in locale files under ProgressSteps namespace
    progressSteps: [
      { id: 1, icon: "Search" },
      { id: 2, icon: "Landmark" },
      { id: 3, icon: "Users" },
      { id: 4, icon: "MessageSquare" },
      { id: 5, icon: "BarChart3" },
      { id: 6, icon: "Compass" },
      { id: 7, icon: "PenTool" },
      { id: 8, icon: "CheckCircle2" },
    ],
  },

  // Political groups colors (for visualization) - full names matching backend
  politicalGroups: {
    // Full names (Canonical keys from backend)
    "FRATELLI D'ITALIA": { color: PARTY_PALETTE.FDI.color, label: "Fratelli d'Italia" },
    "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA": { color: PARTY_PALETTE.PD.color, label: "Partito Democratico - Italia Democratica e Progressista" },
    "MOVIMENTO 5 STELLE": { color: PARTY_PALETTE.M5S.color, label: "Movimento 5 Stelle" },
    "LEGA - SALVINI PREMIER": { color: PARTY_PALETTE.LEGA.color, label: "Lega - Salvini Premier" },
    "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE": { color: PARTY_PALETTE.FI.color, label: "Forza Italia - Berlusconi Presidente - PPE" },
    "ALLEANZA VERDI E SINISTRA": { color: PARTY_PALETTE.AVS.color, label: "Alleanza Verdi e Sinistra" },
    "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE": { color: PARTY_PALETTE.AZIONE.color, label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    "ITALIA VIVA-CASA RIFORMISTA (IV-CR)": { color: PARTY_PALETTE.IV.color, label: "Italia Viva - Casa Riformista" },
    "ITALIA VIVA-IL CENTRO-RENEW EUROPE": { color: PARTY_PALETTE.IV.color, label: "Italia Viva - Il Centro - Renew Europe" },
    "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC, ITALIA AL CENTRO)-MAIE": { color: PARTY_PALETTE.NM.color, label: "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC, Italia al Centro) - MAIE" },
    "MISTO": { color: PARTY_PALETTE.MISTO.color, label: "Gruppo Misto" },

    // Normalized display names (from backend normalize_party_name)
    "Fratelli d'Italia": { color: PARTY_PALETTE.FDI.color, label: "Fratelli d'Italia" },
    "Partito Democratico - Italia Democratica e Progressista": { color: PARTY_PALETTE.PD.color, label: "Partito Democratico - Italia Democratica e Progressista" },
    "Lega - Salvini Premier": { color: PARTY_PALETTE.LEGA.color, label: "Lega - Salvini Premier" },
    "Movimento 5 Stelle": { color: PARTY_PALETTE.M5S.color, label: "Movimento 5 Stelle" },
    "Forza Italia - Berlusconi Presidente - PPE": { color: PARTY_PALETTE.FI.color, label: "Forza Italia - Berlusconi Presidente - PPE" },
    "Alleanza Verdi e Sinistra": { color: PARTY_PALETTE.AVS.color, label: "Alleanza Verdi e Sinistra" },
    "Azione - Popolari Europeisti Riformatori - Renew Europe": { color: PARTY_PALETTE.AZIONE.color, label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    "Italia Viva - Casa Riformista": { color: PARTY_PALETTE.IV.color, label: "Italia Viva - Casa Riformista" },
    "Italia Viva - Il Centro - Renew Europe": { color: PARTY_PALETTE.IV.color, label: "Italia Viva - Il Centro - Renew Europe" },
    "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare": { color: PARTY_PALETTE.NM.color, label: "Noi Moderati - MAIE - Centro Popolare" },
    "Misto": { color: PARTY_PALETTE.MISTO.color, label: "Gruppo Misto" },
    "Governo": { color: PARTY_PALETTE.GOVERNO.color, label: "Governo" },

    // Aliases for common short names (robustness)
    "Lega": { color: PARTY_PALETTE.LEGA.color, label: "Lega - Salvini Premier" },
    "Forza Italia": { color: PARTY_PALETTE.FI.color, label: "Forza Italia - Berlusconi Presidente - PPE" },
    "Pd": { color: PARTY_PALETTE.PD.color, label: "Partito Democratico - Italia Democratica e Progressista" },
    "Partito Democratico": { color: PARTY_PALETTE.PD.color, label: "Partito Democratico - Italia Democratica e Progressista" },
    "M5S": { color: PARTY_PALETTE.M5S.color, label: "Movimento 5 Stelle" },
    "Azione": { color: PARTY_PALETTE.AZIONE.color, label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    "Italia Viva": { color: PARTY_PALETTE.IV.color, label: "Italia Viva - Casa Riformista" },
    "Noi Moderati": { color: PARTY_PALETTE.NM.color, label: "Noi Moderati - MAIE - Centro Popolare" },
    "Gruppo Misto": { color: PARTY_PALETTE.MISTO.color, label: "Gruppo Misto" },
  },

  // Authority score thresholds
  authorityScore: {
    high: 0.7,
    medium: 0.4,
    low: 0,
  },
} as const;

// Type exports for configuration
export type Config = typeof config;
export type PoliticalGroup = keyof typeof config.politicalGroups;
export type ProgressStep = { id: number; icon: string };

// Fuzzy match dei nomi gruppo provenienti dal backend (varianti maiuscole,
// suffissi elettorali, abbreviazioni) verso la palette-dato unica.
const PARTY_MATCHERS: Array<{ needle: string; key: keyof typeof PARTY_PALETTE }> = [
  { needle: "FRATELLI D'ITALIA", key: "FDI" },
  { needle: "PARTITO DEMOCRATICO", key: "PD" },
  { needle: "MOVIMENTO 5 STELLE", key: "M5S" },
  { needle: "LEGA", key: "LEGA" },
  { needle: "FORZA ITALIA", key: "FI" },
  { needle: "ALLEANZA VERDI", key: "AVS" },
  { needle: "AZIONE", key: "AZIONE" },
  { needle: "ITALIA VIVA", key: "IV" },
  { needle: "NOI MODERATI", key: "NM" },
  { needle: "GOVERNO", key: "GOVERNO" },
  { needle: "MISTO", key: "MISTO" },
];

export function getGroupColor(groupName: string): string {
  const exact = config.politicalGroups[groupName as PoliticalGroup];
  if (exact) return exact.color;
  const upper = groupName.toUpperCase();
  const match = PARTY_MATCHERS.find((m) => upper.includes(m.needle));
  return match ? PARTY_PALETTE[match.key].color : PARTY_PALETTE.MISTO.color;
}

export function getGroupAbbrev(groupName: string): string {
  const upper = groupName.toUpperCase();
  const match = PARTY_MATCHERS.find((m) => upper.includes(m.needle));
  return match ? PARTY_PALETTE[match.key].abbrev : groupName.slice(0, 6);
}
