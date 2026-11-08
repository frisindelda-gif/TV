"""Statistical Scouting via API: disponibilidade, descoberta, pesquisas, composites, comparação, perfil, mercado."""

from __future__ import annotations

import csv
import io

import pytest

from fm27si.stats.catalog import default_catalog


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    from fastapi.testclient import TestClient

    from fm27si.api import create_app
    from fm27si.db import Database

    db = Database(f"sqlite:///{tmp_path_factory.mktemp('stats') / 'db.sqlite3'}")
    c = TestClient(create_app(db))
    assert c.post("/api/import/demo", params={"players": 1200, "seasons": 2}).status_code == 200
    return c


def test_catalog_endpoint(api):
    cat = api.get("/api/stats/catalog").json()
    assert len(cat["metrics"]) == len(default_catalog().metrics) == 125
    assert [g["key"] for g in cat["groups"]] == ["GK", "CB", "FB", "DM", "CM", "WM", "AM", "W", "ST"]
    m = next(x for x in cat["metrics"] if x["id"] == "save_pct")
    assert m["formula_texts"] and m["direction"] == "higher" and m["type"] == "percentage" and not m["per90"]
    assert set(cat["min_minutes_options"]) == {450, 900, 1350, 1800}


def test_availability_per_save_keeps_global_catalog(api):
    av = api.get("/api/stats/availability").json()
    assert av["catalog_size"] == 125 and sum(av["counts"].values()) == 125
    items = {i["metric"]: i for i in av["items"]}
    assert items["goals"]["status"] == "AVAILABLE"
    assert items["pass_pct"]["status"] == "CALCULABLE"
    assert items["saves"]["status"] == "CALCULABLE"  # agarradas + para a frente + desviadas
    pc = items["progressive_carries"]
    assert pc["status"] == "UNAVAILABLE" and "Conduções progressivas" in pc["reason"]
    assert items["goal_participations"]["status"] == "PARTIAL"


def test_field_inventory_and_discovery_proposals(api):
    fields = {f["raw_key"]: f for f in api.get("/api/stats/fields").json()}
    assert fields["dribbles"]["mapped_field"] == "dribbles_completed" and fields["dribbles"]["confidence"] == "assumed"
    assert fields["expected_goals"]["mapped_field"] is None
    props = {p["raw_key"]: p for p in api.get("/api/stats/proposals").json()}
    assert {"expected_goals", "distance_km", "average_rating"} <= set(props)
    assert "rated_appearances" not in props  # campo de controlo, não é estatística
    xg = props["expected_goals"]
    assert xg["status"] == "pending" and xg["proposal"]["unit"] == "goals"
    assert props["open_play_key_passes"]["proposal"]["equivalent_metric"] == "key_passes"


def test_approve_and_reject_proposals(api):
    props = {p["raw_key"]: p for p in api.get("/api/stats/proposals", params={"status": "pending"}).json()}
    before = api.get("/api/stats/availability").json()
    r = api.post(f"/api/stats/proposals/{props['expected_goals']['id']}/approve", json={"groups": ["ST", "W"]})
    assert r.status_code == 200 and r.json()["metric_key"] == "custom_expected_goals"
    assert api.post(f"/api/stats/proposals/{props['expected_goals']['id']}/approve", json={}).status_code == 409
    after = api.get("/api/stats/availability").json()
    assert after["catalog_size"] == before["catalog_size"] + 1
    xg = next(i for i in after["items"] if i["metric"] == "custom_expected_goals")
    assert xg["status"] == "CUSTOM" and xg["players_with_value"] > 0 and set(xg["groups"]) == {"ST", "W"}
    res = api.post("/api/stats/search", json={"filters": {"group": "ST"}, "columns": ["custom_expected_goals@p90"],
                                              "sort": {"by": "value", "metric": "custom_expected_goals@p90"}}).json()
    assert res["items"][0]["metrics"]["custom_expected_goals@p90"]["value"] is not None
    assert api.post(f"/api/stats/proposals/{props['offsides']['id']}/reject").json() == {"rejected": props["offsides"]["id"]}
    assert len(default_catalog().metrics) == 125  # o catálogo base não muda


def test_search_and_or_conditions(api):
    base = {"filters": {"group": "ST"}, "columns": ["goals@p90", "shot_on_target_pct"], "limit": 1000}
    all_st = api.post("/api/stats/search", json=base).json()["total"]
    a = api.post("/api/stats/search", json={**base, "conditions": {"op": "and", "conditions": [
        {"metric": "goals@p90", "min": 0.3}, {"metric": "shot_on_target_pct", "kind": "percentile", "min": 50}]}}).json()
    o = api.post("/api/stats/search", json={**base, "conditions": {"op": "or", "conditions": [
        {"metric": "goals@p90", "min": 0.3}, {"metric": "shot_on_target_pct", "kind": "percentile", "min": 50}]}}).json()
    assert a["total"] <= o["total"] <= all_st and a["total"] > 0
    for it in a["items"]:
        assert it["metrics"]["goals@p90"]["value"] >= 0.3 and it["metrics"]["shot_on_target_pct"]["percentile"] >= 50
    nested = api.post("/api/stats/search", json={**base, "conditions": {"op": "and", "conditions": [
        {"op": "or", "conditions": [{"metric": "goals@p90", "min": 0.3}, {"metric": "assists@p90", "min": 0.3}]},
        {"metric": "goals@p90", "max": 2}]}}).json()
    assert nested["total"] >= 0


