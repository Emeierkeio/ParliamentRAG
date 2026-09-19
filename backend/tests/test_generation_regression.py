"""Regression tests for the generation-verifiability refactor.

Offline-testable invariants of the 20-case regression plan
(docs/design/generation-verifiability.md): candidate extraction, assembler
citation preservation, duplicate-citation removal, attribution enforcement,
nested/rhetorical quote handling, translation placeholder shielding,
temporal position brief, Misto component attribution, analyst grounding.
Cases that need live LLM/Neo4j calls stay in the evaluation set.
"""
import pytest

from app.services.generation.quote_candidates import (
    extract_quote_candidates,
    _split_sentences,
)
from app.services.generation.integrator import NarrativeIntegrator
from app.services.generation.pipeline import GenerationPipeline
from app.services.generation.surgeon import CitationSurgeon
from app.services.generation.position_brief import PositionBriefBuilder
from app.services.generation.sectional import SectionalWriter
from app.services.generation.analyst import ClaimAnalyst
from app.services.translation import (
    shield_citation_targets,
    restore_citation_targets,
)


LONG_STANCE = (
    "Noi riteniamo che il salario minimo legale sia una misura indispensabile "
    "per tutelare i lavoratori più deboli del nostro Paese."
)


class TestQuoteCandidates:
    def test_candidates_are_exact_substrings(self):
        text = (
            f"{LONG_STANCE} Il Governo continua a ignorare il problema del "
            "lavoro povero nonostante gli impegni presi in Aula davanti a tutti."
        )
        candidates = extract_quote_candidates(text, query="salario minimo")
        assert candidates
        for c in candidates:
            assert c in text

    def test_leading_connective_rejected(self):
        text = (
            "Quindi non possiamo accettare questa proposta del Governo perché "
            "danneggia i lavoratori dipendenti e le famiglie italiane oggi."
        )
        assert extract_quote_candidates(text) == []

    def test_ellipsis_rejected(self):
        text = (
            "Noi sosteniamo con forza … la proposta di legge sul salario "
            "minimo per tutti i lavoratori del nostro Paese senza eccezioni."
        )
        candidates = extract_quote_candidates(text)
        assert all('…' not in c for c in candidates)

    def test_nested_quote_rejected(self):
        # TEST 06: the stance sentence sits inside an unclosed « block —
        # it is someone else's reported voice.
        text = (
            "Il collega ha dichiarato: «Noi riteniamo che il salario minimo "
            "legale sia una misura indispensabile per tutelare i lavoratori "
            "più deboli e vulnerabili del Paese» e io non sono d'accordo."
        )
        candidates = extract_quote_candidates(text, query="salario minimo")
        assert all("misura indispensabile" not in c for c in candidates)

    def test_procedural_opening_rejected(self):
        text = (
            "Presentiamo una mozione che impegna il Governo su questo tema "
            "davanti a tutta l'Aula della Camera dei Deputati oggi stesso."
        )
        assert extract_quote_candidates(text) == []

    def test_leading_vocative_stripped_not_rejected(self):
        # Transcripts open substantive stances with vocatives: the vocative
        # is cut, the remainder survives as an exact substring.
        text = (
            "Signor Presidente, onorevoli colleghi, come Fratelli d'Italia "
            "siamo estremi difensori del Servizio sanitario nazionale "
            "universale e riteniamo fondamentale difendere questo modello."
        )
        candidates = extract_quote_candidates(text, query="riforma sanitaria")
        assert candidates
        assert candidates[0].startswith("come Fratelli d'Italia")
        assert candidates[0] in text

    def test_length_band(self):
        candidates = extract_quote_candidates("Frase corta.", query="frase")
        assert candidates == []
        long_text = "Parola " * 200
        candidates = extract_quote_candidates(long_text)
        assert all(80 <= len(c) <= 350 for c in candidates)

    def test_query_ranking(self):
        # TEST 19: multiple valid candidates, query-relevant one first.
        text = (
            "La situazione economica europea resta complessa e difficile per "
            "tutti gli Stati membri dell'Unione in questa fase storica. "
            f"{LONG_STANCE}"
        )
        candidates = extract_quote_candidates(text, query="salario minimo lavoratori")
        assert candidates
        assert "salario minimo" in candidates[0]

    def test_no_valid_candidate_returns_empty(self):
        # TEST 20: nothing citable → empty list, caller falls back.
        assert extract_quote_candidates("") == []
        assert extract_quote_candidates("E quindi. Ma però. Che dire.") == []

    def test_sentence_split_keeps_guillemets_atomic(self):
        text = "Ha detto: «Prima frase. Seconda frase.» e ha concluso. Fine del discorso."
        sentences = _split_sentences(text)
        joined = " ".join(sentences)
        assert "«Prima frase. Seconda frase.»" in joined


