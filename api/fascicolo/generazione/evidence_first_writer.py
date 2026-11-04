"""Sezioni scritte partendo dalla citazione.

Prima si fissa la citazione, poi il modello scrive solo il testo che la
introduce: così introduzione e citazione dicono la stessa cosa per
costruzione. La pipeline lo usa per sostituire le citazioni tolte.
"""
import re
import logging
from typing import List, Dict, Any

from .contesto import chat
from .impostazioni import MODELLI, NESSUNA_EVIDENZA

logger = logging.getLogger(__name__)


class EvidenceFirstWriter:
    """Scrive le sezioni dei gruppi attorno a citazioni già scelte (il modello scrive solo l'introduzione)."""

    INTRO_GENERATION_PROMPT = """Sei un redattore parlamentare italiano.

Ti fornisco una citazione ESATTA che dovrai introdurre. Il tuo compito è scrivere SOLO il testo introduttivo.

CITAZIONE DA INTRODURRE:
Oratore: {speaker_name}
Partito: {party}
Testo citazione: "{quote_text}"

TEMA DELLA DOMANDA: {query}

SCRIVI SOLO IL TESTO INTRODUTTIVO (1-2 frasi) che:
1. Nomina l'oratore in **grassetto**: **{speaker_surname}**
2. Riassume/anticipa il CONTENUTO della citazione
3. Termina con una costruzione che introduce la citazione (es. "affermando che", "sottolineando come")
4. Include un SOGGETTO grammaticale che collega alla citazione

FORMATO OBBLIGATORIO:
Il tuo output sarà concatenato con la citazione tra virgolette, quindi deve essere grammaticalmente corretto.

ESEMPI:
Se la citazione è "il sistema sanitario è in crisi per mancanza di fondi"
Scrivi: "**Rossi** denuncia le carenze del sistema sanitario, affermando che"

Se la citazione è "questa riforma porterà benefici a tutte le famiglie"
Scrivi: "**Bianchi** difende la riforma, sottolineando come"

REGOLE:
- NON includere la citazione nel tuo output
- NON aggiungere virgolette
- Termina con una costruzione introduttiva ("affermando che", "sottolineando come", "evidenziando che", etc.)
- Massimo 2 frasi

ORA SCRIVI SOLO IL TESTO INTRODUTTIVO:"""

    def __init__(self):
        self.model = MODELLI["writer"]
        self.no_evidence_message = NESSUNA_EVIDENZA

    def write_section_evidence_first(
        self,
        query: str,
        party: str,
        evidence: List[Dict[str, Any]],
        max_citations: int = 2
    ) -> Dict[str, Any]:
        """Scrive la sezione di un gruppo partendo dalle citazioni.

        Restituisce un dict con party, content (segnaposto [CIT:id]),
        citations, has_evidence e citation_bindings.
        """
        if not evidence:
            return {
                "party": party,
                "content": f"### {party}\n\n{self.no_evidence_message}",
                "citations": [],
                "has_evidence": False,
                "citation_bindings": []
            }

        selected_evidence = sorted(
            evidence,
            key=lambda e: e.get("similarity", 0),
            reverse=True
        )[:max_citations]

        content_parts = []
        citation_bindings = []
        citations = []

        for e in selected_evidence:
            evidence_id = e.get("evidence_id", "")
            speaker_name = e.get("speaker_name", "")
            speaker_surname = speaker_name.split()[-1] if speaker_name else "L'oratore"
            party_name = e.get("party", party)
            quote_text = e.get("quote_text") or e.get("chunk_text", "")
            quote_for_prompt = quote_text[:400] if len(quote_text) > 400 else quote_text

            intro_text = self._generate_introduction(
                query=query,
                speaker_name=speaker_name,
                speaker_surname=speaker_surname,
                party=party_name,
                quote_text=quote_for_prompt,
                evidence_id=evidence_id
            )

            full_segment = f"{intro_text} [CIT:{evidence_id}]."
            content_parts.append(full_segment)

            citation_bindings.append({
                "evidence_id": evidence_id,
                "intro_text": intro_text,
                "quote_preview": quote_text[:100],
                "binding_verified": True  # per costruzione
            })

            citations.append({
                "citation_id": evidence_id,
                "evidence_id": evidence_id,
                "speaker_name": speaker_name,
                "party": party_name,
                "date": str(e.get("date", "")),
            })

        content = f"### {party}\n\n" + " ".join(content_parts)

        return {
            "party": party,
            "content": content,
            "citations": citations,
            "has_evidence": True,
            "citation_bindings": citation_bindings
        }

    def _generate_introduction(
        self,
        query: str,
        speaker_name: str,
        speaker_surname: str,
        party: str,
        quote_text: str,
        evidence_id: str
    ) -> str:
        """Scrive l'introduzione da unire a [CIT:id]."""
        prompt = self.INTRO_GENERATION_PROMPT.format(
            speaker_name=speaker_name,
            speaker_surname=speaker_surname,
            party=party,
            quote_text=quote_text,
            query=query
        )

        try:
            intro = chat(self.model, [{"role": "user", "content": prompt}], massimo=150, temperature=0.2).strip()

            # toglie segnaposto e virgolette (dritte e tipografiche) che il
            # modello può aver aggiunto nonostante le regole del prompt
            intro = re.sub(r'\[CIT:[^\]]*\]', '', intro)
            intro = intro.replace('«', '').replace('»', '')
            intro = intro.replace('"', '').replace('“', '').replace('”', '')

            # se l'introduzione non finisce con un connettivo, almeno si toglie
            # il punto finale perché la citazione possa seguire
            if not any(intro.rstrip().endswith(ending) for ending in [
                "che", "come", "quanto", "quando", "dove",
                "quale", "quali", "perché"
            ]):
                intro = intro.rstrip('.')

            logger.debug(f"Generated intro for {evidence_id}: {intro[:50]}...")

            return intro

        except Exception as e:
            logger.error(f"Introduction generation failed for {evidence_id}: {e}")
            return f"**{speaker_surname}** interviene sul tema, affermando che"
