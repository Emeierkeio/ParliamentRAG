"""
SSE contract tests — verify frozen event shapes and emission order.

These tests encode the frozen contract documented in backend/docs/SSE_CONTRACT.md.
Any change to event names, payload keys, or emission order that breaks these
tests requires a coordinated frontend change.

Tests do NOT import the routers at runtime (to avoid scipy/NumPy 2.x chain).
Instead, they inspect source files directly.
"""
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/


def _read_source(relative_path: str) -> str:
    """Read a source file relative to backend/."""
    return (_BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# chat.py event-type tests
# ---------------------------------------------------------------------------

class TestChatEventTypes:
    """Verify all contract-defined event types are present in chat.py.

    'waiting' events are emitted by PipelineQueue.acquire via the emit callback
    passed from process_chat_background. pipeline_queue.py is therefore included
    in the source scan as part of the chat pipeline infrastructure.
    """

    # Include pipeline_queue.py: 'waiting' events are delegated there via emit_fn callback
    CHAT_SOURCE = (
        _read_source("app/routers/chat.py")
        + "\n"
        + _read_source("app/services/pipeline_queue.py")
    )

    def test_chat_event_types_exist(self):
        """All event types documented in SSE_CONTRACT.md must appear in chat.py."""
        required_events = [
            "waiting",
            "progress",
            "commissioni",
            "experts",
            "citations",
            "balance",
            "compass",
            "topic_stats",
            "chunk",
            "citation_details",
            "hq_variants",
            "complete",
            "error",
        ]
        for event_type in required_events:
            # Match:
            #   {'type': 'event_type', ...}   — inline JSON
            #   sse_event("event_type", ...)  — helper call
            #   emit("event_type", ...)       — async emit call
            #   emit_fn("event_type", ...)    — emit-function call
            pattern = rf"['\"]type['\"]:\s*['\"]?{re.escape(event_type)}['\"]?"
            alt_sse = rf"sse_event\s*\(\s*['\"]?{re.escape(event_type)}['\"]?"
            alt_emit = rf"emit\s*\(\s*['\"]?{re.escape(event_type)}['\"]?"
            alt_emit_fn = rf"emit_fn\s*\(\s*['\"]?{re.escape(event_type)}['\"]?"
            found = (
                re.search(pattern, self.CHAT_SOURCE)
                or re.search(alt_sse, self.CHAT_SOURCE)
                or re.search(alt_emit, self.CHAT_SOURCE)
                or re.search(alt_emit_fn, self.CHAT_SOURCE)
            )
            assert found, (
                f"Event type '{event_type}' not found in chat.py. "
                f"This event is required by SSE_CONTRACT.md."
            )

    def test_chat_chunk_uses_content_key(self):
        """chat.py chunk event must use 'content' key, not 'data'."""
        # Find the chunk emission line
        # Expected pattern: emit("chunk", {"content": chunk})
        pattern = r'emit\s*\(\s*["\']chunk["\'].*?["\']content["\']'
        assert re.search(pattern, self.CHAT_SOURCE), (
            "chat.py must emit chunk events with 'content' key. "
            "SSE_CONTRACT.md: 'chat.py → content key'."
        )

    def test_chat_chunk_does_not_use_data_key(self):
        """chat.py chunk event must NOT use 'data' key (that is query.py's contract)."""
        # Find lines where chunk event is emitted with 'data' key
        # Only check the actual chunk event emission context
        chunk_lines = [
            line for line in self.CHAT_SOURCE.splitlines()
            if "chunk" in line and "emit" in line and "'data'" in line
        ]
        # Filter to only chunk event emissions (not other events that happen to have 'data')
        chunk_emit_with_data = [
            line for line in chunk_lines
            if re.search(r"emit.*chunk.*['\"]data['\"]", line)
        ]
        assert not chunk_emit_with_data, (
            f"chat.py must not use 'data' key in chunk events. "
            f"Found: {chunk_emit_with_data}"
        )

    def test_dual_experts_emission_chat(self):
        """chat.py must emit the 'experts' event at least twice (dual emission pattern)."""
        # Count occurrences of experts emission
        # Both emit("experts", ...) and sse_event("experts", ...) patterns
        emit_count = len(re.findall(r'emit\s*\(\s*["\']experts["\']', self.CHAT_SOURCE))
        sse_count = len(re.findall(r'sse_event\s*\(\s*["\']experts["\']', self.CHAT_SOURCE))
        total = emit_count + sse_count
        assert total >= 2, (
            f"chat.py must emit 'experts' at least twice (pre-generation + post-citation). "
            f"Found {total} emission(s). SSE_CONTRACT.md events #6 and #17."
        )

    def test_chat_sse_payloads_use_snake_case_authority(self):
        """Expert payloads must use 'authority_score' (snake_case), not 'authorityScore'."""
        assert "authority_score" in self.CHAT_SOURCE, (
            "chat.py must use 'authority_score' (snake_case) in expert payloads. "
            "SSE_CONTRACT.md: 'Payload field names use snake_case'."
        )
        assert "authorityScore" not in self.CHAT_SOURCE, (
            "chat.py must NOT use 'authorityScore' (camelCase) in expert payloads."
        )

    def test_chat_sse_payloads_use_snake_case_first_name(self):
        """Expert payloads must use 'first_name' (snake_case), not 'firstName'."""
        assert "first_name" in self.CHAT_SOURCE, (
            "chat.py must use 'first_name' (snake_case) in expert payloads."
        )
        assert "firstName" not in self.CHAT_SOURCE, (
            "chat.py must NOT use 'firstName' (camelCase)."
        )


# ---------------------------------------------------------------------------
# query.py event-type tests
# ---------------------------------------------------------------------------

class TestQueryEventTypes:
    """Verify all contract-defined event types are present in query.py."""

    QUERY_SOURCE = _read_source("app/routers/query.py")

    def test_query_event_types_exist(self):
        """All event types documented in SSE_CONTRACT.md must appear in query.py."""
        required_events = [
            "waiting",
            "progress",
            "experts",
            "compass",
            "topic_stats",
            "citations",
            "citation_details",
            "chunk",
            "complete",
            "error",
        ]
        for event_type in required_events:
            pattern = rf"['\"]type['\"]:\s*['\"]?{re.escape(event_type)}['\"]?"
            found = re.search(pattern, self.QUERY_SOURCE)
            assert found, (
                f"Event type '{event_type}' not found in query.py. "
                f"Required by SSE_CONTRACT.md."
            )

    def test_query_chunk_uses_data_key(self):
        """query.py chunk event must use 'data' key, not 'content'."""
        # Look for chunk event emission with 'data' key
        pattern = r"['\"]type['\"]\s*:\s*['\"]chunk['\"].*?['\"]data['\"]"
        alt_pattern = r"['\"]data['\"]\s*:\s*chunk"
        # Inline JSON: {"type": "chunk", "data": chunk}
        inline_pattern = r"'type':\s*'chunk'.*?'data'"
        found = re.search(pattern, self.QUERY_SOURCE) or re.search(inline_pattern, self.QUERY_SOURCE)
        assert found, (
            "query.py must emit chunk events with 'data' key. "
            "SSE_CONTRACT.md: 'query.py → data key'."
        )

    def test_dual_experts_emission_query(self):
        """query.py must emit the 'experts' event at least twice (dual emission pattern)."""
        count = len(re.findall(r"['\"]type['\"]\s*:\s*['\"]experts['\"]", self.QUERY_SOURCE))
        assert count >= 2, (
            f"query.py must emit 'experts' at least twice (pre + post-citation). "
            f"Found {count} emission(s). SSE_CONTRACT.md events #5 and #12."
        )


# ---------------------------------------------------------------------------
# Expert dict frozen fields
# ---------------------------------------------------------------------------

class TestExpertDictFrozenFields:
    """Verify the frozen expert dict shape is present in experts.py."""

    EXPERTS_SOURCE = _read_source("app/services/experts.py")

    def test_expert_dict_has_frozen_fields(self):
        """The expert dict construction must include all frozen fields from SSE_CONTRACT.md."""
        frozen_fields = [
            "id",
            "first_name",
            "last_name",
            "group",
            "coalition",
            "authority_score",
            "relevant_speeches_count",
            "score_breakdown",
        ]
        for field in frozen_fields:
            assert field in self.EXPERTS_SOURCE, (
                f"Frozen field '{field}' not found in experts.py. "
                f"All frozen fields must be constructed in the expert service. "
                f"SSE_CONTRACT.md Expert Dict Shape."
            )

    def test_expert_service_has_module_docstring(self):
        """experts.py must have a module-level docstring."""
        stripped = self.EXPERTS_SOURCE.lstrip()
        assert stripped.startswith('"""'), (
            "experts.py must start with a module-level docstring."
        )

    def test_expert_score_breakdown_fields(self):
        """score_breakdown must include the six sub-scores."""
        sub_scores = ["speeches", "acts", "committee", "profession", "education", "role"]
        for sub in sub_scores:
            assert sub in self.EXPERTS_SOURCE, (
                f"score_breakdown sub-score '{sub}' not found in experts.py."
            )


# ---------------------------------------------------------------------------
# Phase 14 — vote_coherence and vote_facts SSE event tests
# ---------------------------------------------------------------------------

class TestVoteCoherenceAndFactsEvents:
    """Verify vote_coherence and vote_facts SSE events are present in query.py
    and emitted AFTER citation_details (frozen emission order)."""

    QUERY_SOURCE = _read_source("app/routers/query.py")
    QUERY_LINES = QUERY_SOURCE.splitlines()

    def _first_line_of(self, literal: str) -> int:
        """Return 0-based line index of the first line containing literal, or -1."""
        for i, line in enumerate(self.QUERY_LINES):
            if literal in line:
                return i
        return -1

    def test_vote_coherence_event(self):
        """vote_coherence SSE event must be present in query.py and emitted after citation_details."""
        # Presence checks
        assert "'type': 'vote_coherence'" in self.QUERY_SOURCE or '"type": "vote_coherence"' in self.QUERY_SOURCE, (
            "query.py must emit a 'vote_coherence' SSE event (F1: speech-vote coherence)."
        )
        assert "votes_service.get_vote_coherence" in self.QUERY_SOURCE, (
            "query.py must call votes_service.get_vote_coherence to fetch coherence data."
        )
        # Emission order: citation_details line < vote_coherence line
        cit_line = self._first_line_of("citation_details")
        coh_line = self._first_line_of("vote_coherence")
        assert cit_line >= 0, "citation_details yield not found in query.py"
        assert coh_line > cit_line, (
            f"'vote_coherence' (line {coh_line}) must appear AFTER 'citation_details' (line {cit_line}) "
            f"so the frontend has citations before coherence data."
        )

    def test_vote_facts_event(self):
        """vote_facts SSE event must be present in query.py and emitted after citation_details."""
        # Presence checks
        assert "'type': 'vote_facts'" in self.QUERY_SOURCE or '"type": "vote_facts"' in self.QUERY_SOURCE, (
            "query.py must emit a 'vote_facts' SSE event (F4: vote-fact chips for the chat UI)."
        )
        assert "_fact_chips" in self.QUERY_SOURCE, (
            "query.py must build a _fact_chips list [{vote_id, debate_id, label}] for the vote_facts event."
        )
        assert "[VOTE-FACT-CHIPS] Failed (pipeline continues)" in self.QUERY_SOURCE, (
            "query.py must guard the vote_facts emission with a non-fatal try/except."
        )
        # Emission order: citation_details line < vote_facts line
        cit_line = self._first_line_of("citation_details")
        facts_line = self._first_line_of("'type': 'vote_facts'")
        if facts_line < 0:
            facts_line = self._first_line_of('"type": "vote_facts"')
        assert cit_line >= 0, "citation_details yield not found in query.py"
        assert facts_line > cit_line, (
            f"'vote_facts' (line {facts_line}) must appear AFTER 'citation_details' (line {cit_line})."
        )
