"""
Source-inspection tests for legislature field on QueryRequest and ChatRequest.

Uses path-based source reading (no live imports) to avoid scipy/NumPy 2.x
incompatibility in the anaconda Python 3.12 environment.
"""
from pathlib import Path

QUERY_PATH = Path(__file__).parent.parent / "app" / "routers" / "query.py"
CHAT_PATH = Path(__file__).parent.parent / "app" / "routers" / "chat.py"


def test_legislature_field():
    src = QUERY_PATH.read_text()
    # QueryRequest must declare a legislature int field defaulting to 19
    assert "legislature: int = Field(default=19" in src, \
        "QueryRequest must add legislature: int = Field(default=19, ...)"


def test_chat_legislature_field():
    src = CHAT_PATH.read_text()
    assert "legislature: int = Field(default=19" in src, \
        "ChatRequest must add legislature: int = Field(default=19, ...)"


def test_query_propagates_legislature():
    src = QUERY_PATH.read_text()
    assert "legislature=" in src, \
        "process_query_streaming must pass legislature to retrieve()"
