"""
Query rewriter: preprocessing semantico prima dell'embedding.

Pipeline a due stadi:
  1. Espansione acronimi — deterministica, zero costo, zero latenza.
  2. Espansione LLM — gpt-4o-mini, solo per query brevi/ambigue.

Il testo riscritto viene usato SOLO per l'embedding (dense channel).
La query originale resta invariata per il graph channel (keyword matching).
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# ─── Acronimi parlamentari italiani integrati ──────────────────────────────────
# Formato: SIGLA -> stringa con forma estesa + termini correlati
# I termini aggiuntivi ampliano il campo semantico catturato dall'embedding.

BUILT_IN_ACRONYMS: Dict[str, str] = {
    # Sanità
    "SSN": "Servizio Sanitario Nazionale sistema sanitario salute pubblica ospedali medici cure",
    "ASL": "Azienda Sanitaria Locale sanità territorio medici base pronto soccorso",
    "SSR": "Servizio Sanitario Regionale regioni sanità cure assistenza",
    "LEA": "Livelli Essenziali Assistenza prestazioni sanitarie diritto cura",
    "AIFA": "Agenzia Italiana Farmaco farmaci medicinali approvazione sicurezza",

    # Economia e Finanze
    "MEF": "Ministero Economia Finanze bilancio pubblico fisco erario entrate",
    "DEF": "Documento Economia Finanza manovra finanziaria legge bilancio previsioni",
    "PIL": "Prodotto Interno Lordo crescita economica ricchezza produzione nazionale",
    "IVA": "Imposta Valore Aggiunto tassa consumi aliquota fiscalità indiretta",
    "IRPEF": "Imposta Reddito Persone Fisiche tassa reddito contribuenti aliquote scaglioni",
    "IRES": "Imposta Reddito Società corporate tax fiscalità imprese tassazione",
    "IMU": "Imposta Municipale Unica casa immobili proprietà tassa locale",
    "IRAP": "Imposta Regionale Attività Produttive imprese regioni tassazione",
    "PNRR": "Piano Nazionale Ripresa Resilienza fondi europei Next Generation EU investimenti transizione",
    "NRP": "Piano Nazionale Ripresa Resilienza fondi europei investimenti",

    # Previdenza e Lavoro
    "INPS": "Istituto Nazionale Previdenza Sociale pensioni previdenza contributiva welfare",
    "INAIL": "Istituto Nazionale Assicurazione Infortuni Lavoro sicurezza lavoro infortuni",
    "TFR": "Trattamento Fine Rapporto liquidazione lavoratori previdenza complementare",
    "CIG": "Cassa Integrazione Guadagni ammortizzatori sociali crisi aziendale lavoro",
    "CIGS": "Cassa Integrazione Guadagni Straordinaria ristrutturazione aziendale crisi",
    "NASPI": "Indennità disoccupazione sussidio disoccupati ammortizzatori sociali lavoro",
    "RDC": "Reddito Cittadinanza sussidio povertà assistenza sociale welfare inclusione",
    "ADI": "Assegno Inclusione sostegno reddito povertà famiglie",

    # Ministeri
    "PCM": "Presidenza Consiglio Ministri governo premier decreto presidenza",
    "MiSE": "Ministero Sviluppo Economico imprese industria commercio innovazione",
    "MISE": "Ministero Sviluppo Economico imprese industria commercio innovazione",
    "MIM": "Ministero Istruzione Merito scuola università formazione istruzione pubblica",
    "MIUR": "Ministero Istruzione Università Ricerca scuola formazione accademia",
    "MIT": "Ministero Infrastrutture Trasporti mobilità strade ferrovie autostrade",
    "MAE": "Ministero Affari Esteri diplomazia relazioni internazionali ambasciata",
    "MAECI": "Ministero Affari Esteri Cooperazione Internazionale diplomazia esteri",
    "MITE": "Ministero Transizione Ecologica ambiente clima energia rinnovabili",
    "MASE": "Ministero Ambiente Sicurezza Energetica clima energia ambiente",
    "MDL": "Ministero Lavoro Politiche Sociali occupazione sindacati contratti",

    # Istituzioni italiane
    "CSM": "Consiglio Superiore Magistratura magistratura giudici nomine disciplina",
    "TAR": "Tribunale Amministrativo Regionale giustizia amministrativa ricorso annullamento",
    "CdS": "Consiglio Stato giustizia amministrativa appello sentenza",
    "CC": "Corte Costituzionale incostituzionalità diritti fondamentali sentenza",
    "CNEL": "Consiglio Nazionale Economia Lavoro partenariato sociale sindacati",
    "PA": "Pubblica Amministrazione burocrazia dipendenti pubblici enti statali riforma",
    "RA": "Regione Autonoma autonomia speciale statuto regionale",

    # Atti normativi
    "DL": "decreto legge provvedimento normativo urgenza governo conversione",
    "DLgs": "decreto legislativo delega legislativa attuazione legge",
    "DDL": "disegno legge proposta normativa governo parlamento iter",
    "PDL": "proposta legge iniziativa legislativa deputati parlamento",
    "OdG": "ordine giorno mozione parlamento camera senato votazione",
    "DM": "decreto ministeriale provvedimento ministero regolamentazione",
    "DPCM": "decreto presidente consiglio ministri provvedimento governo",

    # Europeo / Internazionale
    "UE": "Unione Europea istituzioni europee regolamenti direttive Bruxelles integrazione",
    "BCE": "Banca Centrale Europea politica monetaria tassi interesse inflazione euro",
    "BEI": "Banca Europea Investimenti finanziamenti prestiti progetti infrastrutture",
    "FMI": "Fondo Monetario Internazionale debito estero crisi finanziaria stabilizzazione",
    "NATO": "Alleanza Atlantica difesa militare sicurezza internazionale esercito",
    "ONU": "Organizzazione Nazioni Unite pace diritti umani cooperazione internazionale",
    "OCSE": "Organizzazione Cooperazione Sviluppo Economico paesi sviluppati economia",
    "G7": "Gruppo Sette potenze economiche summit cooperazione economia",
    "G20": "Gruppo Venti economie emergenti cooperazione internazionale economia",

    # Altro
    "PMI": "Piccole Medie Imprese imprenditori startup artigianato commercio",
    "CDP": "Cassa Depositi Prestiti investimenti infrastrutture finanziamenti pubblici",
    "ICT": "Tecnologie Informazione Comunicazione digitale innovazione software",
    "AI": "Intelligenza Artificiale machine learning automazione tecnologia digitale",
    "IA": "Intelligenza Artificiale machine learning automazione tecnologia digitale",
}

# ─── Prompt LLM ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Sei un assistente specializzato nel linguaggio parlamentare italiano. "
    "Data una query di ricerca, espandila con sinonimi, concetti correlati e "
    "varianti lessicali del contesto parlamentare. "
    "NON alterare il significato. Restituisci SOLO la query espansa, senza spiegazioni."
)

_USER_TEMPLATE = (
    'Query originale: "{query}"\n\n'
    "Espandi aggiungendo 5-10 termini parlamentari correlati separati da spazio."
)


# ─── QueryRewriter ─────────────────────────────────────────────────────────────

class QueryRewriter:
    """
    Preprocessa la query prima dell'embedding per migliorare il retrieval.

    Stadio 1 — expand_acronyms():
        Sostituisce acronimi noti con forma estesa + termini semanticamente correlati.
        Combina acronimi built-in con quelli custom definiti dall'utente nelle impostazioni.
        Costo: zero. Latenza: trascurabile.

    Stadio 2 — LLM expansion (opzionale):
        Per query brevi (≤ N parole), chiede a gpt-4o-mini di arricchire
        semanticamente la query espansa. Fallback silenzioso se l'API fallisce.

    IMPORTANTE: la query riscritta va SOLO all'embedding (dense channel).
    Il graph channel riceve sempre la query originale per preservare il
    matching lessicale sui termini esatti dell'utente.
    """

    def __init__(self, openai_client, config):
        self.client = openai_client
        self.config = config

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_custom_acronyms(self) -> Dict[str, str]:
        """Carica gli acronimi custom dell'utente dal file dedicato."""
        try:
            return self.config.load_custom_acronyms()
        except Exception:
            return {}

    def _get_rewriting_config(self) -> dict:
        """Legge la sezione query_rewriting dal config principale."""
        try:
            return self.config.load_config().get("query_rewriting", {})
        except Exception:
            return {}

    # ── Stadio 1: acronimi ─────────────────────────────────────────────────────

    def expand_acronyms(self, query: str) -> str:
        """
        Sostituisce le siglle note con la loro espansione semantica.

        Gli acronimi custom dell'utente hanno priorità su quelli built-in,
        consentendo override mirati (es. ridefinire "AI" in un contesto specifico).
        """
        all_acronyms = {**BUILT_IN_ACRONYMS, **self._get_custom_acronyms()}

        words = query.split()
        expanded_parts = []
        for word in words:
            # Rimuovi punteggiatura finale per il lookup, mantieni la parola originale
            clean = word.upper().rstrip(".,;:!?\"')")
            if clean in all_acronyms:
                expanded_parts.append(f"{word} {all_acronyms[clean]}")
            else:
                expanded_parts.append(word)

        return " ".join(expanded_parts)

    # ── Stadio 2: espansione LLM ───────────────────────────────────────────────

    def _llm_expand(self, query: str, model: str) -> str:
        """Chiama il modello LLM per arricchire semanticamente la query."""
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _USER_TEMPLATE.format(query=query)},
            ],
            temperature=0.1,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()

    # ── Entry point principale ─────────────────────────────────────────────────

    def rewrite(self, query: str) -> str:
        """
        Pipeline completa: acronimi + espansione LLM opzionale.

        Logica:
        - Se query_rewriting.enabled = false → restituisce query originale.
        - Stadio 1 (acronimi) → sempre eseguito se enabled.
        - Stadio 2 (LLM) → solo se len(query) <= max_query_words AND llm_expansion.enabled.
        - Fallback silenzioso su errori LLM → usa il risultato dello stadio 1.
        """
        rw_cfg = self._get_rewriting_config()

        if not rw_cfg.get("enabled", True):
            return query

        # Stadio 1 — sempre
        expanded = self.expand_acronyms(query)

        # Stadio 2 — condizionale
        llm_cfg = rw_cfg.get("llm_expansion", {})
        if llm_cfg.get("enabled", True):
            max_words = llm_cfg.get("max_query_words", 5)
            model = llm_cfg.get("model", "gpt-4o-mini")
            if len(query.split()) <= max_words:
                try:
                    result = self._llm_expand(expanded, model)
                    logger.debug(f"Query rewritten: '{query[:40]}' -> '{result[:80]}'")
                    return result
                except Exception as e:
                    logger.warning(f"LLM query expansion failed (fallback to acronym expansion): {e}")

        return expanded
