"""
Source-inspection tests for timeline legislature filter.

Verifies that GET /api/timeline accepts a legislature query param (default 19)
and that get_sessions Cypher filters sessions by s.legislature = $legislature.

Uses source-file inspection (no live import) to avoid scipy/NumPy 2.x
incompatibility in the test environment.
"""
from pathlib import Path

ROUTER = Path(__file__).parent.parent / "app" / "routers" / "timeline.py"
SERVICE = Path(__file__).parent.parent / "app" / "services" / "timeline_service.py"


def test_router_has_legislature_param():
    src = ROUTER.read_text()
    assert "legislature: int = 19" in src, "get_timeline must add legislature: int = 19 query param"
    assert "legislature=legislature" in src, "router must forward legislature to get_sessions"


def test_default_filter():
    src = SERVICE.read_text()
    assert "legislature: int = 19" in src, "get_sessions must accept legislature: int = 19"
    assert "s.legislature = $legislature" in src, "get_sessions Cypher must filter AND s.legislature = $legislature"
    assert '"legislature": legislature' in src, "get_sessions params must include legislature"