def _make_integrator() -> NarrativeIntegrator:
    integ = NarrativeIntegrator()
    integ.mode = "assembler"
    return integ


def _sections_fixture():
    return [
        {
            "party": "GOVERNO",
            "content": "### GOVERNO\n\nIl Governo difende la misura. "
                       "**Meloni** afferma «testo uno» [CIT:leg19_a_chunk_1]. Posizione ferma.",
            "citations": [{"evidence_id": "leg19_a_chunk_1"}],
            "has_evidence": True,
        },
        {
            "party": "Fratelli d'Italia",
            "content": "### Fratelli d'Italia\n\nIl gruppo sostiene il decreto. "
                       "**Rossi** dichiara «testo due» [CIT:leg19_b_chunk_2]. Linea confermata.",
            "citations": [{"evidence_id": "leg19_b_chunk_2"}],
            "has_evidence": True,
        },
        {
            "party": "Partito Democratico - Italia Democratica e Progressista",
            "content": "### Partito Democratico\n\nIl gruppo critica il decreto. "
                       "**Bianchi** contesta «testo tre» [CIT:leg19_c_chunk_3]. Opposizione netta.",
            "citations": [{"evidence_id": "leg19_c_chunk_3"}],
            "has_evidence": True,
        },
        {
            "party": "Misto",
            "content": "## Misto\n\nNel corpus analizzato non risultano interventi rilevanti su questo tema.",
            "citations": [],
            "has_evidence": False,
        },
    ]


class TestAssemblerIntegration:
    def test_assembler_preserves_all_citations(self, monkeypatch):
        # TEST 13: no citation ID can be lost by the integrator.
        integ = _make_integrator()
        monkeypatch.setattr(
            integ, "_generate_introduction", lambda *a, **k: "Intro frase uno. Intro frase due."
        )
        result = integ.integrate_with_guard("query", _sections_fixture())
        text = result["text"]
        for cid in ("leg19_a_chunk_1", "leg19_b_chunk_2", "leg19_c_chunk_3"):
            assert f"[CIT:{cid}]" in text
        assert result["citation_verification"]["missing"] == []
        assert result["citation_verification"]["retried"] is False

    def test_assembler_structure(self, monkeypatch):
        integ = _make_integrator()
        monkeypatch.setattr(
            integ, "_generate_introduction", lambda *a, **k: "Intro."
        )
        text = integ.integrate_with_guard("query", _sections_fixture())["text"]
        assert "## Introduzione" in text
        assert "## Posizione del Governo" in text
        assert "## Posizioni della Maggioranza" in text
        assert "## Posizioni dell'Opposizione" in text
        assert "## Gruppo Misto" in text
        assert "Per Fratelli d'Italia," in text
        # Party headers from the sectional writer must not leak through
        assert "### Fratelli" not in text

    def test_party_without_evidence_states_absence(self, monkeypatch):
        # TEST 01: absence is declared, never invented.
        integ = _make_integrator()
        monkeypatch.setattr(
            integ, "_generate_introduction", lambda *a, **k: "Intro."
        )
        text = integ.integrate_with_guard("query", _sections_fixture())["text"]
        assert "non risultano interventi rilevanti" in text

    def test_fallback_introduction_is_deterministic(self):
        from datetime import date
        stats = {
            "debate_title": "DDL salario minimo",
            "intervention_count": 64,
            "speaker_count": 39,
            "first_date": date(2023, 7, 4),
            "last_date": date(2026, 7, 16),
        }
        intro = NarrativeIntegrator._fallback_introduction(stats)
        assert "DDL salario minimo" in intro
        assert "64" in intro and "39" in intro


