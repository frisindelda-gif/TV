"""Position Lab, rankings e avaliação no perfil (via API)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from fm27si.catalog import ATTRIBUTES
from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector
from fm27si.evaluation.engine import evaluate_player
from fm27si.evaluation.service import active_model, model_spec
from fm27si.evaluation.spec import POSITIONS, RANKING_GROUPS
from fm27si.importer import import_bundle
from fm27si.orm import PlayerEvaluation, SnapshotAttributes


@pytest.fixture
def demo(client):
    assert client.post("/api/import/demo", params={"players": 300, "seasons": 2}).status_code == 200
    return client


def test_original_model_is_builtin_active_and_read_only(demo):
    models = demo.get("/api/evaluation/models").json()
    orig = models[0]
    assert orig["builtin"] and orig["active"]
    assert demo.put(f"/api/evaluation/models/{orig['id']}", json={"name": "x"}).status_code == 409
    assert demo.post(f"/api/evaluation/models/{orig['id']}/reset").status_code == 409
    assert demo.delete(f"/api/evaluation/models/{orig['id']}").status_code == 409
    full = demo.get(f"/api/evaluation/models/{orig['id']}").json()
    m = full["metrics"][0]
    assert {"formula", "attributes", "used_by_positions", "category_label", "description"} <= set(m)


def test_lab_lifecycle_create_edit_reset_activate_recalc_delete(demo):
    orig = demo.get("/api/evaluation/models").json()[0]
    m = demo.post("/api/evaluation/models", json={"name": "O meu modelo"}).json()
    assert not m["builtin"] and m["spec_hash"] == orig["spec_hash"] and not m["modified_from_original"]

    spec = m["spec"]
    spec["metrics"].append({"key": "custom_engine", "name": "Motor", "category": "physical", "description": "",
                            "positions": [], "attributes": [{"attribute": "stamina", "weight": 2, "invert": False},
                                                            {"attribute": "work_rate", "weight": 1, "invert": False}]})
    st = next(p for p in spec["positions"] if p["key"] == "ST")
    st["metrics"].append({"metric": "custom_engine", "weight": 50})
    spec["roles"][0]["enabled"] = False
    u = demo.put(f"/api/evaluation/models/{m['id']}", json={"spec": spec, "description": "teste"}).json()
    assert u["modified_from_original"] and u["spec_hash"] != orig["spec_hash"]
    assert any(x["key"] == "custom_engine" for x in u["metrics"])

    bad = dict(spec, positions=spec["positions"][:-1])
    r = demo.put(f"/api/evaluation/models/{m['id']}", json={"spec": bad})
    assert r.status_code == 422 and "faltam modelos" in str(r.json())

    dup = demo.post(f"/api/evaluation/models/{m['id']}/duplicate").json()
    assert dup["spec_hash"] == u["spec_hash"] and dup["name"].endswith("(cópia)")

    assert demo.post(f"/api/evaluation/models/{m['id']}/activate").json()["active"]
    assert demo.get("/api/evaluation/state").json()["state"] == "missing"
    rc = demo.post("/api/evaluation/recalculate", json={}).json()
    assert rc["players"] > 0 and rc["spec_hash"] == u["spec_hash"]
    assert demo.get("/api/evaluation/state").json()["state"] == "fresh"
    first = demo.get("/api/rankings", params={"group": "ST", "limit": 1}).json()["items"][0]
    assert spec["roles"][0]["key"] not in first["role_scores"]  # função desativada não é calculada

    # pesos alterados → avaliações guardadas ficam desatualizadas até recalcular
    spec["positions"][0]["metrics"][0]["weight"] += 5
    demo.put(f"/api/evaluation/models/{m['id']}", json={"spec": spec})
    assert demo.get("/api/evaluation/state").json()["state"] == "stale"

    reset = demo.post(f"/api/evaluation/models/{m['id']}/reset").json()
    assert reset["spec_hash"] == orig["spec_hash"] and reset["name"] == "O meu modelo"
    assert demo.delete(f"/api/evaluation/models/{m['id']}").status_code == 409  # ativo
    demo.post(f"/api/evaluation/models/{orig['id']}/activate")
    assert demo.delete(f"/api/evaluation/models/{m['id']}").status_code == 200


@pytest.mark.parametrize("group", list(RANKING_GROUPS))
def test_each_ranking_group(demo, group):
    r = demo.get("/api/rankings", params={"group": group, "limit": 500}).json()
    assert r["total"] > 0 and r["state"] == "fresh"
    scores = [x["score"] for x in r["items"]]
    assert scores == sorted(scores, reverse=True)
    members = set(RANKING_GROUPS[group][1])
    for x in r["items"]:
        assert members & set(x["positions"]), "só jogadores competentes num lugar do grupo"
        assert x["score"] == max(v for p, v in x["group_positions"].items() if p in x["positions"] and v is not None)
    everyone = demo.get("/api/rankings", params={"group": group, "eligible_only": False}).json()
    assert everyone["total"] >= r["total"]


def test_ranking_sorting_and_filters(demo):
    for sort in ("ca", "pa", "age", "market_value", "best_role", "role:target_man", "position:ST"):
        r = demo.get("/api/rankings", params={"group": "ST", "sort": sort, "limit": 500})
        assert r.status_code == 200, sort
    r = demo.get("/api/rankings", params={"group": "ST", "sort": "role:target_man", "limit": 500}).json()
    vals = [x["role_scores"].get("target_man") for x in r["items"]]
    assert vals == sorted(vals, reverse=True)
    young = demo.get("/api/rankings", params={"group": "W", "max_age": 21, "limit": 500}).json()
    assert all(x["age"] <= 21 for x in young["items"])
    assert demo.get("/api/rankings", params={"group": "XX"}).status_code == 422
    assert demo.get("/api/rankings", params={"group": "ST", "sort": "xpto"}).status_code == 422


def test_profile_evaluation(demo):
    top = demo.get("/api/rankings", params={"group": "CB", "limit": 1}).json()["items"][0]
    d = demo.get(f"/api/players/{top['player_id']}/evaluation").json()
    assert len(d["positions"]) == 12 and {p["key"] for p in d["positions"]} == set(POSITIONS)
    assert d["focus"] in d["eligible_positions"]
    assert d["ranking"]["position"] == d["focus"]
    if d["focus"] == "DC":
        assert d["ranking"]["rank"] == 1  # é o primeiro do ranking de centrais
    assert all(x["diff"] > 0 for x in d["strengths"]) and all(x["diff"] < 0 for x in d["weaknesses"])
    assert d["comparison"] and all("position_mean" in x for x in d["comparison"])
    assert d["attributes_vs_position"] and d["data_status"] == "estimate"  # demonstração
    assert all(m["confidence"] == "low" for m in d["metrics"])  # dados fictícios nunca têm confiança alta
    other = demo.get(f"/api/players/{top['player_id']}/evaluation", params={"position": "ST"}).json()
    assert other["focus"] == "ST"
    assert demo.get("/api/players/999999/evaluation").status_code == 404


def test_stored_scores_equal_live_engine_and_are_reproducible(demo, db):
    with db.sessionmaker() as s:
        model = active_model(s)
        spec = model_spec(model)
        evs = s.scalars(select(PlayerEvaluation).where(PlayerEvaluation.model_id == model.id).limit(25)).all()
        before = {e.snapshot_id: dict(e.position_scores) for e in evs}
        for e in evs:
            arow = s.get(SnapshotAttributes, e.snapshot_id)
            live = evaluate_player(spec, {k: getattr(arow, k) for k in ATTRIBUTES})
            assert {p["key"]: p["score"] for p in live["positions"]} == e.position_scores
            assert e.spec_hash == model.spec_hash
    demo.post("/api/evaluation/recalculate", json={})
    with db.sessionmaker() as s:
        after = {e.snapshot_id: e.position_scores for e in s.scalars(
            select(PlayerEvaluation).where(PlayerEvaluation.snapshot_id.in_(list(before))))}
    assert after == before


def test_best_role_respects_eligible_positions(demo):
    r = demo.get("/api/rankings", params={"group": "CB", "limit": 500}).json()
    gk_or_st_roles = {"sweeper_keeper", "pressing_forward", "false_nine", "target_man"}
    only_cb = [x for x in r["items"] if set(x["positions"]) <= {"DC"}]
    assert only_cb and all(x["best_role"] not in gk_or_st_roles for x in only_cb)


def test_incomplete_data_flagged_not_zeroed(session, small_dump):
    res = import_bundle(session, FMSuperScoutLiveConnector().from_dict(small_dump))
    ev = {e.snapshot_id: e for e in session.scalars(select(PlayerEvaluation).where(PlayerEvaluation.run_id == res.run.id))}
    from fm27si.orm import PlayerSnapshot

    bad = session.scalar(select(PlayerSnapshot).where(PlayerSnapshot.source_uid == 91000003))
    e = ev[bad.id]
    assert e.min_coverage < 1  # atributos em falta
    assert all(v is None or v >= 0 for v in e.position_scores.values())
    good = session.scalar(select(PlayerSnapshot).where(PlayerSnapshot.source_uid == 91000001))
    assert ev[good.id].min_coverage == 1 and ev[good.id].confidence == "high"  # FMSuperScout: atributos verificados


def test_preview_uses_unsaved_weights(demo):
    m = demo.get(f"/api/evaluation/models/{demo.get('/api/evaluation/models').json()[0]['id']}").json()
    pid = demo.get("/api/rankings", params={"group": "ST", "limit": 1}).json()["items"][0]["player_id"]
    base = demo.post("/api/evaluation/preview", json={"spec": m["spec"], "player_id": pid}).json()
    spec = m["spec"]
    st = next(p for p in spec["positions"] if p["key"] == "ST")
    st["metrics"] = [{"metric": "gk_shot_stopping", "weight": 1}]  # absurdo de propósito
    changed = demo.post("/api/evaluation/preview", json={"spec": spec, "player_id": pid}).json()
    s0 = next(p["score"] for p in base["positions"] if p["key"] == "ST")
    s1 = next(p["score"] for p in changed["positions"] if p["key"] == "ST")
    assert s1 < s0
    spec["min_coverage"] = 5
    assert demo.post("/api/evaluation/preview", json={"spec": spec, "player_id": pid}).status_code == 422


def test_players_list_shows_best_position_and_role(demo):
    rows = demo.get("/api/players", params={"limit": 50}).json()["items"]
    assert all(r["best_position"] in POSITIONS for r in rows)
    assert all(r["best_role"] for r in rows)
    srt = demo.get("/api/players", params={"sort": "best_position_score", "limit": 20}).json()["items"]
    vals = [r["best_position_score"] for r in srt]
    assert vals == sorted(vals, reverse=True)
