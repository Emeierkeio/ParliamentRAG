"""Regia della pipeline di generazione in 4 fasi.

La fase 1 (analista) scompone la domanda in claim, la 2 (scrittore delle
sezioni) scrive una sezione per partito, la 3 (integratore) le unisce in un
racconto coerente, la 4 (chirurgo) risolve le citazioni testuali. Il registro
delle citazioni, il validatore di coerenza e la guardia dell'integratore
seguono le citazioni fase per fase e controllano che siano tutte risolte.
"""
import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .analyst import ClaimAnalyst
from .sectional import SectionalWriter, single_word_stem
from .evidence_first_writer import EvidenceFirstWriter
from .debate_relevance import ON_TOPIC, OTHER, debate_rank
from .integrator import NarrativeIntegrator, lead_body, party_lead, readable_party_leads
from .surgeon import CitationSurgeon
from .citation_registry import CitationRegistry
from .coherence_validator import CoherenceValidator
from . import gruppi
from .contesto import in_parallelo
from .impostazioni import COERENZA_MINIMA, ID_BRANO, METODO_COERENZA
from .verbatim import is_verbatim

logger = logging.getLogger(__name__)



_QUOTE_LINK_RE = re.compile(r'\[«[^»]*»\]\((' + ID_BRANO + r')\)')


def _mask_quote_links(text: str) -> Tuple[str, List[str]]:
    """Sostituisce ogni [«…»](id) con un segno dell'area privata Unicode, che nessuna regex di pulizia tocca."""
    links: List[str] = []

    def keep(m: re.Match) -> str:
        links.append(m.group(0))
        return f"\ue000{len(links) - 1}\ue001"

    return _QUOTE_LINK_RE.sub(keep, text), links


def _unmask_quote_links(text: str, links: List[str]) -> str:
    return re.sub(r"\ue000(\d+)\ue001", lambda m: links[int(m.group(1))], text)


