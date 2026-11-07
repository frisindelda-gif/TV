"""Métricas derivadas, percentis, crescimento e painel."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector
from fm27si.db import Database
from fm27si.importer import import_bundle
from fm27si.metrics import MIN_MINUTES_FOR_PERCENTILE, aggregate, compute, percentiles, position_group
from fm27si.orm import PlayerSnapshot
from fm27si.schemas import SeasonStats


def line(kind="league", **kw) -> SeasonStats:
    core = {k: kw.pop(k) for k in list(kw) if k in SeasonStats.model_fields}
    return SeasonStats(competition_kind=kind, **core, extra=kw)


def test_per90_and_percentages():
    vals, minutes = compute(
        [line(minutes=1800, starts=20, goals=10, expected_goals=8.0, assists=4, shots=50, shots_on_target=20,
              passes_attempted=1000, passes_completed=800, average_rating=7.1)],
        "ST",
    )
    assert minutes == 1800
    assert vals["goals_90"] == pytest.approx(0.5)
    assert vals["xg_90"] == pytest.approx(0.4)
    assert vals["shots_on_target_pct"] == 40.0
    assert vals["conversion_pct"] == 20.0
    assert vals["pass_pct"] == 80.0
    assert vals["goals_minus_xg"] == 2.0
    assert vals["average_rating"] == 7.1
    assert "save_pct" not in vals  # métrica só de guarda-redes


def test_missing_data_stays_none_never_invented():
    vals, _ = compute([line(minutes=900, goals=1, shots=0)], "ST")
    assert vals["conversion_pct"] is None  # 0 remates: sem denominador
    assert vals["xg_90"] is None  # xG não fornecido
    assert vals["goals_90"] == 0.1


def test_goalkeeper_metrics():
    vals, _ = compute(
        [line(minutes=900, starts=10, clean_sheets=4, shots_on_target_faced=40, saves_held=10, saves_parried=15,
              saves_tipped=5, goals_allowed=10, expected_goals_prevented=2.0)],
        "GK",
    )
    assert vals["save_pct"] == 75.0
    assert vals["goals_allowed_90"] == 1.0
    assert vals["clean_sheet_pct"] == 40.0
    assert vals["xgp_90"] == 0.2
    assert "goals_90" not in vals


def test_aggregate_prefers_overall_and_excludes_national_team():
    lines = [line("league", minutes=900, goals=5), line("cup", minutes=180, goals=1), line("international", minutes=270, goals=3)]
    assert aggregate(lines)["goals"] == 6  # liga + taça, sem seleção
    with_overall = [*lines, line("overall", minutes=1080, goals=6)]
    assert aggregate(with_overall)["minutes"] == 1080
    assert compute([], "ST") == ({}, 0.0)


def test_position_groups():
    assert position_group(["GK"]) == "GK"
    assert position_group(["DC"]) == "CB"
    assert position_group(["WBR", "DR"]) == "FB"
    assert position_group(["AMR"]) == "WM"
    assert position_group([], ["ST"]) == "ST"
    assert position_group([]) is None


def test_percentiles_rank_invert_and_thresholds():
    m = MIN_MINUTES_FOR_PERCENTILE
    rows = [(i, "ST", m, {"goals_90": g, "fouls_90": f}) for i, (g, f) in enumerate([(0.1, 3), (0.2, 2), (0.3, 1), (0.4, 0.5), (0.5, 0.2)], start=1)]
    rows.append((99, "ST", m - 1, {"goals_90": 9.9, "fouls_90": 0}))  # poucos minutos: fora da comparação
    rows += [(200 + i, "CB", m, {"goals_90": 1.0}) for i in range(3)]  # grupo pequeno demais
    pct = percentiles(rows)
    assert pct[5]["goals_90"] == 90.0 and pct[1]["goals_90"] == 10.0
    assert pct[5]["fouls_90"] == 90.0  # menos faltas = melhor
    assert 99 not in pct and 200 not in pct


def _dump(small_dump, date, ca_shift=0):
    import copy

    d = copy.deepcopy(small_dump)
    d["meta"]["gameDate"] = date
    for p in d["players"]:
        if p["ca"]:
            p["ca"] = min(200, p["ca"] + ca_shift)
    return FMSuperScoutLiveConnector().from_dict(d)


def test_growth_between_imports(session, small_dump):
    r1 = import_bundle(session, _dump(small_dump, "2026-08-20"), career_key="k")
    first = session.query(PlayerSnapshot).filter_by(run_id=r1.run.id, source_uid=91000001).one()
    assert first.ca_delta is None and first.is_new is None  # 1.ª importação: indefinido

    small_dump["players"].append(dict(small_dump["players"][0], id=91000099, name="Regen Novo", age=15, birthYear=2011))
    r2 = import_bundle(session, _dump(small_dump, "2027-08-20", ca_shift=6), career_key="k")
    snap = session.query(PlayerSnapshot).filter_by(run_id=r2.run.id, source_uid=91000001).one()
    assert snap.ca_delta == 6 and snap.is_new is False and snap.prev_snapshot_id == first.id
    regen = session.query(PlayerSnapshot).filter_by(run_id=r2.run.id, source_uid=91000099).one()
    assert regen.is_new is True and regen.ca_delta is None

    # Um save mais antigo importado depois compara com o que é anterior a ELE, não com o último importado.
    r3 = import_bundle(session, _dump(small_dump, "2027-01-10", ca_shift=3), career_key="k")
    mid = session.query(PlayerSnapshot).filter_by(run_id=r3.run.id, source_uid=91000001).one()
    assert mid.prev_snapshot_id == first.id and mid.ca_delta == 3


def test_api_metrics_sorting_filters_overview(client):
    assert client.post("/api/import/demo", params={"players": 300, "seasons": 2}).status_code == 200
    cat = client.get("/api/metrics").json()
    assert "goals_90" in {m["key"] for m in cat["metrics"]} and "ST" in cat["radar"]

    top = client.get("/api/players", params={"sort": "m:goals_90", "min_minutes": 450, "limit": 20}).json()["items"]
    vals = [x["metric_value"] for x in top]
    assert vals == sorted(vals, reverse=True) and all(x["minutes"] >= 450 for x in top)

    rows = client.get("/api/players", params=[("min_metric", "pass_pct:80"), ("limit", 500)]).json()["items"]
    assert rows and all(x["metric_key"] == "pass_pct" and x["metric_value"] >= 80 for x in rows)

    rows = client.get("/api/players", params={"min_percentile": "xg_90:75", "position_group": "ST", "limit": 500}).json()["items"]
    for r in rows:
        assert client.get(f"/api/players/{r['player_id']}").json()["metrics"]["percentiles"]["xg_90"] >= 75

    risers = client.get("/api/players", params={"sort": "ca_delta", "limit": 10}).json()["items"]
    assert [x["ca_delta"] for x in risers] == sorted([x["ca_delta"] for x in risers], reverse=True)
    assert client.get("/api/players", params={"new_only": True, "limit": 500}).json()["total"] > 0

    prof = client.get(f"/api/players/{top[0]['player_id']}").json()
    assert prof["metrics"]["status"] == "derived" and prof["metrics"]["peers"] >= 5
    assert prof["metrics"]["values"]["goals_90"] == top[0]["metric_value"]

    ov = client.get("/api/overview").json()
    assert ov["kpis"]["players"] == client.get("/api/players").json()["total"]
    assert sum(b["players"] for b in ov["ca_histogram"]) == ov["kpis"]["players"]
    assert ov["has_growth"] and ov["has_metrics"] and ov["top_risers"] and ov["top_rated"]

    for bad in ({"sort": "m:nada"}, {"sort": "xpto"}, {"min_metric": "goals_90:abc"}, {"position_group": "ZZ"}):
        assert client.get("/api/players", params=bad).status_code == 422


def test_migration_adds_new_columns_to_old_database(tmp_path):
    url = f"sqlite:///{tmp_path / 'velha.sqlite3'}"
    eng = create_engine(url)
    with eng.begin() as c:  # tabela de uma versão anterior, sem as colunas de crescimento
        c.execute(text("CREATE TABLE player_snapshots (id INTEGER PRIMARY KEY, player_id INTEGER, run_id INTEGER, "
                       "source_uid INTEGER, name VARCHAR(200), quality VARCHAR(10))"))
    eng.dispose()
    Database(url)
    cols = {c["name"] for c in inspect(create_engine(url)).get_columns("player_snapshots")}
    assert {"ca_delta", "pa_delta", "is_new", "position_group", "prev_snapshot_id"} <= cols
