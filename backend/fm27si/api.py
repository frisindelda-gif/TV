"""API HTTP local (FastAPI). Corre só em 127.0.0.1; não há chamadas externas."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fm27si import __version__
from fm27si.catalog import ATTRIBUTES, POSITION_KEYS
from fm27si.config import fmsuperscout_dump_path
from fm27si.connectors.base import ConnectorError
from fm27si.db import Database
from fm27si.importer import import_bundle
from fm27si.integrity import integrity_report
from fm27si.orm import (
    Career,
    ImportRun,
    Player,
    PlayerSnapshot,
    SeasonStatLine,
    SnapshotAttributes,
    ValidationIssue,
)

# ------------------------------------------------------------------ esquemas de resposta


class RunOut(BaseModel):
    id: int
    career_id: int
    connector: str
    tool: str
    source_path: str | None
    source_sha256: str | None
    read_at: datetime
    imported_at: datetime
    game: str | None
    game_version: str | None
    game_version_supported: bool | None
    game_date: date | None
    game_date_status: str
    season_label: str | None
    managed_club: str | None
    currency: str | None
    synthetic: bool
    player_count: int
    source_player_count: int
    error_count: int
    warning_count: int
    unavailable_fields: list[str]
    warnings: list[str]

    model_config = {"from_attributes": True}


class CareerOut(BaseModel):
    id: int
    key: str
    label: str
    game: str | None
    manager_name: str | None
    runs: int
    latest_run_id: int | None


class PlayerRow(BaseModel):
    player_id: int
    unique_id: int | None
    name: str
    age: int | None
    ca: int | None
    pa: int | None
    club: str | None
    nationalities: list[str]
    positions: list[str]
    natural_positions: list[str]
    market_value: int | None
    wage_weekly: int | None
    contract_expires: date | None
    quality: str


class PlayerPage(BaseModel):
    run_id: int
    total: int
    items: list[PlayerRow]


class ImportSaveIn(BaseModel):
    path: str
    career_key: str | None = None


class ImportLiveIn(BaseModel):
    dump_path: str | None = None
    run_scanner: bool = False
    scanner_path: str | None = None
    career_key: str | None = None


class ImportOut(BaseModel):
    duplicate: bool
    created_players: int
    updated_players: int
    skipped: int
    run: RunOut
    warnings: list[str]


# ----------------------------------------------------------------------- aplicação


def create_app(db: Database | None = None, *, save_connector=None, live_connector=None) -> FastAPI:
    database = db or Database()
    app = FastAPI(title="FM27 Scouting Intelligence", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_session():
        yield from database.session()

    def _save_conn():
        if save_connector is not None:
            return save_connector
        from fm27si.connectors.save_fmsave import FmsaveSaveConnector  # noqa: PLC0415

        return FmsaveSaveConnector()

    def _live_conn():
        if live_connector is not None:
            return live_connector
        from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector  # noqa: PLC0415

        return FMSuperScoutLiveConnector()

    def _latest_run(s: Session, career_id: int | None) -> ImportRun:
        q = select(ImportRun).order_by(ImportRun.id.desc())
        if career_id is not None:
            q = q.where(ImportRun.career_id == career_id)
        run = s.scalar(q)
        if run is None:
            raise HTTPException(404, "Nenhuma importação encontrada")
        return run

    def _import_out(res) -> ImportOut:
        return ImportOut(
            duplicate=res.duplicate,
            created_players=res.created_players,
            updated_players=res.updated_players,
            skipped=res.skipped,
            run=RunOut.model_validate(res.run),
            warnings=res.warnings[:200],
        )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/attributes")
    def attributes():
        return [{"key": a.key, "label": a.label, "category": a.category} for a in ATTRIBUTES.values()]

    # ------------------------------------------------------------- importação
    @app.post("/api/import/save", response_model=ImportOut)
    def import_save(body: ImportSaveIn, s: Session = Depends(get_session)):
        try:
            bundle = _save_conn().load(Path(body.path))
        except ConnectorError as e:
            raise HTTPException(422, str(e)) from e
        return _import_out(import_bundle(s, bundle, career_key=body.career_key))

    @app.post("/api/import/live", response_model=ImportOut)
    def import_live(body: ImportLiveIn, s: Session = Depends(get_session)):
        from fm27si.connectors.live_fmsuperscout import run_scanner, scanner_path_from_env  # noqa: PLC0415

        try:
            if body.run_scanner:
                exe = Path(body.scanner_path) if body.scanner_path else scanner_path_from_env()
                if exe is None:
                    raise ConnectorError("Indique scanner_path ou defina FM27SI_FMSS_SCANNER")
                run_scanner(exe)
            bundle = _live_conn().load(Path(body.dump_path) if body.dump_path else fmsuperscout_dump_path())
        except ConnectorError as e:
            raise HTTPException(422, str(e)) from e
        return _import_out(import_bundle(s, bundle, career_key=body.career_key))

    # ---------------------------------------------------------------- consulta
    @app.get("/api/careers", response_model=list[CareerOut])
    def careers(s: Session = Depends(get_session)):
        rows = s.execute(
            select(Career, func.count(ImportRun.id), func.max(ImportRun.id))
            .outerjoin(ImportRun, ImportRun.career_id == Career.id)
            .group_by(Career.id)
        ).all()
        return [
            CareerOut(id=c.id, key=c.key, label=c.label, game=c.game, manager_name=c.manager_name, runs=n, latest_run_id=last)
            for c, n, last in rows
        ]

    @app.get("/api/careers/{career_id}/runs", response_model=list[RunOut])
    def runs(career_id: int, s: Session = Depends(get_session)):
        return s.scalars(select(ImportRun).where(ImportRun.career_id == career_id).order_by(ImportRun.id)).all()

    @app.get("/api/runs/{run_id}/integrity")
    def run_integrity(run_id: int, s: Session = Depends(get_session)):
        if s.get(ImportRun, run_id) is None:
            raise HTTPException(404, "Importação não encontrada")
        return integrity_report(s, run_id)

    @app.get("/api/runs/{run_id}", response_model=RunOut)
    def run_detail(run_id: int, s: Session = Depends(get_session)):
        run = s.get(ImportRun, run_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        return run

    @app.get("/api/filters")
    def filter_options(career_id: int | None = None, run_id: int | None = None, s: Session = Depends(get_session)):
        """Valores existentes na importação (clubes, nacionalidades, posições) para os filtros da UI."""
        run = s.get(ImportRun, run_id) if run_id else _latest_run(s, career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        S = PlayerSnapshot
        clubs = s.execute(
            select(S.club_name, func.count()).where(S.run_id == run.id, S.club_name.is_not(None))
            .group_by(S.club_name).order_by(S.club_name)
        ).all()
        nats: dict[str, int] = defaultdict(int)
        for (lst,) in s.execute(select(Player.nationalities).join(S, S.player_id == Player.id).where(S.run_id == run.id)):
            for n in lst or []:
                nats[n] += 1
        return {
            "run_id": run.id,
            "game_date": run.game_date,
            "clubs": [{"name": n, "players": c} for n, c in clubs],
            "nationalities": [{"name": n, "players": c} for n, c in sorted(nats.items())],
            "positions": list(POSITION_KEYS),
        }

    @app.post("/api/import/demo", response_model=list[ImportOut])
    def import_demo(players: int = Query(400, ge=10, le=20000), seasons: int = Query(3, ge=1, le=5),
                    s: Session = Depends(get_session)):
        """Cria uma carreira de DEMONSTRAÇÃO com dados sintéticos (marcados como tal)."""
        import tempfile  # noqa: PLC0415

        from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector  # noqa: PLC0415
        from fm27si.testdata import write_test_career  # noqa: PLC0415

        out = []
        with tempfile.TemporaryDirectory(prefix="fm27si-demo-") as tmp:
            for p in write_test_career(Path(tmp), players=players, seasons=seasons):
                bundle = FMSuperScoutLiveConnector().load(p)
                out.append(_import_out(import_bundle(s, bundle, career_key="demo|dados-sinteticos")))
        return out

    @app.get("/api/players", response_model=PlayerPage)
    def players(
        s: Session = Depends(get_session),
        career_id: int | None = None,
        run_id: int | None = None,
        q: str | None = Query(None, description="Pesquisa por nome"),
        club: str | None = None,
        position: str | None = None,
        min_ca: int | None = None,
        min_pa: int | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        max_value: int | None = None,
        nationality: str | None = None,
        expires_before: date | None = Query(None, description="Contrato termina até esta data"),
        quality: Literal["ok", "warning", "error"] | None = None,
        min_attr: list[str] = Query(default=[], description="key:valor, p.ex. pace:15"),
        sort: Literal["ca", "pa", "age", "name", "market_value", "wage_weekly", "contract_expires", "club"] = "ca",
        order: Literal["asc", "desc"] = "desc",
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        run = s.get(ImportRun, run_id) if run_id else _latest_run(s, career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        S = PlayerSnapshot
        stmt = select(S, Player.unique_id, Player.nationalities).join(Player, Player.id == S.player_id).where(S.run_id == run.id)
        if q:
            stmt = stmt.where(S.name.ilike(f"%{q}%"))
        if club:
            stmt = stmt.where(S.club_name.ilike(f"%{club}%"))
        if min_ca is not None:
            stmt = stmt.where(S.ca >= min_ca)
        if min_pa is not None:
            stmt = stmt.where(S.pa >= min_pa)
        if min_age is not None:
            stmt = stmt.where(S.age >= min_age)
        if max_age is not None:
            stmt = stmt.where(S.age <= max_age)
        if max_value is not None:
            stmt = stmt.where(S.market_value <= max_value)
        if nationality:
            stmt = stmt.where(func.json(Player.nationalities).ilike(f"%{nationality}%"))
        if expires_before is not None:
            stmt = stmt.where(S.contract_expires <= expires_before)
        if quality:
            stmt = stmt.where(S.quality == quality)
        if min_attr:
            A = SnapshotAttributes
            stmt = stmt.join(A, A.snapshot_id == S.id)
            for spec in min_attr:
                key, _, val = spec.partition(":")
                if key not in ATTRIBUTES or not val.lstrip("-").isdigit():
                    raise HTTPException(422, f"Filtro de atributo inválido: {spec}")
                stmt = stmt.where(getattr(A, key) >= int(val))
        if position:
            pos = position.upper()
            # natural_positions/accomplished_positions são JSON arrays
            stmt = stmt.where(
                func.instr(func.coalesce(func.json(S.natural_positions), ""), f'"{pos}"')
                + func.instr(func.coalesce(func.json(S.accomplished_positions), ""), f'"{pos}"')
                > 0
            )
        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        col = {
            "ca": S.ca, "pa": S.pa, "age": S.age, "name": S.name, "market_value": S.market_value,
            "wage_weekly": S.wage_weekly, "contract_expires": S.contract_expires, "club": S.club_name,
        }[sort]
        stmt = stmt.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last(), S.id)
        items = [
            PlayerRow(
                player_id=snap.player_id,
                unique_id=uid,
                name=snap.name,
                age=snap.age,
                ca=snap.ca,
                pa=snap.pa,
                club=snap.club_name,
                nationalities=list(nats or []),
                positions=list(snap.natural_positions or []) + list(snap.accomplished_positions or []),
                natural_positions=list(snap.natural_positions or []),
                market_value=snap.market_value,
                wage_weekly=snap.wage_weekly,
                contract_expires=snap.contract_expires,
                quality=snap.quality,
            )
            for snap, uid, nats in s.execute(stmt.limit(limit).offset(offset))
        ]
        return PlayerPage(run_id=run.id, total=total or 0, items=items)

    @app.get("/api/players/{player_id}")
    def player_profile(player_id: int, run_id: int | None = None, s: Session = Depends(get_session)):
        player = s.get(Player, player_id)
        if player is None:
            raise HTTPException(404, "Jogador não encontrado")
        snaps = s.scalars(select(PlayerSnapshot).where(PlayerSnapshot.player_id == player_id).order_by(PlayerSnapshot.run_id)).all()
        snap = next((x for x in snaps if x.run_id == run_id), None) if run_id else (snaps[-1] if snaps else None)
        if snap is None:
            raise HTTPException(404, "Sem snapshot para esta importação")
        run = s.get(ImportRun, snap.run_id)

        grouped: dict[str, dict[str, int]] = defaultdict(dict)
        arow = s.get(SnapshotAttributes, snap.id)
        if arow is not None:
            for key, adef in ATTRIBUTES.items():
                v = getattr(arow, key)
                if v is not None:
                    grouped[adef.category][key] = v
        stats = s.scalars(select(SeasonStatLine).where(SeasonStatLine.snapshot_id == snap.id)).all()
        issues = s.scalars(select(ValidationIssue).where(ValidationIssue.snapshot_id == snap.id)).all()
        runs_by_id = {r.id: r for r in s.scalars(select(ImportRun).where(ImportRun.id.in_([x.run_id for x in snaps])))}

        return {
            "player_id": player.id,
            "unique_id": player.unique_id,
            "identity_key": player.identity_key,
            "name": snap.name,
            "birth_date": player.birth_date,
            "birth_year": player.birth_year,
            "gender": player.gender,
            "nationalities": player.nationalities,
            "age": snap.age,
            "height_cm": snap.height_cm,
            "foot": {"left": snap.foot_left, "right": snap.foot_right, "preferred": snap.preferred_foot},
            "ability": {"ca": snap.ca, "pa": snap.pa, "pa_range_code": snap.pa_range_code},
            "reputation": {"home": snap.reputation_home, "current": snap.reputation_current, "world": snap.reputation_world},
            "club": {"id": snap.club_id, "name": snap.club_name, "division": snap.division},
            "contract": snap.contract,
            "market_value": snap.market_value,
            "positions": {
                "ratings": snap.positions,
                "natural": snap.natural_positions,
                "accomplished": snap.accomplished_positions,
            },
            "roles": snap.roles,
            "traits": snap.traits,
            "attributes": grouped,
            "season_stats": [
                {c: getattr(st, c) for c in (
                    "season", "competition_kind", "club_name", "starts", "sub_appearances", "minutes", "goals",
                    "assists", "average_rating", "player_of_the_match", "expected_goals", "expected_assists",
                    "yellow_cards", "red_cards", "clean_sheets", "extra")}
                for st in stats
            ],
            "quality": snap.quality,
            "issues": [{"severity": i.severity, "field": i.field, "code": i.code, "message": i.message, "value": i.value} for i in issues],
            "field_status": snap.field_status,
            "extra": snap.extra,
            "provenance": {
                "run_id": run.id,
                "connector": run.connector,
                "tool": run.tool,
                "source_path": run.source_path,
                "source_sha256": run.source_sha256,
                "read_at": run.read_at,
                "imported_at": run.imported_at,
                "game_date": run.game_date,
                "game_date_status": run.game_date_status,
                "game_version": run.game_version,
                "synthetic": run.synthetic,
                "currency": run.currency,
            },
            "unavailable_fields": run.unavailable_fields,
            "history": [
                {
                    "run_id": x.run_id,
                    "connector": runs_by_id[x.run_id].connector,
                    "game_date": runs_by_id[x.run_id].game_date,
                    "read_at": runs_by_id[x.run_id].read_at,
                    "ca": x.ca,
                    "pa": x.pa,
                    "market_value": x.market_value,
                    "club": x.club_name,
                }
                for x in snaps
            ],
        }

    _mount_frontend(app)
    return app


def _frontend_dist() -> Path | None:
    import os  # noqa: PLC0415

    env = os.environ.get("FM27SI_FRONTEND_DIST")
    cand = Path(env) if env else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return cand if (cand / "index.html").is_file() else None


def _mount_frontend(app: FastAPI) -> None:
    """Serve a app compilada (frontend/dist) na mesma origem: um só processo para arrancar."""
    from fastapi.responses import FileResponse  # noqa: PLC0415
    from fastapi.staticfiles import StaticFiles  # noqa: PLC0415

    dist = _frontend_dist()
    if dist is None:
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Endpoint não encontrado")
        f = (dist / full_path).resolve()
        if full_path and f.is_file() and dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html")  # rotas do React


app = None  # criado por fm27si.cli serve / uvicorn --factory fm27si.api:create_app
