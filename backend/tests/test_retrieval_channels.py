"""
Source-inspection tests for legislature filter in retrieval channels and engine.

Uses path-based source reading (no live imports) to avoid scipy/NumPy 2.x
incompatibility in the anaconda Python 3.12 environment.
"""
from pathlib import Path

BASE = Path(__file__).parent.parent / "app" / "services" / "retrieval"
CHANNELS = ["dense_channel.py", "sparse_channel.py", "ner_channel.py", "graph_channel.py"]


def test_legislature_param():
    for name in CHANNELS:
        src = (BASE / name).read_text()
        assert "legislature" in src, \
            f"{name} must accept a legislature parameter"
        assert "s.legislature = $legislature" in src, \
            f"{name} Cypher must filter AND s.legislature = $legislature"


def test_engine_threads_legislature():
    src = (BASE / "engine.py").read_text()
    assert "legislature" in src, \
        "engine.py must thread legislature through retrieve/retrieve_sync"
