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
      placeholder: "Chiedi qualcosa sui dibattiti parlamentari...",
      welcomeMessage: "Ciao! Sono il tuo assistente per l'analisi dei dibattiti parlamentari italiani. Posso aiutarti a esplorare le posizioni di tutte le forze politiche su qualsiasi tema.",
    },

    // Progress steps for RAG pipeline (synced with backend main.py)
    progressSteps: [
      { id: 1, label: "Analisi query", description: "Classificazione della domanda" },
      { id: 2, label: "Commissioni", description: "Identificazione commissioni pertinenti" },
      { id: 3, label: "Esperti", description: "Identificazione autorità per coalizione" },
      { id: 4, label: "Interventi", description: "Recupero interventi rilevanti" },
      { id: 5, label: "Statistiche", description: "Calcolo metriche di bilanciamento" },
      { id: 6, label: "Bussola Ideologica", description: "Analisi di posizionamento politico" },
      { id: 7, label: "Generazione", description: "Sintesi della risposta finale" },
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
    "Italia Viva": { color: "#E91E63", label: "Italia Viva - Il Centro - Renew Europe" },
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

// Type exports for configuration
export type Config = typeof config;
export type PoliticalGroup = keyof typeof config.politicalGroups;
export type ProgressStep = typeof config.ui.progressSteps[number];
