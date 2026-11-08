"""Fase 2 — Motor de métricas derivadas: todas as fórmulas."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fm27si.stats.catalog import default_catalog
from fm27si.stats.engine import DerivedMetricEngine, per90

CAT = default_catalog()
FIELDS = list(CAT.fields)


def run(rows: list[dict[str, float]]) -> dict[str, list[float | None]]:
    x = np.full((len(rows), len(FIELDS)), np.nan)
    for i, r in enumerate(rows):
        for k, v in r.items():
            x[i, FIELDS.index(k)] = v
    res = DerivedMetricEngine(CAT, FIELDS).compute(x)
    return {m: [None if math.isnan(v) else round(float(v), 6) for v in res.column(m)] for m in res.metric_ids}


def one(row: dict[str, float]) -> dict[str, float | None]:
    return {k: v[0] for k, v in run([row]).items()}


def test_direct_fields_pass_through():
    for m in CAT.metrics.values():
        f = m.formulas[0]
        if "field" in f and m.type in ("count", "value"):
            assert one({f["field"]: 7})[m.id] == 7, m.id


def test_missing_data_is_null_never_zero():
    out = one({})
    assert all(v is None for v in out.values())


@pytest.mark.parametrize("metric", [m.id for m in CAT.metrics.values() if m.type == "percentage"])
def test_every_percentage(metric):
    expr = CAT.metrics[metric].formulas[0]["pct"]
    num_fields = CAT.required_fields(metric)[0]
    # Preenche cada campo com 10 (denominador) e o numerador com 4 → 40 %.
    den_fields = set().union(*[CAT.required_fields(expr[1]["metric"])[0]]) if "metric" in expr[1] else {expr[1]["field"]}
    row = {f: 10.0 for f in num_fields}
    for f in num_fields - den_fields:
        row[f] = 4.0
    out = one(row)[metric]
    assert out is not None and 0 <= out <= 100, (metric, row, out)
    zero = {**row, **{f: 0.0 for f in den_fields}}
    assert one(zero)[metric] is None  # denominador zero → NULL
    for f in num_fields:
        missing = {k: v for k, v in row.items() if k != f}
        assert one(missing)[metric] is None, (metric, f)


def test_percentage_values_examples():
    out = one({"passes_attempted": 200, "passes_completed": 170, "shots": 20, "shots_on_target": 8, "goals": 5,
               "clean_sheets": 6, "starts": 18, "sub_appearances": 2, "penalties_faced": 4, "penalties_saved": 1})
    assert out["pass_pct"] == 85.0
    assert out["shot_on_target_pct"] == 40.0 and out["conversion_pct"] == 25.0
    assert out["appearances"] == 20 and out["clean_sheet_pct"] == 30.0
    assert out["penalty_save_pct"] == 25.0


def test_impossible_percentage_is_null_and_counted():
    x = np.full((2, len(FIELDS)), np.nan)
    x[0, FIELDS.index("passes_attempted")] = 10
    x[0, FIELDS.index("passes_completed")] = 12  # impossível
    x[1, FIELDS.index("passes_attempted")] = 10
    x[1, FIELDS.index("passes_completed")] = 5
    res = DerivedMetricEngine(CAT, FIELDS).compute(x)
    col = res.column("pass_pct")
    assert math.isnan(col[0]) and col[1] == 50 and res.invalid["pass_pct"] == 1


def test_alternative_formulas():
    out = one({"saves_held": 10, "saves_parried": 5, "saves_tipped": 3, "shots_on_target_faced": 24})
    assert out["saves"] == 18 and out["save_pct"] == 75.0
    assert one({"saves": 20, "saves_held": 1, "saves_parried": 1, "saves_tipped": 1})["saves"] == 20  # direto primeiro
    assert one({"goals": 10, "penalty_goals": 3})["non_penalty_goals"] == 7
    assert one({"non_penalty_goals": 9, "goals": 10, "penalty_goals": 3})["non_penalty_goals"] == 9
    assert one({"shots": 30, "shots_outside_box": 12})["shots_inside_box"] == 18
    assert one({"goals_prevented": 2.5})["goals_prevented"] == 2.5
    assert one({"xg_on_target_faced": 12.0, "goals_conceded": 10})["goals_prevented"] == 2.0


def test_offensive_derived():
    out = one({"goals": 6, "assists": 4, "minutes": 1800, "shots": 30})
    assert out["goal_contributions"] == 10
    assert out["minutes_per_goal"] == 300 and out["shots_per_goal"] == 5
    assert out["goal_participations"] is None  # exige pré-assistências
    assert one({"goals": 6, "assists": 4, "second_assists": 2})["goal_participations"] == 12
    assert one({"goals": 0, "minutes": 900})["minutes_per_goal"] is None  # sem golos: indefinido, não infinito
    assert one({"goals": 3})["goal_contributions"] is None  # faltam assistências


def test_defensive_composed_indicators():
    out = one({"recoveries": 50, "interceptions": 20, "tackles_won": 15})
    assert out["recoveries_plus_interceptions"] == 70
    assert out["tackles_won_plus_interceptions"] == 35


def test_negative_count_is_invalid():
    x = np.full((1, len(FIELDS)), np.nan)
    x[0, FIELDS.index("goals")] = -1
    res = DerivedMetricEngine(CAT, FIELDS).compute(x)
    assert math.isnan(res.column("goals")[0]) and res.invalid["goals"] == 1


def test_per90():
    t = np.array([10.0, 5.0, 3.0, np.nan])
    mins = np.array([900.0, 0.0, np.nan, 900.0])
    out = per90(t, mins)
    assert out[0] == 1.0 and all(math.isnan(v) for v in out[1:])


def test_vectorised_rows_independent():
    rows = [{"goals": i, "shots": 10} for i in range(5)]
    out = run(rows)
    assert out["conversion_pct"] == [0.0, 10.0, 20.0, 30.0, 40.0]


def test_all_metrics_compute_with_every_field_present():
    row = {f: 10.0 for f in FIELDS}
    out = one(row)
    for m in CAT.metrics.values():
        assert out[m.id] is not None, m.id