def test_missing_data_never_satisfies_or_counts_as_zero(api):
    res = api.post("/api/stats/search", json={"conditions": {"op": "and", "conditions": [
        {"metric": "progressive_carries@p90", "min": 0}]}}).json()
    assert res["total"] == 0  # métrica indisponível: ninguém passa, nem com mínimo 0
    assert any("Conduções progressivas" in n and "indisponível" in n.lower() for n in res["notes"])
    any_player = api.post("/api/stats/search", json={"columns": ["progressive_carries"], "limit": 1}).json()["items"][0]
    assert any_player["metrics"]["progressive_carries"]["value"] is None


def test_search_sorting_and_filters(api):
    r = api.post("/api/stats/search", json={"filters": {"group": "CM", "max_age": 25, "min_minutes": 900},
                                            "columns": ["pass_pct"], "sort": {"by": "percentile", "metric": "pass_pct"},
                                            "limit": 200}).json()
    pcts = [i["metrics"]["pass_pct"]["percentile"] for i in r["items"] if i["metrics"]["pass_pct"]["percentile"] is not None]
    assert pcts == sorted(pcts, reverse=True)
    assert all(i["age"] <= 25 and i["minutes"] >= 900 and i["group"] == "CM" for i in r["items"])
    for by in ("age", "market_value", "wage", "minutes", "name", "ca"):
        assert api.post("/api/stats/search", json={"sort": {"by": by}}).status_code == 200
    assert api.post("/api/stats/search", json={"columns": ["inexistente"]}).status_code == 422
    assert api.post("/api/stats/search", json={"filters": {"group": "XX"}}).status_code == 422


def test_export_csv(api):
    r = api.post("/api/stats/search/export", json={"filters": {"group": "ST"}, "columns": ["goals@p90"]})
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿")), delimiter=";"))
    assert rows[0][0] == "player_id" and "Golos por 90 minutos — percentil" in rows[0] and len(rows) > 1


def test_saved_searches(api):
    d = {"filters": {"group": "W", "max_age": 21}, "columns": ["dribbles_completed@p90"]}
    s = api.post("/api/stats/searches", json={"name": "Extremos jovens", "definition": d}).json()
    assert any(x["id"] == s["id"] for x in api.get("/api/stats/searches").json())
    assert api.post("/api/stats/searches", json={"name": "x", "definition": {"filters": {"group": "ZZ"}}}).status_code == 422
    assert api.delete(f"/api/stats/searches/{s['id']}").status_code == 200


def test_shortlists_and_population_universe(api):
    top = api.post("/api/stats/search", json={"filters": {"group": "ST"}, "limit": 12, "columns": ["goals@p90"]}).json()
    pids = [i["player_id"] for i in top["items"]]
    sl = api.post("/api/stats/shortlists", json={"name": "Avançados"}).json()
    assert api.post(f"/api/stats/shortlists/{sl['id']}/items", json={"player_ids": pids + pids[:2], "source": "teste"}).json() == {"added": 12}
    got = api.get(f"/api/stats/shortlists/{sl['id']}").json()
    assert len(got["items"]) == 12
    exp = api.get(f"/api/stats/shortlists/{sl['id']}/export")
    assert exp.status_code == 200 and len(exp.text.strip().splitlines()) == 13
    pop = api.post("/api/stats/search", json={"universe": {"shortlist_id": sl["id"], "competition": "all",
                                                           "min_sample": 3, "min_minutes": 0},
                                              "filters": {"group": "ST"}, "columns": ["goals@p90"], "limit": 100}).json()
    assert "shortlist" in pop["universe"]
    in_list = [i for i in pop["items"] if i["player_id"] in pids]
    assert all(i["metrics"]["goals@p90"]["universe"] <= 12 for i in in_list)
    assert api.delete(f"/api/stats/shortlists/{sl['id']}/items/{pids[0]}").status_code == 200
    assert api.delete(f"/api/stats/shortlists/{sl['id']}").status_code == 200


