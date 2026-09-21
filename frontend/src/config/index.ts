/**
 * Configurazione centralizzata dell'applicazione
 * Modifica questi valori per personalizzare il comportamento del frontend
 */

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
    "FRATELLI D'ITALIA": { color: "#1565C0", label: "Fratelli d'Italia" },
    "PARTITO DEMOCRATICO - ITALIA DEMOCRATICA E PROGRESSISTA": { color: "#E53935", label: "Partito Democratico - Italia Democratica e Progressista" },
    "MOVIMENTO 5 STELLE": { color: "#FFC107", label: "Movimento 5 Stelle" },
    "LEGA - SALVINI PREMIER": { color: "#4CAF50", label: "Lega - Salvini Premier" },
    "FORZA ITALIA - BERLUSCONI PRESIDENTE - PPE": { color: "#2196F3", label: "Forza Italia - Berlusconi Presidente - PPE" },
    "ALLEANZA VERDI E SINISTRA": { color: "#66BB6A", label: "Alleanza Verdi e Sinistra" },
    "AZIONE-POPOLARI EUROPEISTI RIFORMATORI-RENEW EUROPE": { color: "#FF9800", label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    "ITALIA VIVA-CASA RIFORMISTA (IV-CR)": { color: "#E91E63", label: "Italia Viva - Casa Riformista" },
    "ITALIA VIVA-IL CENTRO-RENEW EUROPE": { color: "#E91E63", label: "Italia Viva - Il Centro - Renew Europe" },
    "NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, UDC, ITALIA AL CENTRO)-MAIE": { color: "#9C27B0", label: "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC, Italia al Centro) - MAIE" },
    "MISTO": { color: "#9E9E9E", label: "Gruppo Misto" },

    // Normalized display names (from backend normalize_party_name)
    "Fratelli d'Italia": { color: "#1565C0", label: "Fratelli d'Italia" },
    "Partito Democratico - Italia Democratica e Progressista": { color: "#E53935", label: "Partito Democratico - Italia Democratica e Progressista" },
    "Lega - Salvini Premier": { color: "#4CAF50", label: "Lega - Salvini Premier" },
    "Movimento 5 Stelle": { color: "#FFC107", label: "Movimento 5 Stelle" },
    "Forza Italia - Berlusconi Presidente - PPE": { color: "#2196F3", label: "Forza Italia - Berlusconi Presidente - PPE" },
    "Alleanza Verdi e Sinistra": { color: "#66BB6A", label: "Alleanza Verdi e Sinistra" },
    "Azione - Popolari Europeisti Riformatori - Renew Europe": { color: "#FF9800", label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    "Italia Viva - Casa Riformista": { color: "#E91E63", label: "Italia Viva - Casa Riformista" },
    "Italia Viva - Il Centro - Renew Europe": { color: "#E91E63", label: "Italia Viva - Il Centro - Renew Europe" },
    "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare": { color: "#9C27B0", label: "Noi Moderati - MAIE - Centro Popolare" },
    "Misto": { color: "#9E9E9E", label: "Gruppo Misto" },
    "Governo": { color: "#4B0082", label: "Governo" },

    // Aliases for common short names (robustness)
    "Lega": { color: "#4CAF50", label: "Lega - Salvini Premier" },
    "Forza Italia": { color: "#2196F3", label: "Forza Italia - Berlusconi Presidente - PPE" },
    "Pd": { color: "#E53935", label: "Partito Democratico - Italia Democratica e Progressista" },
    "Partito Democratico": { color: "#E53935", label: "Partito Democratico - Italia Democratica e Progressista" },
    "M5S": { color: "#FFC107", label: "Movimento 5 Stelle" },
    "Azione": { color: "#FF9800", label: "Azione - Popolari Europeisti Riformatori - Renew Europe" },
    "Italia Viva": { color: "#E91E63", label: "Italia Viva - Casa Riformista" },
    "Noi Moderati": { color: "#9C27B0", label: "Noi Moderati - MAIE - Centro Popolare" },
    "Gruppo Misto": { color: "#9E9E9E", label: "Gruppo Misto" },
  },

  // Authority score thresholds
  authorityScore: {
    high: 0.7,
    medium: 0.4,
    low: 0,
  },
} as const;

/* Fuzzy group matching for graph spellings that differ from the canonical
   politicalGroups keys (needle order matters: first hit wins). Colors stay
   the canonical ones above so charts and entity pages agree. */
const PARTY_ABBREV: Record<string, string> = {
  "FRATELLI D'ITALIA": "FdI",
  "PARTITO DEMOCRATICO": "PD",
  "MOVIMENTO 5 STELLE": "M5S",
  "ALLEANZA VERDI": "AVS",
  "FORZA ITALIA": "FI",
  "AZIONE": "Az",
  "ITALIA VIVA": "IV",
  "NOI MODERATI": "NM",
  "LEGA": "Lega",
  "GOVERNO": "Gov",
  "MISTO": "Misto",
};

export function getGroupColor(groupName: string): string {
  const exact = (config.politicalGroups as Record<string, { color: string }>)[groupName];
  if (exact) return exact.color;
  const upper = groupName.toUpperCase();
  const needle = Object.keys(PARTY_ABBREV).find((n) => upper.includes(n));
  if (needle) {
    const entry = Object.entries(config.politicalGroups).find(([k]) =>
      k.toUpperCase().includes(needle)
    );
    if (entry) return (entry[1] as { color: string }).color;
  }
  return "#9E9E9E";
}

export function getGroupAbbrev(groupName: string): string {
  const upper = groupName.toUpperCase();
  const needle = Object.keys(PARTY_ABBREV).find((n) => upper.includes(n));
  return needle ? PARTY_ABBREV[needle] : groupName.slice(0, 6);
}

/* Party logos from the Wikipedia infobox images (see public/groups/).
   Groups without one (Misto, components) have no entry: callers fall
   back to the color dot. */
const PARTY_LOGO: Record<string, string> = {
  "FRATELLI D'ITALIA": "/groups/fdi.png",
  "PARTITO DEMOCRATICO": "/groups/pd.png",
  "MOVIMENTO 5 STELLE": "/groups/m5s.png",
  "ALLEANZA VERDI": "/groups/avs.png",
  "FORZA ITALIA": "/groups/fi.png",
  "AZIONE": "/groups/azione.jpg",
  "ITALIA VIVA": "/groups/iv.png",
  "NOI MODERATI": "/groups/nm.png",
  "LEGA": "/groups/lega.png",
};

export function getGroupLogo(groupName: string): string | null {
  const upper = groupName.toUpperCase();
  const needle = Object.keys(PARTY_LOGO).find((n) => upper.includes(n));
  return needle ? PARTY_LOGO[needle] : null;
}

// Type exports for configuration
export type Config = typeof config;
export type PoliticalGroup = keyof typeof config.politicalGroups;
export type ProgressStep = { id: number; icon: string };