class TestPipelineDeterministicGuards:
    def test_duplicate_citation_removed_from_wrong_party(self):
        # TEST 12: same CIT id twice is always an error; the copy in the
        # wrong party's paragraph goes away.
        evidence_map = {
            "leg19_x_chunk_1": {"party": "Azione - Popolari Europeisti Riformatori - Renew Europe"},
        }
        text = (
            "Per Azione - Popolari Europeisti Riformatori - Renew Europe, il gruppo propone. "
            "**Bonetti** dice «frase» [CIT:leg19_x_chunk_1]. Fine.\n\n"
            "Per Movimento 5 Stelle, il gruppo rilancia. "
            "**Conte** dice «frase» [CIT:leg19_x_chunk_1]. Fine."
        )
        cleaned = GenerationPipeline._dedupe_citation_occurrences(text, evidence_map)
        assert cleaned.count("[CIT:leg19_x_chunk_1]") == 1
        # The surviving occurrence is in the evidence's own party paragraph
        surviving_par = [p for p in cleaned.split("\n\n") if "[CIT:" in p][0]
        assert surviving_par.startswith("Per Azione")

    def test_bold_name_without_citation_is_anonymized(self):
        evidence_map = {
            "leg19_y_chunk_1": {"speaker_name": "Mario Rossi"},
        }
        text = (
            "**Rossi** sostiene la riforma senza mezzi termini. "
            "Il gruppo conferma [«la riforma è necessaria»](leg19_y_chunk_1)."
        )
        fixed, n = GenerationPipeline._enforce_bold_name_attribution(text, evidence_map)
        assert n == 1
        assert not fixed.startswith("**Rossi**")
        assert "Il gruppo sostiene la riforma" in fixed

    def test_bold_name_with_citation_is_kept(self):
        evidence_map = {
            "leg19_y_chunk_1": {"speaker_name": "Mario Rossi"},
        }
        text = "**Rossi** afferma [«la riforma è necessaria»](leg19_y_chunk_1)."
        fixed, n = GenerationPipeline._enforce_bold_name_attribution(text, evidence_map)
        assert n == 0
        assert "**Rossi**" in fixed

    def test_unknown_bold_text_untouched(self):
        evidence_map = {"leg19_y_chunk_1": {"speaker_name": "Mario Rossi"}}
        text = "**Il gruppo** ribadisce la posizione senza citazioni."
        fixed, n = GenerationPipeline._enforce_bold_name_attribution(text, evidence_map)
        assert n == 0
        assert fixed == text


class TestSurgeonInvariants:
    def test_nested_quote_detected(self):
        # TEST 06: reported speech copied with its markers, or extracted
        # from inside an unclosed quote block.
        assert CitationSurgeon._is_nested_quote(
            "«l'espansione è necessaria»", "ha detto Peskov: «l'espansione è necessaria» ieri"
        )
        assert CitationSurgeon._is_nested_quote(
            "l'espansione è necessaria", "ha detto Peskov: «l'espansione è necessaria» ieri"
        )
        assert not CitationSurgeon._is_nested_quote(
            "noi sosteniamo la misura", "In Aula: noi sosteniamo la misura, senza esitazioni."
        )

    def test_rhetorical_question_gets_answer(self):
        # TEST 07: a rhetorical question alone inverts the meaning.
        source = (
            "Possiamo permetterci di sospendere gli aiuti? No, le armi sono "
            "indispensabili per la difesa del Paese aggredito."
        )
        quote = "Possiamo permetterci di sospendere gli aiuti?"
        expanded = CitationSurgeon._expand_rhetorical_answer(quote, source)
        assert "No, le armi sono indispensabili" in expanded

    def test_verbatim_inline_citation_resolves_to_link(self):
        surgeon = CitationSurgeon()
        evidence_map = {
            "leg19_z_chunk_1": {
                "quote_text": LONG_STANCE,
                "quote_vetted": True,
                "speaker_name": "Anna Verdi",
                "party": "Movimento 5 Stelle",
                "date": "2025-03-10",
            }
        }
        text = f"**Verdi** afferma «{LONG_STANCE}» [CIT:leg19_z_chunk_1]."
        result = surgeon.insert_citations(text, evidence_map, query="salario minimo")
        assert "](leg19_z_chunk_1)" in result["text"]
        assert result["failed_count"] == 0
        assert result["citations"][0]["evidence_id"] == "leg19_z_chunk_1"

    def test_unknown_citation_id_reported_as_failed(self):
        surgeon = CitationSurgeon()
        result = surgeon.insert_citations(
            "**X** dice «frase» [CIT:leg19_missing_chunk_9].", {}, query=""
        )
        assert result["failed_count"] == 1
        assert result["failed_citations"][0]["reason"] == "not_found_in_evidence_map"


