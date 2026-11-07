"""API HTTP local (FastAPI). Corre só em 127.0.0.1; não há chamadas externas."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from fm27si import __version__
from fm27si.catalog import ATTRIBUTES, POSITION_KEYS
from fm27si.metrics import METRIC_BY_KEY, METRICS, MIN_MINUTES_FOR_PERCENTILE, POSITION_GROUPS, RADAR
from fm27si.config import fmsuperscout_dump_path
from fm27si.connectors.base import ConnectorError
from fm27si.db import Database
from fm27si.evaluation.service import active_model
from fm27si.importer import import_bundle
from fm27si.integrity import integrity_report
from fm27si.orm import (
    Career,
    ImportRun,
    Player,
    PlayerSnapshot,
    SeasonStatLine,
    SnapshotAttributes,
    SnapshotMetrics,
    PlayerEvaluation,
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
    ca_delta: int | None = None
    is_new: bool | None = None
    position_group: str | None = None
    minutes: float | None = None
    metric_key: str | None = None
    metric_value: float | None = None
    best_position: str | None = None
    best_position_score: float | None = None
    best_role: str | None = None
    best_role_score: float | None = None


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
        from fm27si.testdata import demo_bundles  # noqa: PLC0415

        return [
            _import_out(import_bundle(s, b, career_key="demo|dados-sinteticos"))
            for b in demo_bundles(players=players, seasons=seasons)
        ]

    @app.get("/api/metrics")
    def metrics_catalog():
        return {
            "metrics": [
                {"key": m.key, "label": m.label, "group": m.group, "unit": m.unit,
                 "higher_is_better": m.higher_is_better, "gk_only": m.gk_only, "outfield_only": m.outfield_only}
                for m in METRICS
            ],
            "position_groups": POSITION_GROUPS,
            "radar": RADAR,
            "min_minutes_for_percentile": MIN_MINUTES_FOR_PERCENTILE,
        }

    @app.get("/api/players", response_model=PlayerPage)
    def players(
        s: Session = Depends(get_session),
        career_id: int | None = None,
        run_id: int | None = None,
        q: str | None = Query(None, description="Pesquisa por nome"),
        club: str | None = None,
        position: str | None = None,
        position_group: str | None = Query(None, description="GK, CB, FB, DM, CM, WM, AM, ST"),
        min_ca: int | None = None,
        min_pa: int | None = None,
        min_age: int | None = None,
        max_age: int | None = None,
        max_value: int | None = None,
        nationality: str | None = None,
        expires_before: date | None = Query(None, description="Contrato termina até esta data"),
        quality: Literal["ok", "warning", "error"] | None = None,
        min_ca_delta: int | None = Query(None, description="CA ganho desde a importação anterior"),
        new_only: bool = Query(False, description="Só jogadores que apareceram nesta importação"),
        min_minutes: int | None = None,
        min_attr: list[str] = Query(default=[], description="key:valor, p.ex. pace:15"),
        min_metric: list[str] = Query(default=[], description="key:valor, p.ex. xg_90:0.3"),
        min_percentile: list[str] = Query(default=[], description="key:percentil, p.ex. xg_90:80"),
        sort: str = Query("ca", description="ca, pa, age, name, market_value, wage_weekly, contract_expires, club, ca_delta, pa_gap, minutes ou m:<métrica> / p:<métrica> (percentil)"),
        order: Literal["asc", "desc"] = "desc",
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        run = s.get(ImportRun, run_id) if run_id else _latest_run(s, career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        S, M, E = PlayerSnapshot, SnapshotMetrics, PlayerEvaluation
        model = active_model(s)
        stmt = (
            select(S, Player.unique_id, Player.nationalities, M.minutes, M.values,
                   E.best_position, E.best_position_score, E.best_role, E.best_role_score)
            .join(Player, Player.id == S.player_id)
            .outerjoin(M, M.snapshot_id == S.id)
            .outerjoin(E, (E.snapshot_id == S.id) & (E.model_id == model.id))
            .where(S.run_id == run.id)
        )
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
        if min_ca_delta is not None:
            stmt = stmt.where(S.ca_delta >= min_ca_delta)
        if new_only:
            stmt = stmt.where(S.is_new.is_(True))
        if position_group:
            if position_group not in POSITION_GROUPS:
                raise HTTPException(422, f"Grupo de posição inválido: {position_group}")
            stmt = stmt.where(S.position_group == position_group)
        if min_minutes is not None:
            stmt = stmt.where(M.minutes >= min_minutes)
        for spec in min_metric:
            key, val = _metric_spec(spec)
            stmt = stmt.where(func.json_extract(M.values, f"$.{key}") >= val)
        for spec in min_percentile:
            key, val = _metric_spec(spec)
            stmt = stmt.where(func.json_extract(M.percentiles, f"$.{key}") >= val)
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

        metric_key: str | None = None
        if sort.startswith(("m:", "p:")):
            metric_key = sort[2:]
            if metric_key not in METRIC_BY_KEY:
                raise HTTPException(422, f"Métrica desconhecida: {metric_key}")
            col = func.json_extract(M.values if sort[0] == "m" else M.percentiles, f"$.{metric_key}")
        else:
            cols = {
                "ca": S.ca, "pa": S.pa, "age": S.age, "name": S.name, "market_value": S.market_value,
                "wage_weekly": S.wage_weekly, "contract_expires": S.contract_expires, "club": S.club_name,
                "ca_delta": S.ca_delta, "pa_gap": S.pa - S.ca, "minutes": M.minutes,
                "best_position_score": E.best_position_score, "best_role_score": E.best_role_score,
            }
            if sort not in cols:
                raise HTTPException(422, f"Ordenação inválida: {sort}")
            col = cols[sort]
        if metric_key is None and (min_metric or min_percentile):
            metric_key = _metric_spec((min_metric or min_percentile)[0])[0]
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
                ca_delta=snap.ca_delta,
                is_new=snap.is_new,
                position_group=snap.position_group,
                minutes=minutes,
                metric_key=metric_key,
                metric_value=(values or {}).get(metric_key) if metric_key else None,
                best_position=bp,
                best_position_score=bps,
                best_role=br,
                best_role_score=brs,
            )
            for snap, uid, nats, minutes, values, bp, bps, br, brs in s.execute(stmt.limit(limit).offset(offset))
        ]
        return PlayerPage(run_id=run.id, total=total or 0, items=items)

    @app.get("/api/overview")
    def overview(career_id: int | None = None, run_id: int | None = None, s: Session = Depends(get_session)):
        """Painel da carreira: números gerais, distribuições, maiores subidas, novos regens, destaques."""
        run = s.get(ImportRun, run_id) if run_id else _latest_run(s, career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        S, M = PlayerSnapshot, SnapshotMetrics
        base = select(S).where(S.run_id == run.id)

        def count(*conds) -> int:
            return s.scalar(select(func.count()).select_from(S).where(S.run_id == run.id, *conds)) or 0

        def top(order_col, *conds, n: int = 8, with_metric: str | None = None):
            q = select(S, M.values, M.minutes).outerjoin(M, M.snapshot_id == S.id).where(S.run_id == run.id, *conds)
            rows = s.execute(q.order_by(order_col.desc().nulls_last(), S.id).limit(n)).all()
            return [
                {
                    "player_id": x.player_id, "name": x.name, "age": x.age, "club": x.club_name, "ca": x.ca, "pa": x.pa,
                    "ca_delta": x.ca_delta, "position_group": x.position_group,
                    "positions": list(x.natural_positions or []),
                    "metric": (vals or {}).get(with_metric) if with_metric else None, "minutes": mins,
                }
                for x, vals, mins in rows
            ]

        def histogram(col, width: int = 10):
            bucket = (func.cast(col / width, Integer) * width).label("b")
            rows = s.execute(
                select(bucket, func.count()).where(S.run_id == run.id, col.is_not(None)).group_by(bucket).order_by(bucket)
            ).all()
            return [{"from": int(b), "to": int(b) + width - 1, "players": n} for b, n in rows]

        groups = s.execute(
            select(S.position_group, func.count(), func.avg(S.ca), func.max(S.ca))
            .where(S.run_id == run.id).group_by(S.position_group)
        ).all()
        clubs = s.execute(
            select(S.club_name, func.count(), func.avg(S.ca), func.max(S.pa))
            .where(S.run_id == run.id, S.club_name.is_not(None))
            .group_by(S.club_name).order_by(func.avg(S.ca).desc()).limit(12)
        ).all()
        has_growth = count(S.ca_delta.is_not(None)) > 0
        has_metrics = (s.scalar(select(func.count()).select_from(M).join(S, S.id == M.snapshot_id).where(S.run_id == run.id)) or 0) > 0
        rating = func.json_extract(M.values, "$.average_rating")
        eligible = M.minutes >= MIN_MINUTES_FOR_PERCENTILE
        return {
            "run_id": run.id,
            "game_date": run.game_date,
            "season_label": run.season_label,
            "synthetic": run.synthetic,
            "kpis": {
                "players": count(),
                "avg_ca": round(s.scalar(select(func.avg(S.ca)).where(S.run_id == run.id)) or 0, 1),
                "elite": count(S.ca >= 150),
                "wonderkids": count(S.age <= 19, S.pa >= 150),
                "new_players": count(S.is_new.is_(True)),
                "new_regens": count(S.is_new.is_(True), S.age <= 17),
                "risers": count(S.ca_delta >= 5),
                "fallers": count(S.ca_delta <= -5),
                "with_stats": s.scalar(select(func.count()).select_from(M).join(S, S.id == M.snapshot_id).where(S.run_id == run.id)) or 0,
            },
            "has_growth": has_growth,
            "has_metrics": has_metrics,
            "ca_histogram": histogram(S.ca),
            "pa_histogram": histogram(S.pa),
            "position_groups": [
                {"group": g, "label": POSITION_GROUPS.get(g or "", "Sem posição"), "players": n,
                 "avg_ca": round(a or 0, 1), "max_ca": mx}
                for g, n, a, mx in groups
            ],
            "clubs": [{"name": n, "players": c, "avg_ca": round(a or 0, 1), "max_pa": mp} for n, c, a, mp in clubs],
            "top_risers": top(S.ca_delta, S.ca_delta > 0) if has_growth else [],
            "top_new_regens": top(S.pa, S.is_new.is_(True), S.age <= 18),
            "top_prospects": top(S.pa, S.age <= 21),
            "top_rated": top(rating, eligible, with_metric="average_rating") if has_metrics else [],
            "top_scorers": top(func.json_extract(M.values, "$.goals_90"), eligible, with_metric="goals_90") if has_metrics else [],
        }

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
            "growth": {
                "ca_delta": snap.ca_delta,
                "pa_delta": snap.pa_delta,
                "is_new": snap.is_new,
                "ca_since_first": (snap.ca - snaps[0].ca) if snap.ca is not None and snaps[0].ca is not None and len(snaps) > 1 else None,
            },
            "metrics": _metrics_block(s, snap),
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

    from fm27si.api_evaluation import register as register_evaluation  # noqa: PLC0415

    register_evaluation(app, get_session, _latest_run)
    _mount_frontend(app)
    return app


def _metrics_block(s: Session, snap: PlayerSnapshot) -> dict | None:
    m = s.get(SnapshotMetrics, snap.id)
    if m is None:
        return None
    peers = None
    if m.position_group:
        peers = s.scalar(
            select(func.count()).select_from(SnapshotMetrics).join(PlayerSnapshot, PlayerSnapshot.id == SnapshotMetrics.snapshot_id)
            .where(PlayerSnapshot.run_id == snap.run_id, SnapshotMetrics.position_group == m.position_group,
                   SnapshotMetrics.minutes >= MIN_MINUTES_FOR_PERCENTILE)
        )
    return {
        "position_group": m.position_group,
        "position_group_label": POSITION_GROUPS.get(m.position_group or ""),
        "minutes": m.minutes,
        "appearances": m.appearances,
        "values": m.values,
        "percentiles": m.percentiles,
        "peers": peers,
        "min_minutes": MIN_MINUTES_FOR_PERCENTILE,
        "enough_minutes": m.minutes >= MIN_MINUTES_FOR_PERCENTILE,
        "radar": list(RADAR.get(m.position_group or "", ())),
        "status": "derived",
    }


def _metric_spec(spec: str) -> tuple[str, float]:
    key, _, val = spec.partition(":")
    try:
        num = float(val)
    except ValueError:
        num = None
    if key not in METRIC_BY_KEY or num is None:
        raise HTTPException(422, f"Filtro de métrica inválido: {spec}")
    return key, num


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