def _check_verbatim(text: str, evidence_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Confronta ogni link di citazione del testo finale con il suo tratto di fonte."""
    checked, failed = 0, []
    for m in _QUOTE_LINK_RE.finditer(text):
        quote = m.group(0)[2:m.group(0).index("»]")]
        eid = m.group(1)
        evidence = evidence_map.get(eid) or {}
        source = evidence.get("quote_text") or evidence.get("chunk_text") or ""
        checked += 1
        if not is_verbatim(quote, source):
            failed.append({"evidence_id": eid, "quote": quote[:120]})
    return {"checked": checked, "failed": failed}


def topic_evidence(evidence_list: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """I passaggi che parlano del tema, per il periodo e i conteggi della
    risposta: non quelli detti nei dibattiti su altri atti e, per un tema di
    una parola, solo quelli che la nominano. Senza questo filtro ogni
    fascicolo copriva tutta la legislatura («autonomia differenziata»,
    «tartufo», 28/10/2026). Se non ne resta nessuno, contano tutti come prima."""
    stem = single_word_stem(query)
    kept = [
        e for e in evidence_list
        if e.get("debate_relevance") != OTHER
        and (not stem or stem in (e.get("chunk_text") or e.get("quote_text") or "").lower())
    ]
    return kept or evidence_list

class GenerationPipeline:
    """Regia delle 4 fasi di generazione, con l'integrità delle citazioni."""

    def __init__(self):

        self.analyst = ClaimAnalyst()
        self.sectional_writer = SectionalWriter()
        # sostituisce le citazioni rimosse d'autorità: introduzioni coerenti per costruzione
        self.evidence_first_writer = EvidenceFirstWriter()
        self.integrator = NarrativeIntegrator()
        self.surgeon = CitationSurgeon()
        self.coherence_validator = CoherenceValidator(
            min_coherence_score=COERENZA_MINIMA,
            method=METODO_COERENZA,
        )

    def generate(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]],
        stream_callback: Optional[callable] = None,
        query_context: Optional[str] = None,
        parties: Optional[List[str]] = None,
        scope: Optional[Tuple[Tuple[str, int], ...]] = None,
    ) -> Dict[str, Any]:
        """Esegue tutta la pipeline di generazione, con l'integrità delle citazioni.

        stream_callback, se c'è, riceve gli eventi di avanzamento di ogni fase.
        parties sono i gruppi che hanno una sezione (di norma tutti i gruppi
        dei rami caricati); una richiesta su un ramo passa i suoi gruppi.
        scope (i rami della richiesta) decide se il testo parla di deputati,
        senatori o parlamentari.
        Restituisce il testo finale con citazioni, metadati e resoconto di integrità.
        """
        from .integrator import reset_chambers, set_chambers

        token = set_chambers(tuple(c for c, _ in scope) if scope else None)
        try:
            return self._generate(query, evidence_list, stream_callback, query_context, parties)
        finally:
            reset_chambers(token)

    def _generate(
        self,
        query: str,
        evidence_list: List[Dict[str, Any]],
        stream_callback: Optional[callable],
        query_context: Optional[str],
        parties: Optional[List[str]],
    ) -> Dict[str, Any]:
        start_time = datetime.now()
        pipeline_metadata = {
            "stages": {},
            "start_time": start_time.isoformat(),
            "citation_integrity": {}
        }

        registry = CitationRegistry()
        registry.register_evidence(evidence_list)

        # fase 1: analista
        if stream_callback:
            stream_callback({
                "type": "progress",
                "stage": 1,
                "message": "Analyzing query and evidence..."
            })

        _stage_t0 = time.perf_counter()
        # analista, integratore e validatore di coerenza usano il client OpenAI
        # sincrono: girano in un thread, così mentre aspettano il ciclo degli
        # eventi continua a servire le altre pipeline e /api/health
        claims_result = self.analyst.analyze(query, evidence_list)
        claims = claims_result.get("claims", [])

        pipeline_metadata["stages"]["analyst"] = {
            "claims_count": len(claims),
            "query_type": claims_result.get("query_type"),
            "requires_government": claims_result.get("requires_government_view", False),
            "duration_ms": round((time.perf_counter() - _stage_t0) * 1000, 1),
            "model": self.analyst.model,
        }

        logger.info(f"Stage 1 complete: {len(claims)} claims identified")

        if parties is None:
            parties = gruppi.nomi()
        evidence_by_party = self._group_evidence_by_party(evidence_list, parties)
        government_evidence = self._get_government_evidence(evidence_list)
        evidence_map = {
            e.get("evidence_id"): e for e in evidence_list if e.get("evidence_id")
        }

        # fase 2: scrittore delle sezioni
        if stream_callback:
            stream_callback({
                "type": "progress",
                "stage": 2,
                "message": "Writing party sections..."
            })

        sections = []
        _stage_t0 = time.perf_counter()
        for section in self.sectional_writer.write_sections(
            query=query,
            claims=claims,
            evidence_by_party=evidence_by_party,
            government_evidence=government_evidence,
            query_context=query_context,
            parties=parties,
            # ci sono dibattiti sul tema: i passaggi su altri atti non reggono
            # mai una sezione (card 201)
            exclude_other_acts=any(e.get("debate_relevance") == ON_TOPIC for e in evidence_list),
        ):
            sections.append(section)

            content = section.get("content", "")
            party = section.get("party", "")
            citation_ids = re.findall(r'\[CIT:([^\]]+)\]', content)
            for cit_id in citation_ids:
                # introduzione = testo dalla fine della frase precedente al marcatore
                pattern = rf'([^.!?]*)\[CIT:{re.escape(cit_id)}\]'
                match = re.search(pattern, content)
                intro = match.group(1).strip() if match else ""
                registry.bind_citation(cit_id, party, intro)

            if stream_callback:
                stream_callback({
                    "type": "section",
                    "party": party,
                    "has_evidence": section.get("has_evidence", False),
                })

        pipeline_metadata["stages"]["sectional"] = {
            "sections_count": len(sections),
            "parties_with_evidence": sum(1 for s in sections if s.get("has_evidence")),
            "citations_bound": len(registry.get_expected_citations()),
            "duration_ms": round((time.perf_counter() - _stage_t0) * 1000, 1),
            "model": self.sectional_writer.model,
        }

        logger.info(f"Stage 2 complete: {len(sections)} sections written, "
                    f"{len(registry.get_expected_citations())} citations bound")

        # fase 3: integratore, con la guardia sulle citazioni
        if stream_callback:
            stream_callback({
                "type": "progress",
                "stage": 3,
                "message": "Integrating narrative..."
            })

        topic_statistics = self._compute_topic_statistics(topic_evidence(evidence_list, query), query)

        _stage_t0 = time.perf_counter()
        integrated = self.integrator.integrate_with_guard(
            query, sections, registry, topic_statistics=topic_statistics
        )

        pipeline_metadata["stages"]["integrator"] = {
            "integration_success": not integrated.get("integration_failed", False),
            "citation_verification": integrated.get("citation_verification", {}),
            "citations_repaired": integrated.get("citations_repaired", 0),
            "duration_ms": round((time.perf_counter() - _stage_t0) * 1000, 1),
            "model": self.integrator.model,
        }

        logger.info(f"Stage 3 complete: Narrative integrated, "
                    f"{integrated.get('citations_repaired', 0)} citations repaired")

        # controllo dei nomi dei partiti: a volte il modello dell'integratore
        # perde l'attacco «Per [Nome Partito],» o usa una sigla. Se succede si
        # inserisce come paragrafo di riserva la sezione originale, così la
        # metrica non penalizza a torto
        integrated_text_after_guard = integrated.get("text", "")
        integrated_text_after_guard, injected_parties = self._inject_missing_party_paragraphs(
            integrated_text_after_guard, sections
        )
        if injected_parties:
            pipeline_metadata["stages"]["party_injection"] = {"injected_parties": injected_parties}

        # l'integratore può copiare la frase di un partito nel paragrafo di un
        # altro (sezioni senza citazioni «arricchite»): lo stesso [CIT:id] due
        # volte è sempre un errore, resta solo nel paragrafo giusto
        integrated_text_after_guard = self._dedupe_citation_occurrences(
            integrated_text_after_guard, evidence_map
        )
        integrated["text"] = integrated_text_after_guard

        balance_info = self._check_coalition_balance(integrated.get("text", ""))
        pipeline_metadata["stages"]["balance"] = balance_info
        if balance_info.get("balance_warning"):
            logger.warning(
                f"Coalition imbalance detected: "
                f"majority={balance_info['majority_words']} words, "
                f"opposition={balance_info['opposition_words']} words, "
                f"ratio={balance_info['ratio']:.1f}:1"
            )

        # controllo di coerenza prima del chirurgo. Prima si versano in
        # evidence_map le frasi scelte dal selettore: il validatore deve
        # confrontare l'introduzione con la frase scelta, non con l'embedding
        # dell'intero chunk (~1200 caratteri su più temi) → punteggio 0.15-0.20
        # e rimozione sistematica (osservato il 23/07/2026)
        for section in sections:
            for pick_eid, pick_quote in (section.get("picked_quotes") or {}).items():
                if pick_eid in evidence_map and pick_quote:
                    evidence_map[pick_eid]["quote_text"] = pick_quote
                    evidence_map[pick_eid]["quote_vetted"] = True
        coherence_report = self.coherence_validator.validate_all_citations(
            integrated.get("text", ""),
            evidence_map
        )

        pipeline_metadata["citation_integrity"]["coherence"] = {
            "all_coherent": coherence_report["all_coherent"],
            "coherent_count": coherence_report["coherent_citations"],
            "incoherent_count": coherence_report["incoherent_citations"],
            "average_score": coherence_report["average_score"],
        }

        integrated_text = integrated.get("text", "")

        if not coherence_report["all_coherent"]:
            incoherent = self.coherence_validator.get_incoherent_citations(coherence_report)
            logger.warning(f"Coherence issues: {len(incoherent)} incoherent citations")
            for ic in incoherent[:3]:
                logger.warning(f"  - {ic.get('evidence_id')}: {ic.get('warning')}")

            # si rimuovono d'autorità le citazioni del tutto fuori tema
            # (probabilmente fonte sbagliata). La taratura di 0.35 non è documentata
            HARD_REMOVE_THRESHOLD = 0.35
            # le frasi scelte dal selettore non si rimuovono: lo scrittore
            # costruisce l'introduzione attorno alla frase obbligata, quindi la
            # coerenza è garantita per costruzione. La somiglianza fra embedding
            # di due testi brevi giudica peggio del patto selettore+scrittore:
            # sulle domande di nicchia scendeva sotto 0.35 per quasi tutte le
            # citazioni buone e scatenava sostituzioni a catena (e sezioni senza
            # frase dove le evidenze sono poche, 24/07/2026)
            hard_mismatches = [
                ic for ic in incoherent
                if ic.get("score", 1.0) < HARD_REMOVE_THRESHOLD
                and not evidence_map.get(ic.get("evidence_id", ""), {}).get("quote_vetted")
            ]
            n_exempt = sum(
                1 for ic in incoherent
                if ic.get("score", 1.0) < HARD_REMOVE_THRESHOLD
                and evidence_map.get(ic.get("evidence_id", ""), {}).get("quote_vetted")
            )
            if n_exempt:
                logger.info(
                    f"Coherence: {n_exempt} low-score citations kept (picker-vetted)"
                )
            if hard_mismatches:
                logger.warning(f"Hard-removing {len(hard_mismatches)} citations with score < {HARD_REMOVE_THRESHOLD}")
                for ic in hard_mismatches:
                    eid = ic.get("evidence_id", "")
                    # via «frase» e [CIT:id] insieme, così non restano «» nudi nel testo;
                    # tra » e [CIT: può esserci punteggiatura o spazio (il modello mette . o ,)
                    integrated_text = re.sub(
                        rf'«[^»]+»[.,;:!?\s]*\[CIT:{re.escape(eid)}\]',
                        '',
                        integrated_text
                    )
                    # e via anche il [CIT:id] nudo, se non aveva una frase davanti
                    integrated_text = re.sub(rf'\[CIT:{re.escape(eid)}\]', '', integrated_text)

                # prima di arrendersi si sostituisce: per ogni citazione rimossa
                # si prova l'evidenza successiva del partito con EvidenceFirstWriter
                # (introduzione coerente per costruzione, il suo scopo originale).
                # Solo se non c'è alternativa si ripiega su un paragrafo senza citazione
                if hard_mismatches:
                    removed_ids = {ic.get("evidence_id", "") for ic in hard_mismatches}
                    used_ids = set(re.findall(r'\[CIT:([^\]]+)\]', integrated_text))

                    rewrite_tasks = {}
                    for ic in hard_mismatches:
                        eid = ic.get("evidence_id", "")
                        removed_ev = evidence_map.get(eid, {})
                        party = removed_ev.get("party", "")
                        is_gov = (
                            removed_ev.get("coalition") == "governo"
                            or removed_ev.get("speaker_role") == "GovernmentMember"
                        )

                        # le citazioni del Governo si sostituiscono dentro la
                        # sezione «Posizione del Governo»
                        if is_gov:
                            gov_alternatives = [
                                e for e in government_evidence
                                if e.get("evidence_id") not in removed_ids
                                and e.get("evidence_id") not in used_ids
                            ]
                            if gov_alternatives:
                                # anche le sostituzioni passano dal selettore
                                # (23/07/2026: il chunk_3 di Meloni apriva con la
                                # frase sull'Ucraina, EvidenceFirstWriter l'ha
                                # citata saltando ogni criterio di autosufficienza)
                                pick_eid, pick_quote = self.sectional_writer._pick_quote(
                                    query, gov_alternatives, query_context=query_context
                                )
                                if not pick_eid:
                                    logger.info(
                                        f"No citable GOVERNO substitute (picker) for {eid}"
                                    )
                                    continue
                                gov_alternatives = [
                                    {**e, "quote_text": pick_quote}
                                    for e in gov_alternatives
                                    if e.get("evidence_id") == pick_eid
                                ]
                                if pick_eid in evidence_map:
                                    evidence_map[pick_eid]["quote_text"] = pick_quote
                                    evidence_map[pick_eid]["quote_vetted"] = True
                                section = self.evidence_first_writer.write_section_evidence_first(
                                    query=query, party="GOVERNO",
                                    evidence=gov_alternatives, max_citations=1,
                                )
                                new_body = re.sub(r'^###[^\n]*\n+', '', section.get("content", "")).strip()
                                new_ids = re.findall(r'\[CIT:([^\]]+)\]', new_body)
                                if new_body and new_ids:
                                    replaced = re.sub(
                                        r'(## Posizione del Governo\s*\n+).*?(?=\n\n##|\Z)',
                                        lambda m: m.group(1) + new_body,
                                        integrated_text, count=1, flags=re.DOTALL,
                                    )
                                    if replaced != integrated_text:
                                        integrated_text = replaced
                                        used_ids.update(new_ids)
                                        logger.info(
                                            f"Substituted hard-removed GOVERNO citation "
                                            f"{eid} with {new_ids[0]}"
                                        )
                                        continue
                            logger.info(f"No GOVERNO substitute available for {eid}")
                            continue

                        if not party or party in rewrite_tasks:
                            continue
                        # solo se al partito non resta nessun [CIT:] nel testo
                        remaining = re.findall(r'\[CIT:[^\]]+\]', integrated_text)
                        party_eids = {e.get("evidence_id") for e in evidence_by_party.get(party, [])}
                        has_other_citations = any(
                            r in party_eids for r in remaining
                        )
                        if has_other_citations:
                            logger.info(f"Skipping rewrite for '{party}': still has other citations")
                            continue
                        party_evidence = evidence_by_party.get(party, [])

                        # si prova con l'evidenza successiva del partito
                        alternatives = [
                            e for e in party_evidence
                            if e.get("evidence_id") not in removed_ids
                            and e.get("evidence_id") not in used_ids
                            # anche il sostituto viene da una voce autorevole
                            and e.get("authoritative", True)
                        ]
                        if alternatives:
                            pick_eid, pick_quote = self.sectional_writer._pick_quote(
                                query, alternatives, query_context=query_context
                            )
                            if not pick_eid:
                                logger.info(
                                    f"No citable substitute (picker) for '{party}'"
                                )
                                if party_evidence:
                                    rewrite_tasks[party] = party_evidence
                                continue
                            alternatives = [
                                {**e, "quote_text": pick_quote}
                                for e in alternatives
                                if e.get("evidence_id") == pick_eid
                            ]
                            if pick_eid in evidence_map:
                                evidence_map[pick_eid]["quote_text"] = pick_quote
                                evidence_map[pick_eid]["quote_vetted"] = True
                            section = self.evidence_first_writer.write_section_evidence_first(
                                query=query, party=party,
                                evidence=alternatives, max_citations=1,
                            )
                            new_body = re.sub(r'^###[^\n]*\n+', '', section.get("content", "")).strip()
                            new_ids = re.findall(r'\[CIT:([^\]]+)\]', new_body)
                            if new_body and new_ids:
                                before = integrated_text
                                integrated_text = self._replace_party_paragraph(
                                    integrated_text, party, new_body
                                )
                                if integrated_text != before:
                                    used_ids.update(new_ids)
                                    logger.info(
                                        f"Substituted hard-removed citation for '{party}': "
                                        f"{eid} -> {new_ids[0]}"
                                    )
                                    continue

                        # nessuna alternativa: paragrafo senza citazione
                        if party_evidence:
                            rewrite_tasks[party] = party_evidence

                    if rewrite_tasks:
                        logger.info(f"Rewriting {len(rewrite_tasks)} citation-free paragraphs: {list(rewrite_tasks)}")
                        rewrite_results = in_parallelo(*[
                            lambda party=party, ev=ev: self.sectional_writer.write_section_without_citation(
                                query=query,
                                party=party,
                                evidence=ev,
                                claims=claims,
                            )
                            for party, ev in rewrite_tasks.items()
                        ])
                        failed_rewrites: Dict[str, str] = {}
                        for party, new_body in zip(rewrite_tasks.keys(), rewrite_results):
                            if new_body:
                                before = integrated_text
                                integrated_text = self._replace_party_paragraph(
                                    integrated_text, party, new_body
                                )
                                if integrated_text == before:
                                    # _replace_party_paragraph non ha trovato il paragrafo:
                                    # va inserito di riserva nel blocco di coalizione
                                    failed_rewrites[party] = new_body
                        if failed_rewrites:
                            integrated_text = self._inject_rewritten_paragraphs(
                                integrated_text, failed_rewrites
                            )

        # il modello dell'integratore può scrivere due volte lo stesso partito
        # (osservato il 23/07/2026: Fratelli d'Italia doppio, uno con ’ e uno con '),
        # e gli inserimenti di riserva possono aggiungere un secondo paragrafo
        # quando gli apostrofi diversi nascondevano l'originale. Un partito, un
        # paragrafo, sempre
        integrated_text = self._dedupe_party_paragraphs(integrated_text)

        for detail in coherence_report.get("details", []):
            eid = detail.get("evidence_id")
            score = detail.get("score", 0)
            registry.set_coherence_score(eid, score)

        # fase 4: chirurgo delle citazioni
        if stream_callback:
            stream_callback({
                "type": "progress",
                "stage": 4,
                "message": "Inserting citations..."
            })

        _stage_t0 = time.perf_counter()
        final_result = self.surgeon.insert_citations(
            text=integrated_text,
            evidence_map=evidence_map,
            query=query
        )

        for cit in final_result.get("citations", []):
            registry.mark_resolved(cit.get("evidence_id"), success=True)

        for cit in final_result.get("failed_citations", []):
            registry.mark_resolved(
                cit.get("evidence_id"),
                success=False,
                error=cit.get("reason")
            )

        pipeline_metadata["stages"]["surgeon"] = {
            "citations_inserted": final_result.get("total_citations", 0),
            "citations_failed": final_result.get("failed_count", 0),
            "duration_ms": round((time.perf_counter() - _stage_t0) * 1000, 1),
        }

        logger.info(
            f"Stage 4 complete: {final_result.get('total_citations', 0)} citations inserted"
        )

        final_text = final_result.get("text", "")

        # rete di sicurezza: le sostituzioni dopo la coerenza possono lasciare
        # code orfane dello stesso link, «…»](id) senza apertura subito dopo il
        # link completo (osservato il 24/07/2026, Misto). Ogni ](id) ripetuto è
        # un residuo da togliere
        final_text = self._strip_residual_citation_fragments(final_text)
        # "Ninety-one interventions" → "91 interventions" (solo introduzione):
        # il prompt da solo non vince la convenzione di stile inglese
        final_text = self._spelled_stats_to_digits(final_text)
        final_result["text"] = final_text

        # ID di citazione nel testo ma non in evidence_map possono essere chunk
        # validi dei dati che il modello ha preso dal contesto più ampio. Passano
        # al servizio (api/fascicolo/servizio.py), che li verifica sui dati e li
        # aggiunge alla barra laterale invece di toglierli qui
        valid_evidence_ids = set(evidence_map.keys())
        all_text_ids = set(
            m[1] for m in re.findall(
                r'\[([^\]]+)\]\((' + ID_BRANO + r')\)', final_text
            )
        )
        extra_citation_ids = list(all_text_ids - valid_evidence_ids)
        if extra_citation_ids:
            logger.info(
                f"Found {len(extra_citation_ids)} citation IDs in text not in "
                f"evidence_map — passing to caller for DB verification: "
                f"{extra_citation_ids[:5]}"
            )

        # a volte il modello dell'integratore scrive direttamente i link markdown
        # [«frase»](evidence_id) invece dei segnaposto [CIT:id]. Saltano il
        # chirurgo e mancano dall'elenco delle citazioni: si recuperano, perché
        # il sito possa legare i clic ai metadati
        tracked_ids = {
            c.get("evidence_id") for c in final_result.get("citations", [])
        }
        untracked_links = re.findall(
            r'\[([^\]]+)\]\((' + ID_BRANO + r')\)', final_text
        )
        for display_text, eid in untracked_links:
            if eid not in tracked_ids and eid in evidence_map:
                evidence = evidence_map[eid]
                # il quote_text testuale dell'evidenza, non il testo mostrato, che
                # la formattazione del chirurgo ha cambiato (parentesi tolte,
                # parole sospese, minuscole)
                raw_quote = evidence.get("quote_text", "") or evidence.get("chunk_text", "")

                final_result.get("citations", []).append({
                    "evidence_id": eid,
                    "quote_text": raw_quote,
                    "speaker_name": evidence.get("speaker_name"),
                    "party": evidence.get("party"),
                    "date": str(evidence.get("date", "")),
                    "span_start": evidence.get("span_start", 0),
                    "span_end": evidence.get("span_end", 0),
                })
                tracked_ids.add(eid)
                registry.mark_resolved(eid, success=True)
                logger.info(
                    f"Recovered untracked citation: {eid} "
                    f"(quote: '{raw_quote[:60]}...')"
                )

        if len(tracked_ids) > final_result.get("total_citations", 0):
            recovered = len(tracked_ids) - final_result.get("total_citations", 0)
            logger.info(f"Recovered {recovered} untracked citations from final text")

        # le pulizie di punteggiatura qui sotto riparano il racconto attorno alle
        # frasi tolte. Intanto i link di citazione restano coperti, così una
        # frase tiene gli spazi esatti dell'intervento (es. "Paese . Per")
        final_text, masked_links = _mask_quote_links(final_text)

        # via le «» nude, fuori dai link markdown: compaiono quando una citazione
        # rimossa lascia la frase orfana (es. il modello dell'integratore sposta
        # [CIT:id] dopo un punto, staccandolo dalle «»)
        bare_citations = re.findall(r'(?<!\[)«[^»]+»', final_text)
        if bare_citations:
            logger.warning(
                f"Found {len(bare_citations)} bare citations without markdown links: "
                f"{[c[:50] for c in bare_citations[:3]]}"
            )
            final_text = re.sub(r'(?<!\[)«[^»]+»', '', final_text)

        # via i resti di verbo dopo una frase tolta (nuda o rimossa d'autorità).
        # Gira sempre: la rimozione per coerenza qui sopra toglie «frase»[CIT:id]
        # ma lascia attribuzioni come "**Lupi** afferma: .", e siccome dopo non
        # restano «» nude il blocco bare_citations non scatta mai.
        #
        # Quattro forme, in quest'ordine:
        #
        # 1. "afferma: ."  → "."  (due punti rimasti dopo la frase tolta nelle sezioni)
        final_text = re.sub(r':\s*\.', '.', final_text)
        # 2. "afferma che ." → "."  (congiunzione sospesa dopo il [CIT:id] tolto)
        final_text = re.sub(r'\s+(?:che|come|di)\s+\.', '.', final_text)
        # 3. "afferma ."  → "afferma."  (spazio prima del punto dopo la frase nuda tolta)
        final_text = re.sub(r' \.', '.', final_text)
        # 4. "**nome** afferma."  → ""  (attribuzione da sola, senza contenuto).
        #    Dopo i passi 1-3 tutto finisce qui: nome in grassetto, un verbo e il
        #    punto. Si può togliere: un verbo seguito subito dal punto, senza
        #    oggetto, qui non è mai una frase con senso
        final_text = re.sub(r'\*\*[^*\n]+\*\*\s+\w+\.', '', final_text)
        final_text = _unmask_quote_links(final_text, masked_links)

        # attribuzione: il nome in grassetto di un deputato può stare solo in una
        # frase con la sua citazione. Il prompt dello scrittore lo dice e la
        # fase delle sezioni rende anonimo, ma il modello dell'integratore può
        # ancora spostare nomi in frasi senza citazione
        final_text, attribution_fixes = self._enforce_bold_name_attribution(
            final_text, evidence_map
        )
        if attribution_fixes:
            pipeline_metadata["stages"]["attribution_enforcement"] = {
                "names_anonymized": attribution_fixes,
            }

        # ultimo ritocco della forma: più sotto nessuno cerca «Per {party},»
        final_text = readable_party_leads(final_text)

        remaining_placeholders = re.findall(r'\[CIT:([^\]]+)\]', final_text)
        if remaining_placeholders:
            logger.error(f"Unresolved citation placeholders: {remaining_placeholders}")
            for cit_id in remaining_placeholders:
                final_text = final_text.replace(
                    f"[CIT:{cit_id}]",
                    "[Citazione non risolta]"
                )
                registry.mark_resolved(cit_id, success=False, error="unresolved_placeholder")

        # ultimo controllo prima del lettore: ogni citazione deve essere un tratto
        # continuo della sua fonte, secondo la regola testuale
        verbatim_report = _check_verbatim(final_text, evidence_map)
        pipeline_metadata["citation_integrity"]["verbatim"] = verbatim_report
        for failure in verbatim_report["failed"]:
            logger.error(f"Quotation not verbatim in its source: {failure}")

        # togliere i link a ID non verificabili tocca al servizio
        final_result["text"] = final_text

        unsupported_claims = self.surgeon.extract_unsupported_claims(final_text)
        integrity_report = registry.get_final_report()

        pipeline_metadata["citation_integrity"]["final"] = integrity_report
        pipeline_metadata["citation_integrity"]["unsupported_claims"] = unsupported_claims

        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        pipeline_metadata["end_time"] = end_time.isoformat()
        pipeline_metadata["duration_ms"] = duration_ms

        return {
            "text": final_result.get("text", ""),
            "citations": final_result.get("citations", []),
            "failed_citations": final_result.get("failed_citations", []),
            "extra_citation_ids": extra_citation_ids,
            "claims": claims,
            "sections": [
                {"party": s["party"], "has_evidence": s.get("has_evidence", False)}
                for s in sections
            ],
            "metadata": pipeline_metadata,
            "topic_statistics": topic_statistics,
            "citation_integrity": {
                "is_complete": integrity_report["is_complete"],
                "success_rate": integrity_report["success_rate"],
                "coherence_verified": coherence_report["all_coherent"],
                "unsupported_claims_count": len(unsupported_claims),
                "unresolved_placeholders": remaining_placeholders,
            }
        }

    def _compute_topic_statistics(
        self,
        evidence_list: List[Dict[str, Any]],
        query: str = "",
    ) -> Dict[str, Any]:
        """Le statistiche vere del tema, dalle evidenze recuperate.

        Restituisce i conteggi (per il prompt dell'integratore) e gli elenchi
        di dettaglio (per i numeri cliccabili dell'introduzione sul sito).
        """
        if not evidence_list:
            return {
                "intervention_count": 0,
                "speaker_count": 0,
                "first_date": None,
                "last_date": None,
                "debate_title": None,
                "speakers_detail": [],
                "interventions_detail": [],
                "sessions_detail": [],
            }

        unique_speeches = set(
            e.get("speech_id") for e in evidence_list if e.get("speech_id")
        )
        unique_speakers = set(
            e.get("speaker_id") for e in evidence_list if e.get("speaker_id")
        )
        dates = [e.get("date") for e in evidence_list if e.get("date")]

        most_common_title = _main_debate_title(evidence_list, query)

        session_numbers = [
            e.get("session_number") for e in evidence_list
            if e.get("session_number")
        ]

        speaker_interventions: Dict[str, Dict[str, Any]] = {}
        for e in evidence_list:
            sid = e.get("speaker_id")
            if not sid:
                continue
            if sid not in speaker_interventions:
                speaker_interventions[sid] = {
                    "speaker_id": sid,
                    "speaker_name": e.get("speaker_name", ""),
                    "party": e.get("party", ""),
                    "coalition": e.get("coalition", ""),
                    "speech_ids": set(),
                }
            speech_id = e.get("speech_id")
            if speech_id:
                speaker_interventions[sid]["speech_ids"].add(speech_id)

        speakers_detail = []
        for info in speaker_interventions.values():
            speakers_detail.append({
                "speaker_id": info["speaker_id"],
                "speaker_name": info["speaker_name"],
                "party": info["party"],
                "coalition": info["coalition"],
                "intervention_count": len(info["speech_ids"]),
            })
        speakers_detail.sort(key=lambda x: x["intervention_count"], reverse=True)

        seen_speeches: Dict[str, Dict[str, Any]] = {}
        for e in evidence_list:
            speech_id = e.get("speech_id")
            if not speech_id or speech_id in seen_speeches:
                continue
            seen_speeches[speech_id] = {
                "speech_id": speech_id,
                # il fascicolo conta interventi e oratori per ramo da questo campo
                "chamber": e.get("chamber") or "camera",
                # pagina ufficiale dell'intervento (Senato); None per la Camera
                "url": e.get("url"),
                "speaker_id": e.get("speaker_id", ""),
                "speaker_name": e.get("speaker_name", ""),
                "party": e.get("party", ""),
                "coalition": e.get("coalition", ""),
                "date": str(e.get("date", "")),
                "debate_title": e.get("debate_title", ""),
                "session_number": e.get("session_number", 0),
            }
        interventions_detail = sorted(
            seen_speeches.values(),
            key=lambda x: x["date"],
            reverse=True,
        )

        # sedute: una voce per seduta. I numeri si ripetono tra i rami (la 463
        # del Senato non è la 463 della Camera), quindi la chiave è l'id della seduta
        seen_sessions: Dict[str, Dict[str, Any]] = {}
        for e in evidence_list:
            sn = e.get("session_number")
            key = e.get("doc_id") or str(sn)
            if not sn or key in seen_sessions:
                continue
            seen_sessions[key] = {
                "session_number": sn,
                "session_id": e.get("doc_id", ""),
                "chamber": e.get("chamber") or "camera",
                # pagina della seduta su senato.it: il link dell'intervento senza ancora
                "url": (e.get("url") or "").split("&part=", 1)[0] or None,
                "date": str(e.get("date", "")),
                "debate_title": e.get("debate_title", ""),
            }
        sessions_detail = sorted(
            seen_sessions.values(),
            key=lambda x: (x["chamber"], x["session_number"]),
        )

        # per ramo, per le risposte che mettono insieme Camera e Senato
        by_chamber: Dict[str, Dict[str, set]] = {}
        for e in evidence_list:
            chamber = e.get("chamber") or "camera"
            slot = by_chamber.setdefault(chamber, {"speeches": set(), "speakers": set()})
            if e.get("speech_id"):
                slot["speeches"].add(e["speech_id"])
            if e.get("speaker_id"):
                slot["speakers"].add(e["speaker_id"])

        return {
            "by_chamber": {
                c: {"intervention_count": len(v["speeches"]), "speaker_count": len(v["speakers"])}
                for c, v in by_chamber.items()
            },
            "intervention_count": len(unique_speeches),
            "speaker_count": len(unique_speakers),
            "first_date": min(dates) if dates else None,
            "last_date": max(dates) if dates else None,
            "debate_title": most_common_title,
            "session_numbers": list(set(session_numbers)),
            "speakers_detail": speakers_detail,
            "interventions_detail": interventions_detail,
            "sessions_detail": sessions_detail,
        }

    def _replace_party_paragraph(self, text: str, party: str, new_body: str) -> str:
        """Sostituisce il corpo del paragrafo di un partito nel testo integrato.

        I paragrafi dei partiti seguono la forma obbligata dell'integratore:
            "Per [Nome completo del partito], [corpo]"
        e finiscono prima del paragrafo successivo ("Per ") o di un titolo ("##").

        Si sostituisce solo il corpo; l'attacco «Per [Partito], » resta, così
        il paragrafo mantiene la sua struttura.

        Se l'integratore ha aperto in un altro modo (es. «Il {party}
        critica...» invece di «Per {party}, ...») si cerca in modo più largo.
        """
        # apostrofi: il modello dell'integratore trasforma ' in ’, e così
        # "Fratelli d'Italia" (impostazioni) non trova mai "Fratelli d’Italia" (testo).
        # Nel pattern ogni apostrofo vale per entrambi; il confronto largo
        # normalizza i due lati
        party_escaped = re.escape(party).replace(r"'", "['’]").replace("’", "['’]")
        # ricerca stretta sull'attacco canonico «Per {party},»
        pattern = rf'(Per {party_escaped},\s+).*?(?=\n\nPer |\n\n##|\Z)'
        new_text, n = re.subn(pattern, lambda m: m.group(1) + lead_body(new_body), text, flags=re.DOTALL)
        if n > 0:
            logger.info(f"Rewrote citation-free paragraph for '{party}'")
            return new_text

        # ricerca larga: l'integratore può aver aperto con «Il {party} ...» o simili.
        # Si divide sulle righe vuote, si cerca il paragrafo la cui prima frase
        # contiene il nome del partito e lo si sostituisce tutto
        party_norm = party.replace("’", "'")
        parts = text.split('\n\n')
        for i, part in enumerate(parts):
            stripped = part.lstrip()
            if stripped.startswith('##'):
                continue
            first_sentence = stripped.split('.')[0].replace("’", "'")
            if party_norm in first_sentence:
                parts[i] = party_lead(party, new_body)
                logger.info(f"Rewrote citation-free paragraph for '{party}' (loose match)")
                return '\n\n'.join(parts)

        logger.warning(f"Could not locate paragraph for '{party}' in integrated text — skipping rewrite")
        return text

    @staticmethod
    def _dedupe_party_paragraphs(text: str) -> str:
        """Un solo paragrafo per partito nel testo integrato.

        I doppioni nascono da ripetizioni del modello o da inserimenti di
        riserva che non hanno visto l'originale per via degli apostrofi. Resta
        il paragrafo con citazioni ([CIT:, un link o «»); a parità, il primo.
        Le chiavi dei partiti hanno gli apostrofi normalizzati.
        """
        parts = text.split('\n\n')
        # indice dei paragrafi «Per {party},» per chiave di partito normalizzata
        party_of_part: Dict[int, str] = {}
        by_party: Dict[str, list] = {}
        for i, part in enumerate(parts):
            m = re.match(r'\s*Per ([^,]{3,90}),', part)
            if not m:
                continue
            key = m.group(1).replace("’", "'").strip().lower()
            party_of_part[i] = key
            by_party.setdefault(key, []).append(i)

        to_drop: set = set()
        for key, idxs in by_party.items():
            if len(idxs) < 2:
                continue
            def has_cit(i: int) -> bool:
                return '[CIT:' in parts[i] or '](' in parts[i] or '«' in parts[i]
            keeper = next((i for i in idxs if has_cit(i)), idxs[0])
            for i in idxs:
                if i != keeper:
                    to_drop.add(i)
            logger.warning(
                f"Deduped duplicate party paragraph(s) for {key!r}: "
                f"kept #{keeper}, dropped {sorted(to_drop & set(idxs))}"
            )

        if not to_drop:
            return text
        return '\n\n'.join(p for i, p in enumerate(parts) if i not in to_drop)

    # numeri inglesi in lettere (1-99): a inizio frase il modello scrive
    # "Ninety-one interventions" per convenzione di stile anche quando gli si
    # chiedono le cifre, e il sito rende cliccabili i numeri solo con \d+.
    # Conversione fissa, solo nell'introduzione
    _EN_UNITS = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
        "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    }
    _EN_TENS = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    }

    @classmethod
    def _spelled_stats_to_digits(cls, text: str) -> str:
        """Porta in cifre i numeri inglesi in lettere davanti a un nome di statistica.

        Tocca solo l'introduzione (la prima sezione ##).
        """
        tens = "|".join(cls._EN_TENS)
        units = "|".join(cls._EN_UNITS)
        nouns = r"(interventions?|deput(?:y|ies)|parliamentarians?|speeches|sessions?|sittings?)"
        pattern = re.compile(
            rf"\b((?:{tens})(?:[-\s](?:{units}))?|(?:{units}))\s+{nouns}",
            re.IGNORECASE,
        )

        def to_digits(m: re.Match) -> str:
            word = m.group(1).lower().replace("-", " ")
            parts = word.split()
            value = 0
            for p in parts:
                value += cls._EN_TENS.get(p, cls._EN_UNITS.get(p, 0))
            if value == 0:
                return m.group(0)
            return f"{value} {m.group(2)}"

        # solo l'introduzione (dal primo ## al secondo): le citazioni testuali
        # nelle sezioni dei partiti non si toccano mai
        first = re.search(r"^##\s", text, re.M)
        if not first:
            return text
        second = re.search(r"^##\s", text[first.end():], re.M)
        end = first.end() + second.start() if second else len(text)
        intro = text[:end]
        converted = pattern.sub(to_digits, intro)
        if converted != intro:
            logger.info("[INTRO] Spelled-out stat numbers converted to digits")
        return converted + text[end:]

    @staticmethod
    def _enforce_bold_name_attribution(
        text: str,
        evidence_map: Dict[str, Any],
    ) -> tuple:
        """Rende anonimi i nomi in grassetto nelle frasi senza la loro citazione.

        Un **Nome** in grassetto dice «sono parole sue»: senza un link di
        citazione nella stessa frase l'attribuzione non si può verificare, e il
        nome diventa un generico rimando al gruppo. Si toccano solo i nomi degli
        oratori delle evidenze, il resto del grassetto no. Gli ID dei link
        contengono punti, quindi i confini delle frasi si calcolano su una copia
        con ogni link coperto.

        Restituisce (testo, magari modificato; numero di nomi resi anonimi).
        """
        names = set()
        for e in evidence_map.values():
            full = (e.get("speaker_name") or "").strip()
            if full:
                names.add(full)
                names.add(full.split()[-1])
        if not names:
            return text, 0

        link_re = re.compile(r'\[«[^\]]*»\]\([^)\s]+\)')
        masked_chars = list(text)
        for m in link_re.finditer(text):
            for i in range(m.start(), m.end()):
                masked_chars[i] = '\x01'
        masked = ''.join(masked_chars)

        replacements = []
        for m in re.finditer(r'\*\*([^*\n]+)\*\*', text):
            if m.group(1).strip() not in names:
                continue
            start = max(masked.rfind(ch, 0, m.start()) for ch in '.!?\n') + 1
            ends = [
                idx for idx in (masked.find(ch, m.end()) for ch in '.!?\n')
                if idx != -1
            ]
            end = min(ends) if ends else len(masked)
            sentence = masked[start:end]
            if '\x01' in sentence or '[CIT:' in sentence or '«' in sentence:
                continue
            replacements.append((m.start(), m.end(), m.group(1).strip()))

        for a, b, name in reversed(replacements):
            replacement = 'Il gruppo' if a == 0 or text[a - 1] in '.!?\n' else 'il gruppo'
            text = text[:a] + replacement + text[b:]
            logger.info(f"Attribution enforcement: anonymized bold name {name!r}")

        return text, len(replacements)

    @staticmethod
    def _strip_residual_citation_fragments(text: str) -> str:
        """Toglie i residui e i doppioni dello stesso link di citazione.

        Dopo il chirurgo ogni citazione è un link [«frase»](chunk_id) e ogni
        chunk_id compare una volta sola. Le sostituzioni dopo la coerenza
        possono lasciare code orfane («…»](id) senza apertura) attaccate al
        link completo. Resta la prima occorrenza completa; ogni altro ](id) si
        toglie, risalendo a sinistra fino all'apertura del frammento (« o
        confine di frase).
        """
        link_re = re.compile(r'\[«[^»]{1,600}»\]\((' + ID_BRANO + r')\)')
        first_span: Dict[str, tuple] = {}
        for m in link_re.finditer(text):
            first_span.setdefault(m.group(1), (m.start(), m.end()))

        tail_re = re.compile(r'»?\]\((' + ID_BRANO + r')\)')
        removals = []
        for m in tail_re.finditer(text):
            eid = m.group(1)
            kept = first_span.get(eid)
            if kept and kept[0] <= m.start() < kept[1]:
                continue  # è il link che resta
            if not kept:
                continue  # unica occorrenza in forma inattesa: si lascia
            start = m.start()
            idx_open = text.rfind('«', 0, start)
            idx_sent = max(text.rfind(ch, 0, start) for ch in '.!?\n')
            if idx_open > idx_sent:
                left = idx_open
                if left > 0 and text[left - 1] == '[':
                    left -= 1
            else:
                left = idx_sent + 1
            end = m.end()
            if end < len(text) and text[end] in '.,;':
                end += 1
            removals.append((left, end))

        if not removals:
            return text
        for a, b in sorted(removals, reverse=True):
            logger.warning(
                f"Stripped residual citation fragment: {text[a:b][:90]!r}"
            )
            text = text[:a] + text[b:]
        return re.sub(r' {2,}', ' ', text)

    @staticmethod
    def _dedupe_citation_occurrences(text: str, evidence_map: Dict[str, Any]) -> str:
        """Toglie le occorrenze ripetute dello stesso [CIT:id] in paragrafi diversi.

        A volte l'integratore «arricchisce» i paragrafi senza citazioni
        copiando frase e CIT di un altro partito (osservato il 23/07/2026: una
        frase di Bonetti, Azione, attribuita al M5S con una cornice opposta).
        Lo stesso CIT due volte è sempre un errore: resta l'occorrenza nel
        paragrafo del partito dell'evidenza (in mancanza, la prima) e altrove
        si toglie tutta la frase.
        """
        ids = re.findall(r'\[CIT:([^\]]+)\]', text)
        dup_ids = {i for i in ids if ids.count(i) > 1}
        if not dup_ids:
            return text

        def para_key(p: str) -> Optional[str]:
            m = re.match(r"\s*Per ([^,]{3,90}),", p)
            return m.group(1).replace("’", "'").strip().lower() if m else None

        parts = text.split('\n\n')
        for eid in dup_ids:
            ev = evidence_map.get(eid, {})
            ev_party = (
                ev.get("current_party")
                if ev.get("party_changed") and ev.get("current_party")
                else ev.get("party", "")
            ) or ""
            key = ev_party.replace("’", "'").strip().lower()
            occ = [i for i, p in enumerate(parts) if f'[CIT:{eid}]' in p]
            if len(occ) < 2:
                continue
            keeper = next((i for i in occ if para_key(parts[i]) == key), occ[0])
            for i in occ:
                if i == keeper:
                    continue
                cleaned = re.sub(
                    r'[^.!?\n]*«[^»]*»\s*\[CIT:' + re.escape(eid) + r'\][^.!?\n]*[.!?]?',
                    '',
                    parts[i],
                )
                # riserva: CIT senza «» accanto (forma inattesa)
                cleaned = cleaned.replace(f'[CIT:{eid}]', '')
                parts[i] = re.sub(r'  +', ' ', cleaned).strip()
                logger.warning(
                    f"Removed misattributed duplicate citation {eid} "
                    f"(evidence party={ev_party!r}) from paragraph "
                    f"{para_key(parts[i]) or '<no header>'!r}"
                )
        return '\n\n'.join(p for p in parts if p.strip())

    def _inject_rewritten_paragraphs(
        self,
        text: str,
        rewritten: Dict[str, str],
    ) -> str:
        """Inserisce i paragrafi riscritti che _replace_party_paragraph non ha saputo collocare.

        Ogni corpo diventa un paragrafo nuovo «Per {party}, {body}». Quelli
        della maggioranza vanno in fondo al blocco della maggioranza; quelli di
        opposizione e Misto in fondo al testo, con il titolo del blocco se manca
        (come in _inject_missing_party_paragraphs).
        """
        coalitions = gruppi.coalizioni()
        MAGGIORANZA = coalitions.get("maggioranza", [])
        MISTO = coalitions.get("misto", [])

        magg_injections: list = []
        opp_injections: list = []
        misto_injections: list = []

        for party, body in rewritten.items():
            para = party_lead(party, body)
            if party in MAGGIORANZA:
                magg_injections.append(para)
            elif party in MISTO:
                # il Misto ha un blocco suo: non sta né con la maggioranza né con l'opposizione
                misto_injections.append(para)
            else:
                opp_injections.append(para)
            logger.info(f"Fallback injection: appending rewritten paragraph for '{party}'")

        if magg_injections:
            magg_header = "## Posizioni della Maggioranza"
            inject_block = "\n\n".join(magg_injections)
            if magg_header in text:
                pos = text.find(magg_header)
                next_sec = text.find("\n\n##", pos + len(magg_header))
                if next_sec > 0:
                    text = text[:next_sec] + "\n\n" + inject_block + text[next_sec:]
                else:
                    text = text + "\n\n" + inject_block
            else:
                text = text + f"\n\n{magg_header}\n\n{inject_block}"

        if opp_injections:
            opp_header = "## Posizioni dell\u2019Opposizione"
            opp_header_alt = "## Posizioni dell'Opposizione"
            inject_block = "\n\n".join(opp_injections)
            header_in_text = (
                opp_header if opp_header in text
                else (opp_header_alt if opp_header_alt in text else None)
            )
            if header_in_text:
                text = text + "\n\n" + inject_block
            else:
                text = text + f"\n\n{opp_header_alt}\n\n{inject_block}"

        if misto_injections:
            misto_header = "## Gruppo Misto"
            inject_block = "\n\n".join(misto_injections)
            if misto_header in text:
                text = text + "\n\n" + inject_block
            else:
                text = text + f"\n\n{misto_header}\n\n{inject_block}"

        return text

    def _group_evidence_by_party(
        self,
        evidence_list: List[Dict[str, Any]],
        parties: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Raggruppa le evidenze per gruppo parlamentare.

        Ordine: prima l'oratore più autorevole, perché per ogni gruppo
        risponda la persona più autorevole. Una semplice somma pesata dei
        punteggi lascia che i chunk molto simili di un oratore meno autorevole
        scavalchino il capogruppo. Per evitarlo si alternano gli oratori in due
        passi:

        1. Nel partito, i chunk si raggruppano per oratore.
        2. Per ogni oratore best_chunk_score =
               0.75 * similarity + 0.25 * salience
        3. Gli oratori si ordinano per
               0.70 * authority_score + 0.30 * best_chunk_score
           → primo è l'oratore più autorevole con almeno un chunk pertinente.
        4. Si alternano: miglior chunk dell'oratore 1, miglior chunk
           dell'oratore 2, poi il secondo dell'oratore 1, e così via.

        Così la posizione 1 va all'oratore in testa (conta soprattutto
        l'autorevolezza) e la 2 a un altro oratore: lo scrittore delle sezioni
        (e la deduplicazione semantica) ha una coppia davvero diversa.

        I membri del Governo (GovernmentMember) restano fuori: hanno una
        sezione loro.
        """
        from collections import defaultdict

        all_parties = parties if parties is not None else gruppi.nomi()
        by_party: Dict[str, List[Dict[str, Any]]] = {party: [] for party in all_parties}

        for evidence in evidence_list:
            # i membri del Governo hanno una sezione loro
            if evidence.get("speaker_role") == "GovernmentMember":
                continue

            # il partito attuale se l'oratore ha cambiato gruppo, così sotto ogni
            # gruppo compaiono solo i suoi membri di oggi
            party = (
                evidence.get("current_party")
                if evidence.get("party_changed") and evidence.get("current_party")
                else evidence.get("party", "Misto")
            )

            # la ricerca per sottostringa regge le varianti dei nomi; quello che
            # non corrisponde finisce nel Misto
            if party not in by_party:
                matched = False
                for known_party in all_parties:
                    if party in known_party or known_party in party:
                        by_party[known_party].append(evidence)
                        matched = True
                        break
                if not matched:
                    by_party.setdefault("Misto", []).append(evidence)
            else:
                by_party[party].append(evidence)

        for party in by_party:
            chunks = by_party[party]
            if not chunks:
                continue

            # salienza: il punteggio di citabilità dell'indicizzazione se c'è, altrimenti 0.5 neutro
            for e in chunks:
                if e.get("salience") is None:
                    cit = e.get("citability_score")
                    e["salience"] = float(cit) if cit is not None else 0.5

            speaker_chunks: Dict[str, list] = defaultdict(list)
            for e in chunks:
                speaker_chunks[e.get("speaker_id", "")].append(e)

            def _chunk_quality(e):
                return 0.75 * e.get("similarity", 0.0) + 0.25 * (e.get("salience") or 0.0)

            for sid in speaker_chunks:
                # prima i passaggi di un dibattito sul tema (card 201)
                speaker_chunks[sid].sort(key=lambda e: (debate_rank(e), -_chunk_quality(e)))

            def _speaker_rank(sid):
                auth = speaker_chunks[sid][0].get("authority_score", 0.0)
                best = _chunk_quality(speaker_chunks[sid][0])
                return 0.70 * auth + 0.30 * best

            sorted_speakers = sorted(
                speaker_chunks.keys(),
                key=lambda sid: (debate_rank(speaker_chunks[sid][0]), -_speaker_rank(sid)))

            if sorted_speakers and len(speaker_chunks) > 1:
                top_sid = sorted_speakers[0]
                top_auth = speaker_chunks[top_sid][0].get("authority_score", 0.0)
                top_best = _chunk_quality(speaker_chunks[top_sid][0])
                logger.info(
                    f"[PARTY RANKING] {party}: top speaker = "
                    f"{speaker_chunks[top_sid][0].get('speaker_name', top_sid)} "
                    f"(auth={top_auth:.2f}, best_chunk={top_best:.3f}, "
                    f"rank_score={_speaker_rank(top_sid):.3f}), "
                    f"total_speakers={len(sorted_speakers)}"
                )

            # alternanza: il miglior chunk di ogni oratore in classifica, poi il secondo, ...
            max_depth = max(len(v) for v in speaker_chunks.values())
            interleaved = []
            for depth in range(max_depth):
                for sid in sorted_speakers:
                    evs = speaker_chunks[sid]
                    if depth < len(evs):
                        interleaved.append(evs[depth])

            by_party[party] = interleaved

        return by_party

    def _check_coalition_balance(
        self,
        text: str
    ) -> Dict[str, Any]:
        """Misura l'equilibrio in parole tra le sezioni di maggioranza e opposizione.

        Segue il principio di copertura uguale di Coverage-based Fairness
        (NAACL 2025). balance_warning scatta quando una parte supera l'altra
        di oltre 2:1; il log tocca a chi chiama.
        """
        majority_section = ""
        opposition_section = ""

        sections = re.split(r'##\s+', text)
        for section in sections:
            if section.startswith("Posizioni della Maggioranza"):
                majority_section = section
            elif section.startswith("Posizioni dell'Opposizione") or section.startswith("Posizioni dell\u2019Opposizione"):
                opposition_section = section

        majority_words = len(majority_section.split())
        opposition_words = len(opposition_section.split())

        if opposition_words > 0:
            ratio = majority_words / opposition_words
        elif majority_words > 0:
            ratio = float('inf')
        else:
            ratio = 1.0

        return {
            "majority_words": majority_words,
            "opposition_words": opposition_words,
            "ratio": round(ratio, 2),
            "balance_warning": ratio > 2.0 or (1 / ratio if ratio > 0 else 0) > 2.0,
        }

    # sottostringhe minuscole che riconoscono il nome di ogni partito nel testo
    # generato. Per i partiti che mancano vale il pezzo prima di " - "
    _PARTY_SHORT_NAMES = {
        "Fratelli d'Italia": "fratelli d'italia",
        "Lega - Salvini Premier": "lega",
        "Forza Italia - Berlusconi Presidente - PPE": "forza italia",
        "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare": "noi moderati",
        "Partito Democratico - Italia Democratica e Progressista": "partito democratico",
        "Movimento 5 Stelle": "movimento 5 stelle",
        "Alleanza Verdi e Sinistra": "alleanza verdi",
        "Azione - Popolari Europeisti Riformatori - Renew Europe": "azione",
        "Italia Viva - Casa Riformista": "italia viva",
        # nome in uso prima del cambio dell'estate 2026
        "Italia Viva - Il Centro - Renew Europe": "italia viva",
        "Misto": "misto",
    }

    def _inject_missing_party_paragraphs(
        self,
        text: str,
        sections: List[Dict[str, Any]],
    ) -> tuple:
        """Controlla che ogni partito con evidenze sia nominato nel testo integrato.

        A volte il modello dell'integratore perde l'attacco obbligato «Per [Nome
        Partito],» o usa una sigla. In quel caso si inserisce la sezione
        originale (con i marcatori [CIT:id]), così testo e metrica di
        completezza non pagano un semplice errore di forma. I paragrafi della
        maggioranza vanno in fondo al suo blocco; quelli di opposizione e Misto
        in fondo al testo. Un partito fuori da ogni coalizione risulta inserito
        ma non viene aggiunto.

        Restituisce (testo, magari modificato; elenco dei partiti inseriti).
        """
        coalitions = gruppi.coalizioni()
        MAGGIORANZA = coalitions.get("maggioranza", [])
        OPPOSIZIONE = coalitions.get("opposizione", [])
        MISTO = coalitions.get("misto", [])

        text_lower = text.lower()
        magg_injections: List[str] = []
        opp_injections: List[str] = []
        misto_injections: List[str] = []
        injected: List[str] = []

        for section in sections:
            party = section.get("party", "")
            if party == "GOVERNO" or not section.get("has_evidence"):
                continue

            short = self._PARTY_SHORT_NAMES.get(party, party.split(" - ")[0]).lower()
            if short in text_lower:
                continue

            content = section.get("content", "")
            if not content:
                continue

            # via le righe di titolo ## che lo scrittore delle sezioni può aver aggiunto
            content = re.sub(r'^##\s+[^\n]*\n+', '', content.strip(), flags=re.MULTILINE)
            injected_para = party_lead(party, content)

            if party in MAGGIORANZA:
                magg_injections.append(injected_para)
            elif party in OPPOSIZIONE:
                opp_injections.append(injected_para)
            elif party in MISTO:
                misto_injections.append(injected_para)

            injected.append(party)
            logger.warning(f"Party injection: '{party}' missing from integrated text — injecting original section")

        if not injected:
            return text, []

        if magg_injections:
            magg_header = "## Posizioni della Maggioranza"
            inject_block = "\n\n".join(magg_injections)
            if magg_header in text:
                # prima della sezione successiva (## …) o in fondo al testo
                magg_pos = text.find(magg_header)
                next_section = text.find("\n\n##", magg_pos + len(magg_header))
                if next_section > 0:
                    text = text[:next_section] + "\n\n" + inject_block + text[next_section:]
                else:
                    text = text + "\n\n" + inject_block
            else:
                text = text + f"\n\n{magg_header}\n\n{inject_block}"

        if opp_injections:
            opp_header = "## Posizioni dell\u2019Opposizione"
            opp_header_alt = "## Posizioni dell'Opposizione"
            inject_block = "\n\n".join(opp_injections)
            header_in_text = opp_header if opp_header in text else (opp_header_alt if opp_header_alt in text else None)
            if header_in_text:
                text = text + "\n\n" + inject_block
            else:
                text = text + f"\n\n{opp_header_alt}\n\n{inject_block}"

        if misto_injections:
            misto_header = "## Gruppo Misto"
            inject_block = "\n\n".join(misto_injections)
            if misto_header in text:
                text = text + "\n\n" + inject_block
            else:
                text = text + f"\n\n{misto_header}\n\n{inject_block}"

        return text, injected

    def _get_government_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        min_similarity: float = 0.35,
        max_per_speaker: int = 3,
    ) -> List[Dict[str, Any]]:
        """Le evidenze dei membri del Governo, in ordine di autorevolezza dell'oratore.

        Una soglia minima di somiglianza esclude i membri del Governo i cui
        chunk non riguardano il tema della domanda.

        Alterna gli oratori come _group_evidence_by_party (conta soprattutto
        l'autorevolezza), così lo scrittore delle sezioni cita il ministro più
        pertinente per ruolo e non quello col chunk più simile.
        """
        from collections import defaultdict

        gov = [
            e for e in evidence_list
            if e.get("speaker_role") == "GovernmentMember"
            and e.get("similarity", 0.5) >= min_similarity
        ]

        if not gov:
            return []

        # salienza: il punteggio di citabilità dell'indicizzazione se c'è, altrimenti 0.5 neutro
        for e in gov:
            if e.get("salience") is None:
                cit = e.get("citability_score")
                e["salience"] = float(cit) if cit is not None else 0.5

        speaker_chunks: dict = defaultdict(list)
        for e in gov:
            speaker_chunks[e.get("speaker_id", "")].append(e)

        def _chunk_quality(e):
            return 0.75 * e.get("similarity", 0.0) + 0.25 * (e.get("salience") or 0.0)

        for sid in speaker_chunks:
            # prima i passaggi di un dibattito sul tema (card 201)
            speaker_chunks[sid].sort(key=lambda e: (debate_rank(e), -_chunk_quality(e)))

        def _speaker_rank(sid):
            auth = speaker_chunks[sid][0].get("authority_score", 0.0)
            best = _chunk_quality(speaker_chunks[sid][0])
            return 0.70 * auth + 0.30 * best

        sorted_speakers = sorted(
            speaker_chunks.keys(),
            key=lambda sid: (debate_rank(speaker_chunks[sid][0]), -_speaker_rank(sid)))

        if sorted_speakers:
            top_sid = sorted_speakers[0]
            top_auth = speaker_chunks[top_sid][0].get("authority_score", 0.0)
            top_name = speaker_chunks[top_sid][0].get("speaker_name", top_sid)
            logger.info(
                f"[GOV RANKING] top speaker = {top_name} "
                f"(auth={top_auth:.2f}, rank={_speaker_rank(top_sid):.3f}), "
                f"total_ministers={len(sorted_speakers)}"
            )

        # alternanza per profondità, al massimo max_per_speaker chunk per ministro
        max_depth = max(len(v) for v in speaker_chunks.values())
        filtered = []
        for depth in range(max_depth):
            if depth >= max_per_speaker:
                break
            for sid in sorted_speakers:
                evs = speaker_chunks[sid]
                if depth < len(evs):
                    filtered.append(evs[depth])

        return filtered


# titoli di dibattito che nominano una procedura e non un provvedimento: question
# time, ordine dei lavori, titoli di ripresa. Non dicono mai di cosa parla un fascicolo
_PROCEDURAL_TITLE = re.compile(
    r'(?i)^\s*(si riprende la discussione'
    r'|seguito della discussione\.?\s*$'
    r'|ripresa della discussione'
    r'|discussione congiunta\.?\s*$'
    r'|missioni\.?\s*$'
    r'|interventi di fine seduta'
    r'|ordine del giorno della prossima seduta'
    r'|svolgimento di interrogazioni'
    r'|svolgimento di interpellanze'
    r'|interrogazioni a risposta immediata'
    r'|sull.ordine dei lavori'
    r'|sui lavori dell)'
)
_TITLE_STOPWORDS = {
    "qual", "quale", "posizione", "gruppi", "parlamentari", "tema", "cosa",
    "come", "pensano", "partiti", "della", "delle", "degli", "dello", "nella",
    "sulla", "sulle", "sugli", "riforma", "legge", "misure", "disposizioni",
}
# quota delle evidenze con titolo che serve a un titolo per inquadrare
# l'introduzione quando non nomina il tema
_MAIN_TITLE_SHARE = 0.25


def _main_debate_title(evidence_list: List[Dict[str, Any]], query: str) -> Optional[str]:
    """Il provvedimento che l'introduzione può nominare: il titolo di dibattito
    più frequente, se nomina il tema o raccoglie un quarto delle evidenze.

    Un tema sparso su molti dibattiti non ha un provvedimento principale: gli
    interventi sul premierato cadono nel question time, nella legge elettorale
    e nel disegno di legge costituzionale del Senato, e nominarne uno inganna.
    Allora l'introduzione si ricava solo dalle sezioni dei gruppi.
    """
    from collections import Counter

    titles = [e.get("debate_title") for e in evidence_list if e.get("debate_title")]
    counts = Counter(t for t in titles if not _PROCEDURAL_TITLE.match(t))
    if not counts:
        return None
    title, n = counts.most_common(1)[0]
    words = [
        w for w in re.findall(r"[a-zàèéìòù]+", query.lower())
        if len(w) >= 4 and w not in _TITLE_STOPWORDS
    ]
    names_topic = bool(words) and all(w in title.lower() for w in words)
    return title if names_topic or n >= _MAIN_TITLE_SHARE * len(titles) else None