class TestTranslationShield:
    def test_roundtrip_preserves_ids(self):
        # TEST 14: citation IDs survive translation byte-identical.
        text = (
            "Il gruppo sostiene [«frase uno»](leg19_sed100_tit1.sub2.int3_chunk_1) "
            "e critica [«frase due»](leg19_sed200_tit4.sub5.int6_chunk_2)."
        )
        shielded, mapping = shield_citation_targets(text)
        assert "leg19_sed100" not in shielded
        assert "__CIT_1__" in shielded and "__CIT_2__" in shielded
        restored, ok = restore_citation_targets(shielded, mapping)
        assert ok
        assert restored == text

    def test_lost_placeholder_detected(self):
        text = "Testo [«a»](leg19_a_chunk_1) e [«b»](leg19_b_chunk_2)."
        shielded, mapping = shield_citation_targets(text)
        corrupted = shielded.replace("(__CIT_2__)", "(link)")
        _, ok = restore_citation_targets(corrupted, mapping)
        assert not ok

    def test_duplicated_placeholder_detected(self):
        text = "Testo [«a»](leg19_a_chunk_1)."
        shielded, mapping = shield_citation_targets(text)
        corrupted = shielded + " extra (__CIT_1__)"
        _, ok = restore_citation_targets(corrupted, mapping)
        assert not ok

    def test_no_links_no_placeholders(self):
        shielded, mapping = shield_citation_targets("Nessun link qui.")
        assert mapping == {}
        restored, ok = restore_citation_targets(shielded, mapping)
        assert ok and restored == "Nessun link qui."


PRO_TEXT = (
    "Siamo favorevoli al salario minimo, è un diritto dei lavoratori e serve "
    "una soglia di dignità di 9 euro per tutti."
)
AGAINST_TEXT = (
    "Siamo contrari al salario minimo per legge: la contrattazione collettiva "
    "è la strada, respingiamo questa proposta dannosa."
)


class TestPositionBriefTemporal:
    def _brief(self, evidence):
        return PositionBriefBuilder().build_brief(evidence, "Partito Test")

    def test_temporal_evolution_detected(self):
        # TEST 03: support in 2023, opposition in 2025 → evolution, no average.
        evidence = [
            {"speaker_name": "A", "date": "2023-05-01", "quote_text": PRO_TEXT},
            {"speaker_name": "B", "date": "2025-06-01", "quote_text": AGAINST_TEXT},
        ]
        brief = self._brief(evidence)
        assert "IN EVOLUZIONE" in brief
        assert "2023" in brief and "2025" in brief

    def test_conflicting_same_period(self):
        # TEST 18/02: opposing signals in the same window → conflicting.
        evidence = [
            {"speaker_name": "A", "date": "2024-05-01", "quote_text": PRO_TEXT},
            {"speaker_name": "B", "date": "2024-05-01", "quote_text": AGAINST_TEXT},
        ]
        brief = self._brief(evidence)
        assert "CONFLITTUALE" in brief

    def test_stable_direction(self):
        evidence = [
            {"speaker_name": "A", "date": "2024-05-01", "quote_text": AGAINST_TEXT},
            {"speaker_name": "B", "date": "2025-02-01", "quote_text": AGAINST_TEXT},
        ]
        brief = self._brief(evidence)
        assert "CONTRARIO" in brief
        assert "IN EVOLUZIONE" not in brief

    def test_brief_is_hypothesis_not_mandate(self):
        evidence = [
            {"speaker_name": "A", "date": "2024-05-01", "quote_text": PRO_TEXT},
        ]
        brief = self._brief(evidence)
        assert "IPOTESI DI POSIZIONE" in brief
        assert "VIETATO citare" not in brief


