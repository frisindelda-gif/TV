"""Endpoints usados pela interface: demonstração, opções de filtro, filtros extra, app servida."""

from fastapi.testclient import TestClient

from fm27si.api import create_app


def test_demo_creates_synthetic_career(client):
    r = client.post("/api/import/demo", params={"players": 60, "seasons": 2})
    assert r.status_code == 200, r.text
    runs = r.json()
    assert len(runs) == 2 and all(x["run"]["synthetic"] for x in runs)
    careers = client.get("/api/careers").json()
    assert careers[0]["key"] == "demo|dados-sinteticos" and careers[0]["runs"] == 2
    run = client.get(f"/api/runs/{runs[-1]['run']['id']}").json()
    assert run["synthetic"] is True
    assert client.get("/api/runs/999").status_code == 404


def test_filter_options_and_extra_filters(client):
    client.post("/api/import/demo", params={"players": 200, "seasons": 1})
    opts = client.get("/api/filters").json()
    assert opts["clubs"] and opts["nationalities"] and "GK" in opts["positions"]
    assert sum(c["players"] for c in opts["clubs"]) == 200

    club = opts["clubs"][0]["name"]
    rows = client.get("/api/players", params={"club": club, "limit": 500}).json()
    assert rows["total"] == opts["clubs"][0]["players"]

    nat = opts["nationalities"][0]["name"]
    rows = client.get("/api/players", params={"nationality": nat, "limit": 500}).json()["items"]
    assert rows and all(nat in r["nationalities"] for r in rows)

    rows = client.get("/api/players", params={"min_age": 25, "max_age": 28, "limit": 500}).json()["items"]
    assert rows and all(25 <= r["age"] <= 28 for r in rows)

    rows = client.get("/api/players", params={"max_value": 500000, "limit": 500}).json()["items"]
    assert all(r["market_value"] is not None and r["market_value"] <= 500000 for r in rows)

    rows = client.get("/api/players", params={"expires_before": "2027-06-30", "limit": 500}).json()["items"]
    assert rows and all(r["contract_expires"] <= "2027-06-30" for r in rows)

    for sort in ("wage_weekly", "contract_expires", "club"):
        assert client.get("/api/players", params={"sort": sort, "order": "asc"}).status_code == 200


def test_spa_is_served_when_built(db, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "a.js").write_text("console.log(1)")
    monkeypatch.setenv("FM27SI_FRONTEND_DIST", str(dist))
    c = TestClient(create_app(db))
    assert c.get("/").text == "<html>app</html>"
    assert c.get("/jogador/5").text == "<html>app</html>"  # rota do React
    assert c.get("/assets/a.js").text == "console.log(1)"
    assert c.get("/api/nao-existe").status_code == 404
    assert c.get("/api/health").json()["status"] == "ok"
    (tmp_path / "segredo.txt").write_text("nao servir")
    assert "nao servir" not in c.get("/%2e%2e/segredo.txt").text  # sem path traversal para fora de dist
