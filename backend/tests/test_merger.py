"""Unit tests for the channel merger: dedup, score composition, quotas.

The merger is the methodological core of the paper (weighted fusion of the
two channels), so its arithmetic is pinned here with explicit weights rather
than the YAML ones: _compute_scores takes weights as arguments, which lets
the tests stay stable if the config is retuned.
"""
from app.services.retrieval.merger import ChannelMerger


def _result(eid, speaker="s1", party="Fratelli d'Italia", sim=0.8, cit=0.6):
    return {
        "evidence_id": eid,
        "speaker_id": speaker,
        "speaker_name": speaker,
        "party": party,
        "similarity": sim,
        "citability_score": cit,
        "retrieval_channel": "dense",
    }


def test_deduplicate_keeps_higher_similarity_from_dense():
    merger = ChannelMerger()
    dense = [_result("c1", sim=0.9), _result("c1", sim=0.7)]
    graph = [_result("c1", sim=0.99)]
    out = merger._deduplicate(dense, graph)
    assert len(out) == 1
    # Graph never overrides an id already seen in dense.
    assert out[0]["similarity"] == 0.9


def test_compute_scores_is_the_declared_weighted_sum():
    merger = ChannelMerger()
    r = _result("c1", sim=0.8, cit=0.6)
    scored = merger._compute_scores(
        [r],
        authority_scores={"s1": 0.9},
        relevance_weight=0.35,
        diversity_weight=0.15,
        coverage_weight=0.20,
        authority_weight=0.05,
        salience_weight=0.25,
    )[0]
    comp = scored["score_components"]
    # Single result: its speaker and party are the max counts, so the soft
    # penalties evaluate to 1 - 0.5*1 = 0.5 for both diversity and coverage.
    assert comp["relevance"] == 0.8
    assert comp["diversity"] == 0.5
    assert comp["coverage"] == 0.5
    assert comp["authority"] == 0.9
    assert comp["salience"] == 0.6
    expected = 0.35 * 0.8 + 0.15 * 0.5 + 0.20 * 0.5 + 0.05 * 0.9 + 0.25 * 0.6
    assert abs(scored["final_score"] - expected) < 1e-9


def test_compute_scores_defaults_without_authority():
    merger = ChannelMerger()
    scored = merger._compute_scores(
        [_result("c1")], None, 0.35, 0.15, 0.20, 0.05, 0.25
    )[0]
    assert scored["score_components"]["authority"] == 0.5


def test_select_diverse_respects_top_k_and_speaker_cap():
    merger = ChannelMerger()
    parties = list(merger.config.get_all_parties())[:2]
    results = []
    for i in range(80):
        r = _result(
            f"c{i}",
            speaker=f"sp{i % 8}",
            party=parties[i % 2],
            sim=1.0 - i * 0.01,
        )
        r["final_score"] = r["similarity"]
        results.append(r)
    top_k = 30
    selected = merger._select_diverse(results, top_k=top_k)
    assert len(selected) <= top_k
    per_speaker = {}
    for r in selected:
        per_speaker[r["speaker_id"]] = per_speaker.get(r["speaker_id"], 0) + 1
    assert max(per_speaker.values()) <= top_k // 10


def test_select_diverse_min_party_quota_topup():
    merger = ChannelMerger()
    min_per_party = merger.config.retrieval.get("merger", {}).get("min_per_party", 5)
    parties = list(merger.config.get_all_parties())
    big, small = parties[0], parties[1]
    results = []
    # 40 strong chunks for the big party, from many speakers.
    for i in range(40):
        r = _result(f"b{i}", speaker=f"big{i}", party=big, sim=0.95 - i * 0.001)
        r["final_score"] = r["similarity"]
        results.append(r)
    # A handful of weak chunks for the small party.
    for i in range(min_per_party):
        r = _result(f"s{i}", speaker=f"small{i}", party=small, sim=0.10)
        r["final_score"] = r["similarity"]
        results.append(r)
    selected = merger._select_diverse(results, top_k=30)
    small_count = sum(1 for r in selected if r["party"] == small)
    assert small_count >= min_per_party
