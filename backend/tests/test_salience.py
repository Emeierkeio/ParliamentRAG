"""Tests for the political salience scoring system."""
import pytest
from app.services.citation.sentence_extractor import (
    SentenceExtractor,
    compute_chunk_salience,
    extract_best_sentences,
)


@pytest.fixture
def extractor():
    return SentenceExtractor(max_sentences=2)


# --- _political_salience_score tests ---

class TestPoliticalSalienceScore:

    def test_opinion_single_hit(self, extractor):
        s = "Riteniamo che questa misura sia del tutto inadeguata."
        assert extractor._political_salience_score(s) == 0.9

    def test_opinion_double_hit(self, extractor):
        s = "Riteniamo che questo provvedimento è inaccettabile per il Paese."
        assert extractor._political_salience_score(s) == 1.0

    def test_procedural_only(self, extractor):
        s = "Signor Presidente, ha facoltà di parlare l'onorevole Rossi."
        assert extractor._political_salience_score(s) == 0.2

    def test_procedural_with_opinion_wins(self, extractor):
        """If both procedural and opinion markers exist, opinion wins."""
        s = "Signor Presidente, riteniamo che questa legge sia sbagliata."
        score = extractor._political_salience_score(s)
        assert score >= 0.9

    def test_argumentation_single(self, extractor):
        s = "Rispetto a quanto previsto, i costi sono aumentati notevolmente."
        assert extractor._political_salience_score(s) == 0.7

    def test_argumentation_with_legal_and_numbers(self, extractor):
        """Two argumentation hits: legal ref + monetary figure."""
        s = "L'articolo 5 del decreto prevede tagli per 2 miliardi di euro."
        assert extractor._political_salience_score(s) == 0.8

    def test_argumentation_double(self, extractor):
        s = "Rispetto a quanto previsto dall'articolo 12, i fondi sono insufficienti."
        assert extractor._political_salience_score(s) == 0.8

    def test_neutral(self, extractor):
        s = "Il tema della scuola pubblica è molto discusso in questi giorni."
        assert extractor._political_salience_score(s) == 0.5

    def test_group_identity(self, extractor):
        s = "Il nostro gruppo ha sempre difeso i diritti dei lavoratori."
        assert extractor._political_salience_score(s) == 0.9

    def test_vote_declaration(self, extractor):
        s = "Voteremo contro questo provvedimento."
        assert extractor._political_salience_score(s) == 0.9

    def test_session_opening(self, extractor):
        s = "Dichiaro aperta la seduta."
        assert extractor._political_salience_score(s) == 0.2

    def test_thanks(self, extractor):
        s = "Ringrazio il Presidente per la parola concessa."
        # "ringrazio il presidente" is procedural
        assert extractor._political_salience_score(s) == 0.2

    def test_value_judgment(self, extractor):
        s = "È fondamentale garantire risorse adeguate alla sanità pubblica."
        assert extractor._political_salience_score(s) == 0.9

    def test_policy_direction(self, extractor):
        s = "Questa riforma rappresenta un passo indietro per il Paese."
        assert extractor._political_salience_score(s) == 0.9

    def test_parere_favorevole(self, extractor):
        s = "Sull'ordine del giorno n. 9/1606-A/33 Scerra, il parere è favorevole."
        assert extractor._political_salience_score(s) == 0.2

    def test_parere_contrario(self, extractor):
        s = "Il parere è contrario sull'emendamento presentato."
        assert extractor._political_salience_score(s) == 0.2

    def test_emendamento_approvato(self, extractor):
        s = "L'emendamento è approvato."
        assert extractor._political_salience_score(s) == 0.2

    def test_governo_esprime_parere(self, extractor):
        s = "Il Governo esprime parere favorevole sull'ordine del giorno."
        assert extractor._political_salience_score(s) == 0.2

    def test_relatore_invita_ritiro(self, extractor):
        s = "Il relatore invita al ritiro dell'emendamento 1.5."
        assert extractor._political_salience_score(s) == 0.2

    def test_annuncio_voto_favorevole(self, extractor):
        s = "Con quest'auspicio annuncio il voto favorevole del gruppo Noi Moderati."
        assert extractor._political_salience_score(s) == 0.2

    def test_dichiaro_voto(self, extractor):
        s = "Dichiaro il voto favorevole del mio gruppo su questa mozione."
        assert extractor._political_salience_score(s) == 0.2

    def test_real_case_gava(self, extractor):
        """Real case from COP28 debate output."""
        s = "Sull'ordine del giorno n. 9/1606-A/33 Scerra, il parere è favorevole."
        assert extractor._political_salience_score(s) == 0.2

    def test_real_case_cirielli_is_substantive(self, extractor):
        """Real case: Cirielli expressing a political stance."""
        s = ("Sinceramente la narrazione di un Governo negazionista "
             "dei cambiamenti climatici è priva di fondamento.")
        score = extractor._political_salience_score(s)
        # Should NOT be procedural — it's a political judgment
        assert score >= 0.5

    def test_empty_string(self, extractor):
        assert extractor._political_salience_score("") == 0.5


