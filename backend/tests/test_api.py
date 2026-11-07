"""Endpoints da API."""

from fm27si.catalog import PLAYER_ATTRIBUTE_KEYS


def _import(client, path, key=None):
    r = client.post("/api/import/live", json={"dump_path": str(path), "career_key": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert len(client.get("/api/attributes").json()) == 60


def test_players_list_and_filters(client, career_dumps):
    _import(client, career_dumps[0])
    page = client.get("/api/players", params={"limit": 10}).json()
    assert page["total"] == 400 and len(page["items"]) == 10
    cas = [p["ca"] for p in page["items"]]
    assert cas == sorted(cas, reverse=True)

    young = client.get("/api/players", params={"max_age": 19, "min_pa": 150, "limit": 500}).json()
    assert all(p["age"] <= 19 and p["pa"] >= 150 for p in young["items"])

    fast = client.get("/api/players", params=[("min_attr", "pace:15"), ("min_attr", "acceleration:14"), ("limit", 500)]).json()
    for row in fast["items"][:20]:
        prof = client.get(f"/api/players/{row['player_id']}").json()
        assert prof["attributes"]["physical"]["pace"] >= 15 and prof["attributes"]["physical"]["acceleration"] >= 14

    gk = client.get("/api/players", params={"position": "GK", "limit": 500}).json()
    assert gk["total"] > 0 and all("GK" in p["positions"] for p in gk["items"])

    assert client.get("/api/players", params={"min_attr": "magia:5"}).status_code == 422


def test_full_profile(client, small_dump_path):
    _import(client, small_dump_path)
    rows = client.get("/api/players", params={"q": "Sardinha"}).json()["items"]
    assert len(rows) == 1
    p = client.get(f"/api/players/{rows[0]['player_id']}").json()
    assert p["ability"] == {"ca": 112, "pa": 178, "pa_range_code": None}
    cats = p["attributes"]
    assert sum(len(cats[c]) for c in ("technical", "mental", "physical", "goalkeeping", "hidden")) == len(PLAYER_ATTRIBUTE_KEYS)
    assert len(cats["personality"]) == 8
    assert p["provenance"]["connector"] == "live_memory" and p["provenance"]["synthetic"] is True
    assert p["provenance"]["game_date"] == "2026-08-20"
    assert p["field_status"]["ca"] == "verified"
    assert p["contract"]["wage_weekly"] == 1500
    assert p["unavailable_fields"]
    assert len(p["history"]) == 1


def test_profile_history_across_seasons(client, career_dumps):
    for path in career_dumps:
        _import(client, path)
    careers = client.get("/api/careers").json()
    assert len(careers) == 1 and careers[0]["runs"] == 3
    runs = client.get(f"/api/careers/{careers[0]['id']}/runs").json()
    first = client.get("/api/players", params={"run_id": runs[0]["id"], "limit": 1, "sort": "age", "order": "asc"}).json()["items"][0]
    prof = client.get(f"/api/players/{first['player_id']}").json()
    assert len(prof["history"]) >= 2
    assert [h["run_id"] for h in prof["history"]] == sorted(h["run_id"] for h in prof["history"])
    old = client.get(f"/api/players/{first['player_id']}", params={"run_id": runs[0]["id"]}).json()
    assert old["ability"]["ca"] == prof["history"][0]["ca"]


def test_integrity_endpoint_and_errors(client, small_dump_path):
    run = _import(client, small_dump_path)["run"]
    rep = client.get(f"/api/runs/{run['id']}/integrity").json()
    assert rep["ok"] is False  # o dump pequeno inclui uma leitura corrompida de propósito
    assert client.get("/api/runs/999/integrity").status_code == 404
    assert client.get("/api/players/999").status_code == 404
    assert client.post("/api/import/live", json={"dump_path": "/nao/existe.json"}).status_code == 422
    assert client.post("/api/import/save", json={"path": "/nao/existe.fm"}).status_code == 422


def test_reimport_via_api_is_duplicate(client, small_dump_path):
    _import(client, small_dump_path)
    assert _import(client, small_dump_path)["duplicate"] is True
