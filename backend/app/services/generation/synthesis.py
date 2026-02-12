"""
Stage 3.5: Convergence-Divergence Analyzer

Identifies cross-party convergences, key fault lines, and
cross-coalition positions from the integrated report.

Grounded in:
- "Positioning Political Texts with Large Language Models" (arXiv 2023):
  LLMs can identify political position similarity via "asking and averaging"
- Convergence Coefficient (Schofield, PMC 2013): formal framework for
  measuring centripetal (convergence) vs centrifugal (divergence) forces
"""
import logging
from typing import Dict, Any, Optional

import openai

from ...config import get_config, get_settings

logger = logging.getLogger(__name__)


class ConvergenceDivergenceAnalyzer:
    """
    Analyzes the integrated report to identify convergences,
    divergences, and cross-coalition positions.

    Appends a "## Analisi Trasversale" section to the report.
    """

    SYSTEM_PROMPT = """Sei un analista politico parlamentare esperto.
Dato un report sulle posizioni dei partiti su un tema specifico, devi
identificare i pattern trasversali alle coalizioni.

STRUTTURA OUTPUT (usa ESATTAMENTE questi sottotitoli):

### Convergenze
Temi su cui maggioranza e opposizione concordano sostanzialmente.
Per ogni convergenza, cita i partiti coinvolti e riferisciti alle loro
posizioni nel report. Se non ci sono convergenze evidenti, scrivi
"Non emergono convergenze significative dal corpus analizzato."

### Linee di Frattura
I punti di disaccordo fondamentale tra le coalizioni.
Per ogni frattura, identifica chiaramente la posizione della maggioranza
e quella dell'opposizione. Se il disaccordo non è netto, sfumalo.

### Posizioni Trasversali
Partiti che si distinguono dalla propria coalizione o che esprimono
posizioni atipiche rispetto al proprio schieramento.
Se non ci sono posizioni trasversali, scrivi
"Non emergono posizioni trasversali significative."

REGOLE:
1. Basa l'analisi SOLO sulle citazioni e posizioni presenti nel testo
2. NON inventare convergenze o divergenze non evidenti
3. Sii CONCISO: max 2-3 frasi per ogni punto
4. Usa i nomi dei partiti completi
5. Se il report contiene marcatori [CIT:...], puoi riferirli ma NON copiarli
6. NON aggiungere nuove citazioni [CIT:...]
7. Mantieni un tono analitico e neutrale, mai editoriale"""

    def __init__(self):
        self.config = get_config()
        self.settings = get_settings()
        self.client = openai.OpenAI(api_key=self.settings.openai_api_key)

        gen_config = self.config.load_config().get("generation", {})
        self.model = gen_config.get("models", {}).get("integrator", "gpt-4o")

    def analyze(
        self,
        integrated_text: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Analyze the integrated report for convergences and divergences.

        Args:
            integrated_text: The full integrated report text (post-Stage 3)
            query: Original user query for context

        Returns:
            Dictionary with:
            - synthesis_text: The "## Analisi Trasversale" section
            - success: Whether analysis completed successfully
        """
        user_prompt = f"""Domanda originale: {query}

Report da analizzare:
{integrated_text}

Identifica convergenze, linee di frattura e posizioni trasversali
basandoti ESCLUSIVAMENTE sulle posizioni espresse nel report sopra.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )

            synthesis_text = response.choices[0].message.content

            return {
                "synthesis_text": synthesis_text,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Convergence-divergence analysis failed: {e}")
            return {
                "synthesis_text": "",
                "success": False,
                "error": str(e),
            }