# --- compute_salience (chunk-level) tests ---

class TestComputeSalience:

    def test_chunk_with_mixed_content_returns_max(self, extractor):
        text = (
            "La seduta è aperta alle ore 10. "
            "Riteniamo che il Governo debba intervenire con urgenza "
            "per risolvere la crisi del settore automobilistico."
        )
        score = extractor.compute_salience(text)
        # Should return max of sentences => 0.9 (opinion hit)
        assert score >= 0.9

    def test_chunk_all_procedural(self, extractor):
        text = (
            "La seduta è aperta. "
            "Ha facoltà di parlare l'onorevole Bianchi. "
            "Avverto che è iscritto a parlare l'onorevole Verdi."
        )
        score = extractor.compute_salience(text)
        assert score <= 0.2

    def test_chunk_empty(self, extractor):
        assert extractor.compute_salience("") == 0.0

    def test_convenience_function(self):
        text = "Proponiamo di modificare l'articolo 3 della legge n. 42."
        score = compute_chunk_salience(text)
        assert score >= 0.7


# --- Sentence extraction with salience integration ---

class TestExtractionWithSalience:

    def test_prefers_opinion_over_procedural(self):
        """When both procedural and opinion sentences match the query,
        the extractor should prefer the opinion sentence."""
        text = (
            "Signor Presidente, onorevoli colleghi, intervengo sul tema della sanità. "
            "Riteniamo che il taglio di 3 miliardi alla sanità pubblica "
            "sia una scelta inaccettabile che colpisce i cittadini più fragili."
        )
        query = "sanità pubblica"
        result = extract_best_sentences(text, query, max_sentences=1, max_chars=500)
        # Should prefer the opinion sentence, not the procedural opening
        assert "riteniamo" in result.lower() or "inaccettabile" in result.lower()

    def test_neutral_still_extracted_when_only_option(self):
        """When there's only neutral content, it should still be extracted."""
        text = "Il tema dell'istruzione è stato affrontato in commissione."
        query = "istruzione"
        result = extract_best_sentences(text, query, max_sentences=1, max_chars=500)
        assert "istruzione" in result.lower()

    def test_argumentation_preferred_over_neutral(self):
        """Argumentation with data should rank higher than neutral text."""
        text = (
            "Il problema dell'energia è noto a tutti. "
            "Rispetto al 2019, i costi energetici sono aumentati del 40 per cento "
            "secondo i dati dell'ISTAT."
        )
        query = "costi energetici"
        result = extract_best_sentences(text, query, max_sentences=1, max_chars=500)
        # Should prefer the sentence with numbers/comparison
        assert "40 per cento" in result or "rispetto" in result.lower()


# --- Merger integration (unit-level) ---

class TestMergerSalienceIntegration:

    def test_score_components_include_salience(self):
        """The merger should include salience in score_components."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()

        dense_results = [{
            "evidence_id": "chunk_1",
            "speaker_id": "sp1",
            "party": "Fratelli d'Italia",
            "similarity": 0.8,
            "chunk_text": "Riteniamo che questa legge sia fondamentale per il Paese.",
            "quote_text": "Riteniamo che questa legge sia fondamentale per il Paese.",
        }]

        merged = merger.merge(
            dense_results=dense_results,
            graph_results=[],
            authority_scores=None,
            top_k=10
        )

        assert len(merged) == 1
        assert "salience" in merged[0]["score_components"]
        # Opinion text should get high salience
        assert merged[0]["score_components"]["salience"] >= 0.9

    def test_procedural_gets_lower_final_score(self):
        """Procedural chunks should get lower final_score than opinion chunks,
        all else being equal."""
        from app.services.retrieval.merger import ChannelMerger

        merger = ChannelMerger()

        dense_results = [
            {
                "evidence_id": "opinion_chunk",
                "speaker_id": "sp1",
                "party": "PD",
                "similarity": 0.7,
                "chunk_text": "Proponiamo una riforma strutturale della sanità pubblica.",
                "quote_text": "Proponiamo una riforma strutturale della sanità pubblica.",
            },
            {
                "evidence_id": "procedural_chunk",
                "speaker_id": "sp2",
                "party": "Lega",
                "similarity": 0.7,
                "chunk_text": "Ha facoltà di parlare l'onorevole Bianchi.",
                "quote_text": "Ha facoltà di parlare l'onorevole Bianchi.",
            },
        ]

        merged = merger.merge(
            dense_results=dense_results,
            graph_results=[],
            authority_scores=None,
            top_k=10
        )

        opinion = next(r for r in merged if r["evidence_id"] == "opinion_chunk")
        procedural = next(r for r in merged if r["evidence_id"] == "procedural_chunk")

        assert opinion["final_score"] > procedural["final_score"]
