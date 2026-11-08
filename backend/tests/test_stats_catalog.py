"""Fase 1 — Catálogo global de métricas."""

from __future__ import annotations

import pytest

from fm27si.stats.catalog import Catalog, default_catalog
from fm27si.stats.catalog_data import COMPOSITES, METRICS, POSITION_MAP, TRANSVERSAL

CAT = default_catalog()

# Número de itens de cada secção do documento "Statistical Scouting" (§2.1–2.9).
EXPECTED_SECTION_SIZES = {
    "GK": [12, 9, 12, 6],
    "CB": [20, 13, 18, 9, 6, 8],
    "FB": [21, 14, 12, 8, 6],
    "DM": [15, 13, 8, 15, 7, 8, 5],
    "CM": [18, 8, 18, 6, 11, 6],
    "WM": [15, 10, 10, 8, 14, 4],
    "AM": [14, 9, 11, 7, 10, 4],
    "W": [11, 14, 11, 8, 12, 4],
    "ST": [19, 9, 10, 7, 8, 8, 4],
}


@pytest.mark.parametrize("group", list(EXPECTED_SECTION_SIZES))
def test_every_document_item_is_mapped(group):
    sizes = [len(items) for _title, items in POSITION_MAP[group]]
    assert sizes == EXPECTED_SECTION_SIZES[group]


@pytest.mark.parametrize("group", list(POSITION_MAP))
def test_mapped_items_resolve_to_metric_views(group):
    for _title, items in POSITION_MAP[group]:
        for key in items:
            m, view = CAT.parse_view(key)
            if view == "p90":
                assert m.per90 and m.type in ("count", "derived_count", "value")


def test_transversal_section_resolves():
    keys = [k for _t, items in TRANSVERSAL for k in items]
    assert len(keys) == 28
    for k in keys:
        CAT.parse_view(k)


def test_ids_unique_and_definitions_complete():
    ids = [m["id"] for m in METRICS]
    assert len(ids) == len(set(ids)) == len(CAT.metrics)
    for m in CAT.metrics.values():
        assert m.name and m.description and m.category and m.unit
        d = CAT.describe(m.id)
        assert d["formula_texts"] and d["source_fields"] and all(d["source_fields"])


def test_rates_have_no_per90_and_percentages_formula():
    for m in CAT.metrics.values():
        if m.type in ("percentage", "ratio"):
            assert not m.per90
        if m.type == "percentage":
            assert "pct" in m.formulas[0]
    with pytest.raises(KeyError):
        CAT.parse_view("pass_pct@p90")
    with pytest.raises(KeyError):
        CAT.parse_view("inexistente")


def test_lower_is_better_metrics():
    lower = {m.id for m in CAT.metrics.values() if m.direction == "lower"}
    assert {"possession_lost", "errors_leading_to_goal", "errors_leading_to_shot", "minutes_per_goal",
            "goals_conceded", "fouls_committed", "passes_intercepted", "big_chances_missed"} <= lower


def test_metric_reused_across_positions():
    assert set(CAT.metric_groups["pass_pct"]) >= {"GK", "CB", "FB", "DM", "CM", "WM", "AM", "W", "ST"}
    assert CAT.metric_groups["saves"] == ["GK"]


def test_alternative_formulas_and_fields():
    assert CAT.required_fields("saves") == [{"saves"}, {"saves_held", "saves_parried", "saves_tipped"}]
    assert CAT.required_fields("save_pct") == [{"saves", "shots_on_target_faced"}]
    assert CAT.required_fields("non_penalty_goals") == [{"non_penalty_goals"}, {"goals", "penalty_goals"}]


def test_composed_indicators_are_flagged():
    for k in ("recoveries_plus_interceptions", "tackles_won_plus_interceptions"):
        assert CAT.metrics[k].composed


def test_composites_reference_valid_views():
    assert {c["key"] for c in COMPOSITES} == {"cb_dominant", "cb_builder", "dm_ball_winner", "cm_creative",
                                               "w_dribbler", "st_finisher"}
    for c in COMPOSITES:
        for k in c["components"]:
            m, _ = CAT.parse_view(k)
            assert m.composite


def test_catalog_rejects_bad_definitions():
    bad = {"id": "x_bad", "name": "Bad", "description": "d", "category": "custom", "type": "count", "unit": "count",
           "formulas": [{"field": "campo_inexistente"}], "per90": True}
    with pytest.raises(ValueError, match="campo de origem desconhecido"):
        Catalog(custom=[bad])
    cyc = {**bad, "id": "x_cyc", "formulas": [{"metric": "x_cyc"}]}
    with pytest.raises(ValueError):
        Catalog(custom=[cyc])
    pct_p90 = {**bad, "id": "x_pct", "type": "percentage", "formulas": [{"pct": [{"field": "goals"}, {"field": "shots"}]}]}
    with pytest.raises(ValueError, match="por 90"):
        Catalog(custom=[pct_p90])


def test_custom_metric_with_custom_field():
    custom = {"id": "custom_xg", "name": "Golos esperados", "description": "xG", "category": "custom",
              "type": "value", "unit": "goals", "formulas": [{"field": "expected_goals"}], "per90": True,
              "groups": ["ST"]}
    c = Catalog(custom=[custom], custom_fields={"expected_goals": ("xG", "goals", "Golos esperados")})
    assert c.metrics["custom_xg"].validation_status == "custom" and not c.metrics["custom_xg"].builtin
    assert c.metric_groups["custom_xg"] == ["ST"]
    assert len(c.metrics) == len(CAT.metrics) + 1  # o catálogo base não muda
