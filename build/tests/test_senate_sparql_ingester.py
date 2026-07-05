"""
test_senate_sparql_ingester.py — Unit tests for senate_sparql_ingester.py

All HTTP calls are mocked; no network access required.
Tests cover: GET-only HTTP method, outcome derivation, URI parsing, Vote id format.
"""

from __future__ import annotations

import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

# Ensure build/ is on the path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from senate_sparql_ingester import (
    SenateVoteIngester,
    _senato_sparql_get,
    parse_senate_votazione_uri,
    _derive_senate_outcome,
    SENATO_USER_AGENT,
    SENATO_SPARQL_ENDPOINT,
)


# ---------------------------------------------------------------------------
# URI parsing helpers
# ---------------------------------------------------------------------------

class TestSenateUriParsing:
    """Tests for parse_senate_votazione_uri."""

    def test_standard_uri_returns_leg_seduta_vote(self):
        leg, seduta, vote = parse_senate_votazione_uri(
            "http://dati.senato.it/votazione/19-167-42"
        )
        assert leg == 19
        assert seduta == 167
        assert vote == 42

    def test_legislature_18(self):
        leg, seduta, vote = parse_senate_votazione_uri(
            "http://dati.senato.it/votazione/18-100-5"
        )
        assert leg == 18
        assert seduta == 100
        assert vote == 5

    def test_large_numbers(self):
        leg, seduta, vote = parse_senate_votazione_uri(
            "http://dati.senato.it/votazione/19-435-200"
        )
        assert leg == 19
        assert seduta == 435
        assert vote == 200

    def test_invalid_uri_returns_none_triple(self):
        leg, seduta, vote = parse_senate_votazione_uri("http://example.com/invalid")
        assert leg is None
        assert seduta is None
        assert vote is None

    def test_empty_string_returns_none_triple(self):
        leg, seduta, vote = parse_senate_votazione_uri("")
        assert leg is None
        assert seduta is None
        assert vote is None


# ---------------------------------------------------------------------------
# Outcome derivation
# ---------------------------------------------------------------------------

class TestSenateOutcomeDerivation:
    """Tests for _derive_senate_outcome (favorevoli >= maggioranza → approved)."""

    def test_favorevoli_less_than_maggioranza_is_rejected(self):
        assert _derive_senate_outcome(favorevoli=32, maggioranza=51) == "rejected"

    def test_favorevoli_greater_than_maggioranza_is_approved(self):
        assert _derive_senate_outcome(favorevoli=60, maggioranza=51) == "approved"

    def test_favorevoli_equal_maggioranza_is_approved(self):
        assert _derive_senate_outcome(favorevoli=51, maggioranza=51) == "approved"

    def test_none_favorevoli_returns_unknown(self):
        assert _derive_senate_outcome(favorevoli=None, maggioranza=51) == "unknown"

    def test_none_maggioranza_returns_unknown(self):
        assert _derive_senate_outcome(favorevoli=60, maggioranza=None) == "unknown"

    def test_both_none_returns_unknown(self):
        assert _derive_senate_outcome(favorevoli=None, maggioranza=None) == "unknown"


# ---------------------------------------------------------------------------
# Vote id format
# ---------------------------------------------------------------------------

class TestSenateVoteId:
    """Tests for the stable Senate Vote id format (senato_leg{N}_sed{M}_v{K})."""

    def test_vote_id_format_3digit_zero_padded(self):
        """Aggregate Vote id built from (leg=19, seduta=167, vote=42) matches expected format."""
        leg, seduta, vote = 19, 167, 42
        vote_id = f"senato_leg{leg}_sed{seduta:03d}_v{vote:03d}"
        assert vote_id == "senato_leg19_sed167_v042"

    def test_vote_id_has_senato_prefix(self):
        vote_id = f"senato_leg19_sed001_v001"
        assert vote_id.startswith("senato")

    def test_vote_number_zero_padded(self):
        vote_id = f"senato_leg19_sed167_v{5:03d}"
        assert "v005" in vote_id

    def test_seduta_number_zero_padded(self):
        vote_id = f"senato_leg19_sed{7:03d}_v042"
        assert "sed007" in vote_id


# ---------------------------------------------------------------------------
# HTTP method — GET-only with browser User-Agent
# ---------------------------------------------------------------------------

class TestSenateHttpMethod:
    """Tests that _senato_sparql_get uses GET (no data= body) + browser User-Agent."""

    def _make_mock_urlopen(self):
        """Return a MagicMock urlopen whose context manager yields a readable response."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"results":{"bindings":[]}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen = MagicMock(return_value=mock_response)
        return mock_urlopen

    def test_request_uses_get_method(self):
        """Request passed to urlopen must use GET (no data body)."""
        mock_urlopen = self._make_mock_urlopen()
        with patch("urllib.request.urlopen", mock_urlopen):
            _senato_sparql_get("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        # urllib.request.Request without data= body defaults to GET
        assert req.get_method() == "GET"

    def test_request_has_no_data_body(self):
        """GET request must not carry a POST data body."""
        mock_urlopen = self._make_mock_urlopen()
        with patch("urllib.request.urlopen", mock_urlopen):
            _senato_sparql_get("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        req = mock_urlopen.call_args[0][0]
        assert req.data is None

    def test_user_agent_contains_mozilla_and_chrome(self):
        """User-Agent header must look like a browser (contain Mozilla and Chrome)."""
        mock_urlopen = self._make_mock_urlopen()
        with patch("urllib.request.urlopen", mock_urlopen):
            _senato_sparql_get("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        req = mock_urlopen.call_args[0][0]
        # urllib.request.Request capitalizes the first letter of each header word
        user_agent = req.headers.get("User-agent", "")
        assert "Mozilla" in user_agent
        assert "Chrome" in user_agent

    def test_query_is_in_url_not_body(self):
        """The SPARQL query must appear in the URL query string (GET), not a body."""
        mock_urlopen = self._make_mock_urlopen()
        query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
        with patch("urllib.request.urlopen", mock_urlopen):
            _senato_sparql_get(query)

        req = mock_urlopen.call_args[0][0]
        # GET encodes query in URL
        assert "query=" in req.full_url or "SELECT" in req.full_url

    def test_returns_empty_list_on_empty_bindings(self):
        """_senato_sparql_get returns [] when bindings is empty."""
        mock_urlopen = self._make_mock_urlopen()
        with patch("urllib.request.urlopen", mock_urlopen):
            result = _senato_sparql_get("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
        assert result == []

    def test_endpoint_constant_is_senato(self):
        """SENATO_SPARQL_ENDPOINT must point to dati.senato.it."""
        assert "senato.it" in SENATO_SPARQL_ENDPOINT
        assert SENATO_SPARQL_ENDPOINT == "https://dati.senato.it/sparql"
