"""Fase 3 — Percentis, rankings e universos de comparação."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fm27si.stats.catalog import default_catalog
from fm27si.stats.data import RunStats
from fm27si.stats.engine import DerivedMetricEngine
from fm27si.stats.percentiles import UNKNOWN_COMPETITION, Universe, compute

CAT = default_catalog()
FIELDS = list(CAT.fields)


def make_rs(rows: list[dict]) -> RunStats:
    """rows: {fields..., 'comp', 'pos'} — dados mínimos para o motor de percentis."""
    n = len(rows)
    x = np.full((n, len(FIELDS)), np.nan)
    for i, r in enumerate(rows):
        for k, v in r.items():
            if k in FIELDS:
                x[i, FIELDS.index(k)] = v
    pos = [r.get("pos", "DC") for r in rows]
    from fm27si.stats.data import POS_TO_GROUP

    nan = np.full(n, np.nan)
    rs = RunStats(
        run_id=1, scope="club", profile="fmsave", mapping={}, game_date=None,
        snapshot_ids=np.arange(1, n + 1), player_ids=np.arange(1, n + 1), names=[f"J{i}" for i in range(n)],
        clubs=[None] * n, competitions=[r.get("comp") for r in rows], positions=pos,
        groups=[POS_TO_GROUP[p] for p in pos], natural_positions=[[p] for p in pos], nationalities=[[]] * n,
        feet=[None] * n, age=nan, ca=nan, pa=nan, height=nan, market_value=nan, wage=nan, contract_days=nan,
        contract_expires=[None] * n, listed=np.zeros(n, bool), loan_listed=np.zeros(n, bool),
        fields=FIELDS, x=x, raw_presence={},
    )
    rs.result = DerivedMetricEngine(CAT, FIELDS).compute(x)
    return rs


def u(**kw) -> Universe:
    return Universe(**{"min_sample": 5, **kw})


def test_percentile_formula_and_rank():
    rs = make_rs([{"minutes": 900, "goals": g} for g in range(1, 11)])
    r = compute(rs, CAT, "goals", u())
    # valor 10: 9 abaixo, 0 empates além dele → 100 × (9 + 0,5) / 10 = 95
    assert r.percentile[9] == 95.0 and r.percentile[0] == 5.0
    assert r.rank[9] == 1 and r.rank[0] == 10
    st = r.stats_for(0)
    assert st["with_value"] == 10 and st["mean"] == 5.5 and st["median"] == 5.5
    assert st["best"] == 10 and st["worst"] == 1 and st["coverage"] == 1.0


def test_ties_use_half_weight():
    rs = make_rs([{"minutes": 900, "goals": g} for g in [1, 2, 2, 2, 3]])
    r = compute(rs, CAT, "goals", u())
    assert r.percentile[1] == r.percentile[2] == 50.0  # 1 abaixo + 0,5×3 → 2,5/5
    assert r.rank[1] == 2  # só um estritamente melhor


def test_lower_is_better_inverted():
    rs = make_rs([{"minutes": 900, "possession_lost": v} for v in range(1, 11)])
    r = compute(rs, CAT, "possession_lost", u())
    assert r.percentile[0] == 95.0 and r.rank[0] == 1  # menos perdas = melhor


def test_min_minutes_and_insufficient_sample():
    rows = [{"minutes": 900, "goals": g} for g in range(6)] + [{"minutes": 100, "goals": 50}]
    r = compute(make_rs(rows), CAT, "goals", u(min_minutes=450))
    assert math.isnan(r.percentile[6]) and not r.eligible[6]
    r2 = compute(make_rs(rows), CAT, "goals", u(min_minutes=450, min_sample=10))
    assert np.isnan(r2.percentile).all()
    assert r2.stats_for(0)["sufficient"] is False


def test_partitions_by_competition_and_position():
    rows = ([{"minutes": 900, "goals": g, "comp": "Liga A", "pos": "ST"} for g in range(5)]
            + [{"minutes": 900, "goals": g * 10, "comp": "Liga B", "pos": "ST"} for g in range(5)]
            + [{"minutes": 900, "goals": g, "comp": "Liga A", "pos": "DC"} for g in range(5)])
    rs = make_rs(rows)
    same = compute(rs, CAT, "goals", u())
    assert same.percentile[4] == same.percentile[9] == 90.0  # melhor de cada liga
    assert same.partition[0] != same.partition[5]
    allc = compute(rs, CAT, "goals", u(competition="all"))
    assert allc.percentile[9] > allc.percentile[4]  # comparados entre ligas
    allp = compute(rs, CAT, "goals", u(position_level="all"))
    assert allp.stats_for(0)["with_value"] == 10  # Liga A, todas as posições


def test_unknown_competition_is_labelled():
    rs = make_rs([{"minutes": 900, "goals": g} for g in range(5)])
    r = compute(rs, CAT, "goals", u())
    assert r.stats_for(0)["competition"] == UNKNOWN_COMPETITION


def test_population_subset():
    rs = make_rs([{"minutes": 900, "goals": g} for g in range(10)])
    r = compute(rs, CAT, "goals", u(population=(6, 7, 8, 9, 10), population_label="shortlist"))
    assert np.isnan(r.percentile[:5]).all() and r.stats_for(9)["with_value"] == 5
    assert "shortlist" in u(population=(1,), population_label="shortlist").describe()


def test_missing_values_reduce_coverage_not_counted_as_zero():
    rows = [{"minutes": 900, "goals": g} for g in range(6)] + [{"minutes": 900} for _ in range(4)]
    r = compute(make_rs(rows), CAT, "goals", u())
    st = r.stats_for(0)
    assert st["eligible"] == 10 and st["with_value"] == 6 and st["coverage"] == 0.6
    assert np.isnan(r.percentile[6:]).all()


def test_per90_view_and_percentage_view():
    rows = [{"minutes": m, "goals": 9, "shots": 30} for m in (900, 1800, 2700, 450, 3600)]
    rs = make_rs(rows)
    p90 = compute(rs, CAT, "goals@p90", u())
    assert p90.values[0] == pytest.approx(0.9) and p90.rank[3] == 1  # menos minutos, mais golos /90
    pct = compute(rs, CAT, "conversion_pct", u())
    assert pct.values[0] == 30.0