class TestSectionalHelpers:
    def test_misto_component_note(self):
        # TEST 09: Misto positions are attributed to the component.
        writer = SectionalWriter()
        evidence = [{
            "evidence_id": "leg19_m_chunk_1",
            "speaker_name": "Luca Neri",
            "party": "Misto",
            "misto_component": "+Europa",
            "date": "2025-01-01",
            "quote_text": PRO_TEXT,
            "citability_score": 0.8,
        }]
        context = writer._build_evidence_context(evidence, "salario minimo")
        assert "COMPONENTE DEL GRUPPO MISTO: +Europa" in context
        assert "MAI al gruppo Misto" in context

    def test_claims_block_filters_absent_and_other_parties(self):
        claims = [
            {"claim": "Sostiene X", "party": "Fratelli d'Italia",
             "evidence_status": "supported", "stance": "supportive",
             "temporal_scope": None},
            {"claim": "Nessuna evidenza", "party": "Fratelli d'Italia",
             "evidence_status": "absent", "stance": "unclear",
             "temporal_scope": None},
            {"claim": "Critica Y", "party": "Movimento 5 Stelle",
             "evidence_status": "partial", "stance": "critical",
             "temporal_scope": "2024"},
        ]
        block = SectionalWriter._build_claims_block(claims, "Fratelli d'Italia")
        assert "Sostiene X" in block
        assert "Nessuna evidenza" not in block
        assert "Critica Y" not in block
        assert "NON fatti" in block

    def test_single_citation_enforced(self):
        content = (
            "**Rossi** dice «frase A» [CIT:leg19_a_chunk_1]. "
            "**Bianchi** aggiunge «frase B» [CIT:leg19_b_chunk_2]."
        )
        result = SectionalWriter._enforce_single_citation(content)
        assert result.count("[CIT:") == 1
        assert "«frase B»" in result


class TestAnalystGrounding:
    def test_fabricated_evidence_ids_dropped_and_downgraded(self):
        claims = [{
            "claim_id": "c1",
            "claim": "Il partito sostiene X",
            "party": "Lega - Salvini Premier",
            "evidence_status": "supported",
            "evidence_ids": ["leg19_fake_chunk_1"],
            "stance": "supportive",
            "temporal_scope": None,
            "priority": "high",
        }]
        evidence = [{"evidence_id": "leg19_real_chunk_1"}]
        ClaimAnalyst._validate_evidence_ids(claims, evidence)
        assert claims[0]["evidence_ids"] == []
        assert claims[0]["evidence_status"] == "absent"

    def test_valid_ids_kept(self):
        claims = [{
            "claim_id": "c1",
            "claim": "Il partito sostiene X",
            "party": "Lega - Salvini Premier",
            "evidence_status": "partial",
            "evidence_ids": ["leg19_real_chunk_1", "leg19_fake_chunk_2"],
            "stance": "supportive",
            "temporal_scope": None,
            "priority": "high",
        }]
        evidence = [{"evidence_id": "leg19_real_chunk_1"}]
        ClaimAnalyst._validate_evidence_ids(claims, evidence)
        assert claims[0]["evidence_ids"] == ["leg19_real_chunk_1"]
        assert claims[0]["evidence_status"] == "partial"


class TestUnsupportedClaimRate:
    def test_rate_computation(self):
        from app.routers.evaluation import _compute_unsupported_claim_rate
        answer = (
            "Il gruppo sostiene la riforma [«testo citato»](leg19_a_chunk_1). "
            "Il partito critica la gestione del dossier. "
            "La discussione riguarda il salario minimo."
        )
        rate, unsupported, total = _compute_unsupported_claim_rate(answer)
        assert total == 2
        assert unsupported == 1
        assert rate == pytest.approx(0.5)

    def test_empty_answer(self):
        from app.routers.evaluation import _compute_unsupported_claim_rate
        assert _compute_unsupported_claim_rate("") == (0.0, 0, 0)
