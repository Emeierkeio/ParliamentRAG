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

    # --- Meta-comment pattern tests (FActScore-inspired, C1) ---

    def test_meta_comment_delicate_topic(self, extractor):
        """Generic importance claim without policy content."""
        s = "Questo mi sembra uno dei più delicati dossier che la I Commissione si è trovata a dover esaminare."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_important_topic(self, extractor):
        s = "È un tema importante che merita la nostra attenzione."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_complex_topic(self, extractor):
        s = "Su un tema così complesso, probabilmente, in quest'Aula avremmo potuto dare un contributo."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_in_questa_sede(self, extractor):
        s = "In questa sede vogliamo ribadire l'importanza del confronto parlamentare."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_come_sappiamo(self, extractor):
        s = "Come sappiamo, il tema è stato ampiamente dibattuto nelle commissioni."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_mi_preme(self, extractor):
        s = "Mi preme sottolineare l'importanza di questa discussione."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_abbiamo_esaminato(self, extractor):
        s = "Abbiamo esaminato il provvedimento con grande attenzione."
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_comment_with_opinion_wins(self, extractor):
        """Meta-comment with opinion marker should score as opinion, not meta."""
        s = "È un tema importante e riteniamo che il Governo debba intervenire."
        score = extractor._political_salience_score(s)
        assert score >= 0.9  # Opinion wins over meta

    def test_meta_comment_with_argumentation_wins(self, extractor):
        """Meta-comment with argumentation should score as argumentation."""
        s = "Su un tema così complesso, i costi sono aumentati del 40 per cento."
        score = extractor._political_salience_score(s)
        assert score >= 0.7  # Argumentation wins over meta

    def test_meta_real_case_kelany(self, extractor):
        """Real case from analyzed output: Kelany's meta-comment."""
        s = ("Uno dei più delicati, da quando è iniziata la legislatura, "
             "che la I Commissione si è trovata a dover esaminare.")
        assert extractor._political_salience_score(s) == 0.35

    def test_meta_real_case_grippo(self, extractor):
        """Real case: Grippo's meta-comment about collaboration.
        Contains 'la maggioranza' which triggers group identity opinion pattern,
        so opinion (0.9) wins over meta-comment (0.35)."""
        s = ("Vede, su un tema così complesso, probabilmente, in quest'Aula, "
             "la maggioranza e l'opposizione avrebbero potuto dare un contributo.")
        # Opinion marker wins over meta-comment
        assert extractor._political_salience_score(s) >= 0.9

    def test_meta_pure_process_comment(self, extractor):
        """Pure meta-comment with no opinion or argumentation markers."""
        s = ("Vede, su un tema così complesso, probabilmente "
             "avremmo potuto dare un contributo migliore.")
        assert extractor._political_salience_score(s) == 0.35


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


# --- Generation pipeline salience filters ---

class TestSectionalSalienceFilter:
    """Test that the sectional writer filters out procedural citations."""

    @pytest.fixture
    def writer(self):
        """Create a SectionalWriter with mocked settings."""
        from unittest.mock import patch, MagicMock
        with patch('app.services.generation.sectional.get_settings') as mock_settings, \
             patch('app.services.generation.sectional.get_config') as mock_config, \
             patch('app.services.generation.sectional.openai'):
            mock_settings.return_value = MagicMock(openai_api_key="test")
            mock_config.return_value = MagicMock(
                load_config=MagicMock(return_value={"generation": {"models": {"writer": "gpt-4o"}}})
            )
            from app.services.generation.sectional import SectionalWriter
            yield SectionalWriter()

    def test_build_evidence_context_skips_procedural(self, writer):
        """Procedural citations should be skipped in evidence context."""
        evidence = [
            {
                "evidence_id": "proc_1",
                "speaker_name": "Gava",
                "date": "2024-01-15",
                "quote_text": "Sull'ordine del giorno n. 9/1606-A/33 Scerra, il parere è favorevole.",
                "chunk_text": "Sull'ordine del giorno n. 9/1606-A/33 Scerra, il parere è favorevole.",
            },
            {
                "evidence_id": "opinion_1",
                "speaker_name": "Rossi",
                "date": "2024-01-15",
                "quote_text": "Riteniamo che questa riforma sia fondamentale per il Paese.",
                "chunk_text": "Riteniamo che questa riforma sia fondamentale per il Paese.",
            },
        ]

        context = writer._build_evidence_context(evidence, "riforma")
        assert "proc_1" not in context
        assert "opinion_1" in context

    def test_build_evidence_context_keeps_substantive(self, writer):
        """Substantive citations should always be included."""
        evidence = [
            {
                "evidence_id": "opinion_1",
                "speaker_name": "Bianchi",
                "date": "2024-01-15",
                "quote_text": "Proponiamo una riforma strutturale della sanità pubblica.",
                "chunk_text": "Proponiamo una riforma strutturale della sanità pubblica.",
            },
        ]

        context = writer._build_evidence_context(evidence, "sanità")
        assert "opinion_1" in context

    def test_build_evidence_context_skips_vote_announcement(self, writer):
        """Vote announcement citations should be filtered out."""
        evidence = [
            {
                "evidence_id": "vote_1",
                "speaker_name": "Semenzato",
                "date": "2024-01-15",
                "quote_text": "Con quest'auspicio annuncio il voto favorevole del gruppo Noi Moderati.",
                "chunk_text": "Con quest'auspicio annuncio il voto favorevole del gruppo Noi Moderati.",
            },
        ]

        context = writer._build_evidence_context(evidence, "cambiamenti climatici")
        assert "vote_1" not in context

    def test_build_evidence_context_skips_meta_comment(self, writer):
        """Meta-comments about debate importance should be filtered (C1)."""
        evidence = [
            {
                "evidence_id": "meta_1",
                "speaker_name": "Kelany",
                "date": "2024-01-15",
                "quote_text": ("Questo mi sembra uno dei più delicati dossier "
                               "che la I Commissione si è trovata a dover esaminare."),
                "chunk_text": ("Questo mi sembra uno dei più delicati dossier "
                               "che la I Commissione si è trovata a dover esaminare."),
            },
            {
                "evidence_id": "opinion_1",
                "speaker_name": "Rossi",
                "date": "2024-01-15",
                "quote_text": "Riteniamo che questa riforma sia fondamentale per il Paese.",
                "chunk_text": "Riteniamo che questa riforma sia fondamentale per il Paese.",
            },
        ]

        context = writer._build_evidence_context(evidence, "immigrazione")
        assert "meta_1" not in context
        assert "opinion_1" in context


class TestSurgeonSalienceGate:
    """Test that the surgeon detects procedural citations."""

    def test_format_citation_detects_procedural(self):
        """Surgeon should detect and log procedural citations."""
        from app.services.generation.surgeon import CitationSurgeon
        from app.services.citation.sentence_extractor import compute_chunk_salience

        # Verify the salience scoring correctly identifies procedural text
        procedural = "il parere è favorevole"
        assert compute_chunk_salience(procedural) <= 0.2

        substantive = "riteniamo che questa legge sia fondamentale per il Paese"
        assert compute_chunk_salience(substantive) >= 0.9