def test_composites_crud_and_coverage(api):
    comps = api.get("/api/stats/composites").json()
    assert len([c for c in comps if c["builtin"]]) == 6
    b = comps[0]
    assert api.put(f"/api/stats/composites/{b['id']}", json={**b, "name": "x"}).status_code == 409
    dup = api.post(f"/api/stats/composites/{b['id']}/duplicate").json()
    assert not dup["builtin"] and dup["components"] == b["components"]
    bad = {"name": "Mau", "group_key": "CB", "components": [{"metric": "pass_pct@p90", "weight": 1}]}
    assert api.post("/api/stats/composites", json=bad).status_code == 422
    # Cobertura mínima mais baixa permite avaliar com as componentes disponíveis neste save.
    low = api.put(f"/api/stats/composites/{dup['id']}", json={**dup, "min_coverage": 0.3}).json()
    r = api.post("/api/stats/search", json={"filters": {"group": low["group_key"]}, "composite_ids": [low["id"]],
                                            "sort": {"by": "composite", "composite_id": low["id"]}, "limit": 50}).json()
    scores = [i["composites"][str(low["id"])] for i in r["items"]]
    vals = [x["score"] for x in scores if x["score"] is not None]
    assert vals and vals == sorted(vals, reverse=True) and all(0 <= v <= 100 for v in vals)
    assert all(x["coverage"] < 1 for x in scores if x["coverage"] is not None)  # cobertura visível
    assert api.delete(f"/api/stats/composites/{dup['id']}").status_code == 200
    assert api.delete(f"/api/stats/composites/{b['id']}").status_code == 409


def test_identification_by_composite_minimum(api):
    comps = {c["key"]: c["id"] for c in api.get("/api/stats/composites").json()}
    cid = comps["st_finisher"]
    r = api.post("/api/stats/search", json={"filters": {"group": "ST"}, "composite_min": {str(cid): 60},
                                            "sort": {"by": "composite", "composite_id": cid}, "limit": 200}).json()
    assert r["total"] > 0 and all(i["composites"][str(cid)]["score"] >= 60 for i in r["items"])
    assert api.post("/api/stats/search", json={"composite_min": {"99999": 10}}).status_code == 422


def test_compare_profile_history(api):
    st = api.post("/api/stats/search", json={"filters": {"group": "ST", "min_minutes": 900}, "limit": 2}).json()["items"]
    cb = api.post("/api/stats/search", json={"filters": {"group": "CB", "min_minutes": 900}, "limit": 1}).json()["items"]
    ids = [st[0]["player_id"], st[1]["player_id"], cb[0]["player_id"]]
    cmp = api.post("/api/stats/compare", json={"player_ids": ids, "metrics": ["goals@p90", "aerial_duel_pct"]}).json()
    assert len(cmp["players"]) == 3 and any("posições diferentes" in w for w in cmp["warnings"])
    assert api.post("/api/stats/compare", json={"player_ids": ids + [1, 2]}).status_code == 422
    prof = api.get(f"/api/stats/players/{ids[0]}/profile").json()
    assert set(prof["tabs"]) == {"defensive", "passing", "progression", "attacking", "physical_duels", "pressing"}
    rows = {r["key"]: r for t in prof["tabs"].values() for r in t["rows"]}
    assert rows["goals@p90"]["status"] == "AVAILABLE" and "fmsave" in rows["goals@p90"]["source"]
    assert rows["progressive_carries"]["status"] == "UNAVAILABLE" and rows["progressive_carries"]["value"] is None
    assert prof["overview"] and prof["percentiles"]
    hist = api.get(f"/api/stats/players/{ids[0]}/history", params={"metrics": ["goals@p90"]}).json()
    assert hist and "goals@p90" in hist[0]["values"]


def test_percentile_analysis_and_market(api):
    pa = api.get("/api/stats/percentile-analysis", params={"metric": "pass_pct", "group": "CM"}).json()
    assert pa["histogram"] and pa["partitions"] and pa["top"]
    pid = pa["top"][0]["player_id"]
    pp = api.get("/api/stats/percentile-analysis", params={"metric": "pass_pct", "player_id": pid}).json()["player"]
    assert pp["position"]["universe"] != pp["competition"]["universe"]
    comps = {c["key"]: c["id"] for c in api.get("/api/stats/composites").json()}
    m = api.post("/api/stats/market", json={"composite_id": comps["st_finisher"], "min_performance": 40,
                                            "filters": {"max_value": 5_000_000}, "sort": "value"}).json()
    vals = [i["market_value"] for i in m["items"]]
    assert vals == sorted(vals) and all(v <= 5_000_000 for v in vals) and m["caveat"]
    assert all(i["performance"] >= 40 for i in m["items"])
    assert api.post("/api/stats/market", json={}).status_code == 422


def test_overview(api):
    ov = api.get("/api/stats/overview").json()
    assert ov["players_with_stats"] > 0 and ov["catalog_size"] >= 125
    assert sum(ov["availability"].values()) == ov["catalog_size"]
    assert {c["name"] for c in ov["composites"]} >= {"Central Defensivo Dominante", "Ponta de Lança Finalizador"}


# No fim: cria uma importação mais recente (live) noutra carreira.
def test_zz_live_import_without_stats_marks_everything_unavailable(api, small_dump_path):
    r = api.post("/api/import/live", json={"dump_path": str(small_dump_path), "career_key": "live-test"}).json()
    av = api.get("/api/stats/availability", params={"run_id": r["run"]["id"]}).json()
    assert av["counts"]["UNAVAILABLE"] == av["catalog_size"]
    assert "memória" in av["items"][0]["reason"]
