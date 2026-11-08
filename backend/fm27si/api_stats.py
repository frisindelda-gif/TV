"""API do Statistical Scouting (/api/stats/...)."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fm27si.orm import (
    CompositeScoreDefinition,
    ImportRun,
    MetricDiscoveryProposal,
    Player,
    SavedSearch,
    SaveMetricAvailability,
    SaveStatField,
    Shortlist,
    ShortlistItem,
)
from fm27si.stats import repository
from fm27si.stats.catalog_data import POSITION_GROUPS
from fm27si.stats.composites import CompositeSpec
from fm27si.stats.data import SCOPES
from fm27si.stats.percentiles import MIN_MINUTES_OPTIONS
from fm27si.stats.queries import (
    Ctx,
    MarketRequest,
    SearchRequest,
    UniverseIn,
    catalog_payload,
    compare,
    history,
    market,
    overview,
    profile,
    run_search,
)
from fm27si.stats.service import approve, reject

STATUSES = ["AVAILABLE", "CALCULABLE", "PARTIAL", "UNAVAILABLE", "INVALID", "CUSTOM"]


class CompositeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    group_key: str
    components: list[dict]
    min_coverage: float = 0.6


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["filter", "identification", "market"] = "filter"
    definition: dict


class ShortlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ShortlistItemsIn(BaseModel):
    player_ids: list[int] = Field(min_length=1, max_length=500)
    source: str | None = None
    note: str | None = None


class ApproveIn(BaseModel):
    key: str | None = None
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    type: Literal["count", "value", "percentage"] | None = None
    direction: Literal["higher", "lower"] | None = None
    per90: bool | None = None
    groups: list[str] | None = None


class CompareIn(BaseModel):
    run_id: int | None = None
    career_id: int | None = None
    scope: Literal["club", "league"] = "club"
    player_ids: list[int] = Field(min_length=1, max_length=4)
    metrics: list[str] = Field(default_factory=list, max_length=40)
    composite_ids: list[int] = Field(default_factory=list, max_length=6)
    universe: UniverseIn = Field(default_factory=UniverseIn)


def _composite_out(c: CompositeScoreDefinition) -> dict[str, Any]:
    return {"id": c.id, "key": c.key, "name": c.name, "description": c.description, "builtin": c.builtin,
            "group_key": c.group_key, "group_label": POSITION_GROUPS.get(c.group_key, ("?",))[0],
            "components": c.components, "min_coverage": c.min_coverage, "updated_at": c.updated_at}


def register(app: FastAPI, get_session, latest_run) -> None:  # noqa: C901
    def run_of(s: Session, run_id: int | None, career_id: int | None) -> ImportRun:
        run = s.get(ImportRun, run_id) if run_id else latest_run(s, career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        return run

    def ctx_of(s, run_id, career_id, scope="club", uni: UniverseIn | None = None) -> Ctx:
        try:
            return Ctx(s, run_of(s, run_id, career_id), scope, uni)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    def composites(s: Session, ids: list[int] | None = None) -> list[CompositeScoreDefinition]:
        repository.sync_builtin(s)
        q = select(CompositeScoreDefinition).order_by(CompositeScoreDefinition.builtin.desc(), CompositeScoreDefinition.id)
        if ids is not None:
            q = q.where(CompositeScoreDefinition.id.in_(ids))
        return list(s.scalars(q))

    def guarded(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except (KeyError, ValueError, LookupError) as e:
            raise HTTPException(422, str(e).strip("'\"")) from e

    # --------------------------------------------------------------- catálogo
    @app.get("/api/stats/catalog")
    def get_catalog(s: Session = Depends(get_session)):
        cat, version, _ = repository.load_catalog(s)
        s.commit()
        return {"version": version, "scopes": SCOPES, "min_minutes_options": MIN_MINUTES_OPTIONS,
                **catalog_payload(cat)}

    # ------------------------------------------------------------ disponibilidade
    @app.get("/api/stats/availability")
    def availability(s: Session = Depends(get_session), run_id: int | None = None, career_id: int | None = None):
        run = run_of(s, run_id, career_id)
        cat, _v, _m = repository.load_catalog(s)
        rows = {a.metric_key: a for a in s.scalars(select(SaveMetricAvailability).where(SaveMetricAvailability.run_id == run.id))}
        if not rows:  # importação anterior a este módulo: calcular agora
            from fm27si.stats.service import process_run  # noqa: PLC0415

            process_run(s, run)
            rows = {a.metric_key: a for a in s.scalars(select(SaveMetricAvailability).where(SaveMetricAvailability.run_id == run.id))}
        s.commit()
        items = []
        for mid, m in cat.metrics.items():
            a = rows.get(mid)
            items.append({"metric": mid, "name": m.name, "category": m.category, "groups": cat.metric_groups.get(mid, []),
                          "status": a.status if a else "UNAVAILABLE", "reason": a.reason if a else "Por calcular.",
                          "players_with_value": a.players_with_value if a else 0,
                          "missing_fields": a.missing_fields if a else [], "builtin": m.builtin})
        counts = {st: sum(1 for i in items if i["status"] == st) for st in STATUSES}
        return {"run_id": run.id, "connector": run.connector, "catalog_size": len(cat.metrics), "counts": counts,
                "items": items}

    @app.get("/api/stats/fields")
    def fields(s: Session = Depends(get_session), run_id: int | None = None, career_id: int | None = None):
        run = run_of(s, run_id, career_id)
        rows = s.scalars(select(SaveStatField).where(SaveStatField.run_id == run.id).order_by(SaveStatField.raw_key)).all()
        return [{c: getattr(r, c) for c in ("raw_key", "data_source", "mapped_field", "confidence", "players_with_value",
                                             "min_value", "max_value", "mean_value", "integer_share")} for r in rows]

    # -------------------------------------------------------------- descoberta
    @app.get("/api/stats/proposals")
    def proposals(s: Session = Depends(get_session), status: str | None = None):
        q = select(MetricDiscoveryProposal).order_by(MetricDiscoveryProposal.id)
        if status:
            q = q.where(MetricDiscoveryProposal.status == status)
        return [{"id": p.id, "data_source": p.data_source, "raw_key": p.raw_key, "status": p.status,
                 "proposal": p.proposal, "sample": p.sample, "first_run_id": p.first_run_id,
                 "last_run_id": p.last_run_id, "created_metric_key": p.created_metric_key, "decided_at": p.decided_at}
                for p in s.scalars(q)]

    @app.post("/api/stats/proposals/{pid}/approve")
    def approve_proposal(pid: int, body: ApproveIn, s: Session = Depends(get_session)):
        p = s.get(MetricDiscoveryProposal, pid)
        if p is None:
            raise HTTPException(404, "Proposta não encontrada")
        if p.status != "pending":
            raise HTTPException(409, f"Proposta já {p.status}")
        try:
            row = approve(s, p, body.model_dump())
        except (ValueError, ValidationError) as e:
            s.rollback()
            raise HTTPException(422, str(e)) from e
        s.commit()
        return {"approved": pid, "metric_key": row.key}

    @app.post("/api/stats/proposals/{pid}/reject")
    def reject_proposal(pid: int, s: Session = Depends(get_session)):
        p = s.get(MetricDiscoveryProposal, pid)
        if p is None:
            raise HTTPException(404, "Proposta não encontrada")
        if p.status != "pending":
            raise HTTPException(409, f"Proposta já {p.status}")
        reject(s, p)
        s.commit()
        return {"rejected": pid}

    # --------------------------------------------------------------- consultas
    @app.get("/api/stats/overview")
    def get_overview(s: Session = Depends(get_session), run_id: int | None = None, career_id: int | None = None,
                     scope: Literal["club", "league"] = "club", min_minutes: int = 450):
        ctx = ctx_of(s, run_id, career_id, scope, UniverseIn(min_minutes=min_minutes))
        if not ctx.availability():
            from fm27si.stats.service import process_run  # noqa: PLC0415

            process_run(s, ctx.run)
            ctx._avail = None
        out = guarded(overview, ctx, composites(s, None))
        s.commit()
        return out

    @app.post("/api/stats/search")
    def search(req: SearchRequest, s: Session = Depends(get_session)):
        ctx = ctx_of(s, req.run_id, req.career_id, req.scope, req.universe)
        out = guarded(run_search, ctx, req)
        s.commit()
        return out

    @app.post("/api/stats/search/export")
    def export_search(req: SearchRequest, s: Session = Depends(get_session)):
        ctx = ctx_of(s, req.run_id, req.career_id, req.scope, req.universe)
        req = req.model_copy(update={"limit": 1000, "offset": 0})
        out = guarded(run_search, ctx, req)
        return _csv(out["items"], req.columns, ctx)

    @app.get("/api/stats/percentile-analysis")
    def percentile_analysis(s: Session = Depends(get_session), metric: str = Query(...), group: str | None = None,
                            position: str | None = None, competition: str | None = None, run_id: int | None = None,
                            career_id: int | None = None, scope: Literal["club", "league"] = "club",
                            universe_competition: Literal["same", "all"] = "same",
                            position_level: Literal["group", "position", "all"] = "group",
                            min_minutes: int = 450, min_sample: int = 10, shortlist_id: int | None = None,
                            player_id: int | None = None):
        import numpy as np  # noqa: PLC0415

        uni = UniverseIn(competition=universe_competition, position_level=position_level, min_minutes=min_minutes,
                         min_sample=min_sample, shortlist_id=shortlist_id)
        ctx = ctx_of(s, run_id, career_id, scope, uni)
        try:
            m, _view = ctx.cat.parse_view(metric)
            res = ctx.pct(metric)
        except KeyError as e:
            raise HTTPException(422, str(e).strip("'")) from e
        rd = ctx.rd
        sel = res.eligible.copy()
        if group:
            sel &= np.array([g == group for g in rd.groups])
        if position:
            sel &= np.array([p == position for p in rd.positions])
        if competition:
            sel &= np.array([(c or "Competição não identificada") == competition for c in rd.competitions])
        vals = res.values[sel]
        vals = vals[~np.isnan(vals)]
        hist = []
        if len(vals):
            counts, edges = np.histogram(vals, bins=min(20, max(5, len(vals) // 5)))
            hist = [{"from": float(edges[i]), "to": float(edges[i + 1]), "players": int(c)} for i, c in enumerate(counts)]
        parts = sorted({p for p in res.partition[sel] if p is not None})
        top_idx = [int(i) for i in np.nonzero(sel)[0]]
        top_idx.sort(key=lambda i: (np.isnan(res.percentile[i]), -np.nan_to_num(res.percentile[i])))
        player = None
        if player_id is not None:
            i = rd.index_of_player(player_id)
            if i is not None:
                from fm27si.stats.percentiles import Universe  # noqa: PLC0415

                def p_in(u):
                    r = ctx.pct(metric, u)
                    st = r.stats_for(i)
                    return {"universe": u.describe(), "percentile": r.percentile[i] if not np.isnan(r.percentile[i]) else None,
                            "rank": None if np.isnan(r.rank[i]) else int(r.rank[i]), "of": int(r.universe_size[i]),
                            "mean": st["mean"] if st else None}
                base = ctx.universe
                player = {
                    "name": rd.names[i], "value": None if np.isnan(res.values[i]) else float(res.values[i]),
                    "position": p_in(Universe("same", "group", base.min_minutes, base.min_sample)),
                    "competition": p_in(Universe("same", "all", base.min_minutes, base.min_sample)),
                    "population": p_in(base) if base.population is not None else None,
                }
        s.commit()
        return {"metric": metric, "label": ctx.cat.view_label(metric), "unit": ctx.cat.view_unit(metric),
                "direction": m.direction, "universe": ctx.universe.describe(), "histogram": hist,
                "partitions": [{"key": p, **res.partitions[p]} for p in parts],
                "top": [{**_row(ctx, i), "value": float(res.values[i]) if not np.isnan(res.values[i]) else None,
                         "percentile": None if np.isnan(res.percentile[i]) else round(float(res.percentile[i]), 1),
                         "rank": None if np.isnan(res.rank[i]) else int(res.rank[i])} for i in top_idx[:50]],
                "player": player}

    @app.post("/api/stats/compare")
    def do_compare(body: CompareIn, s: Session = Depends(get_session)):
        ctx = ctx_of(s, body.run_id, body.career_id, body.scope, body.universe)
        keys = body.metrics or ["minutes", "goals", "goals@p90", "assists@p90", "pass_pct", "progressive_passes@p90",
                                "tackles_won@p90", "interceptions@p90", "aerial_duel_pct", "dribbles_completed@p90"]
        out = guarded(compare, ctx, body.player_ids, keys, composites(s, body.composite_ids or None)
                      if body.composite_ids else composites(s, None))
        s.commit()
        return out

    @app.get("/api/stats/players/{player_id}/profile")
    def player_profile(player_id: int, s: Session = Depends(get_session), run_id: int | None = None,
                       scope: Literal["club", "league"] = "club", min_minutes: int = 450):
        from fm27si.orm import PlayerSnapshot  # noqa: PLC0415

        if s.get(Player, player_id) is None:
            raise HTTPException(404, "Jogador não encontrado")
        if run_id is None:
            run_id = s.scalar(select(func.max(PlayerSnapshot.run_id)).where(PlayerSnapshot.player_id == player_id))
        ctx = ctx_of(s, run_id, None, scope, UniverseIn(min_minutes=min_minutes))
        if not ctx.availability():
            from fm27si.stats.service import process_run  # noqa: PLC0415

            process_run(s, ctx.run)
            ctx._avail = None
        out = guarded(profile, ctx, player_id, composites(s, None))
        s.commit()
        if out is None:
            return {"player": None, "reason": "Sem estatísticas de jogo para este jogador nesta importação "
                                              "(a leitura da memória não inclui estatísticas)."}
        return out

    @app.get("/api/stats/players/{player_id}/history")
    def player_history(player_id: int, s: Session = Depends(get_session), metrics: list[str] = Query(default=[]),
                       scope: Literal["club", "league"] = "club"):
        keys = metrics or ["goals@p90", "assists@p90", "pass_pct", "tackles_won@p90", "interceptions@p90"]
        out = guarded(history, s, player_id, keys, scope)
        s.commit()
        return out

    @app.post("/api/stats/market")
    def market_ops(req: MarketRequest, s: Session = Depends(get_session)):
        ctx = ctx_of(s, req.run_id, req.career_id, req.scope, req.universe)
        out = guarded(market, ctx, req)
        s.commit()
        return out

    # -------------------------------------------------------- composite scores
    @app.get("/api/stats/composites")
    def list_composites(s: Session = Depends(get_session)):
        out = [_composite_out(c) for c in composites(s, None)]
        s.commit()
        return out

    def _validated(body: CompositeIn, s: Session) -> CompositeSpec:
        cat, _v, _m = repository.load_catalog(s)
        try:
            spec = CompositeSpec(**body.model_dump())
            spec.validate_against(cat)
        except (ValidationError, ValueError, KeyError) as e:
            raise HTTPException(422, str(e).strip("'")) from e
        return spec

    @app.post("/api/stats/composites")
    def create_composite(body: CompositeIn, s: Session = Depends(get_session)):
        spec = _validated(body, s)
        now = datetime.now()
        c = CompositeScoreDefinition(key=f"custom_{now.strftime('%Y%m%d%H%M%S%f')}", name=spec.name,
                                     description=spec.description, builtin=False, group_key=spec.group_key,
                                     components=[x.model_dump() for x in spec.components],
                                     min_coverage=spec.min_coverage, created_at=now, updated_at=now)
        s.add(c)
        s.commit()
        return _composite_out(c)

    @app.put("/api/stats/composites/{cid}")
    def update_composite(cid: int, body: CompositeIn, s: Session = Depends(get_session)):
        c = s.get(CompositeScoreDefinition, cid)
        if c is None:
            raise HTTPException(404, "Modelo não encontrado")
        if c.builtin:
            raise HTTPException(409, "Os modelos iniciais não podem ser alterados. Duplique para editar.")
        spec = _validated(body, s)
        c.name, c.description, c.group_key = spec.name, spec.description, spec.group_key
        c.components, c.min_coverage, c.updated_at = [x.model_dump() for x in spec.components], spec.min_coverage, datetime.now()
        s.commit()
        return _composite_out(c)

    @app.post("/api/stats/composites/{cid}/duplicate")
    def duplicate_composite(cid: int, s: Session = Depends(get_session)):
        c = s.get(CompositeScoreDefinition, cid)
        if c is None:
            raise HTTPException(404, "Modelo não encontrado")
        return create_composite(CompositeIn(name=f"{c.name} (cópia)", description=None if c.builtin else c.description,
                                            group_key=c.group_key, components=c.components, min_coverage=c.min_coverage), s)

    @app.delete("/api/stats/composites/{cid}")
    def delete_composite(cid: int, s: Session = Depends(get_session)):
        c = s.get(CompositeScoreDefinition, cid)
        if c is None:
            raise HTTPException(404, "Modelo não encontrado")
        if c.builtin:
            raise HTTPException(409, "Os modelos iniciais não podem ser apagados.")
        s.delete(c)
        s.commit()
        return {"deleted": cid}

    # ------------------------------------------------------- pesquisas guardadas
    @app.get("/api/stats/searches")
    def list_searches(s: Session = Depends(get_session), kind: str | None = None):
        q = select(SavedSearch).order_by(SavedSearch.id.desc())
        if kind:
            q = q.where(SavedSearch.kind == kind)
        return [{"id": x.id, "name": x.name, "kind": x.kind, "definition": x.definition, "created_at": x.created_at}
                for x in s.scalars(q)]

    @app.post("/api/stats/searches")
    def save_search(body: SavedSearchIn, s: Session = Depends(get_session)):
        try:
            (MarketRequest if body.kind == "market" else SearchRequest).model_validate(body.definition)
        except ValidationError as e:
            raise HTTPException(422, str(e)) from e
        x = SavedSearch(name=body.name, kind=body.kind, definition=body.definition, created_at=datetime.now())
        s.add(x)
        s.commit()
        return {"id": x.id, "name": x.name, "kind": x.kind, "definition": x.definition, "created_at": x.created_at}

    @app.delete("/api/stats/searches/{sid}")
    def delete_search(sid: int, s: Session = Depends(get_session)):
        x = s.get(SavedSearch, sid)
        if x is None:
            raise HTTPException(404, "Pesquisa não encontrada")
        s.delete(x)
        s.commit()
        return {"deleted": sid}

    # --------------------------------------------------------------- shortlists
    @app.get("/api/stats/shortlists")
    def list_shortlists(s: Session = Depends(get_session)):
        rows = s.execute(select(Shortlist, func.count(ShortlistItem.id)).outerjoin(ShortlistItem)
                         .group_by(Shortlist.id).order_by(Shortlist.id)).all()
        return [{"id": sl.id, "name": sl.name, "players": n, "created_at": sl.created_at} for sl, n in rows]

    @app.post("/api/stats/shortlists")
    def create_shortlist(body: ShortlistIn, s: Session = Depends(get_session)):
        sl = Shortlist(name=body.name, created_at=datetime.now())
        s.add(sl)
        s.commit()
        return {"id": sl.id, "name": sl.name, "players": 0, "created_at": sl.created_at}

    @app.get("/api/stats/shortlists/{sid}")
    def get_shortlist(sid: int, s: Session = Depends(get_session), career_id: int | None = None):
        from fm27si.orm import PlayerSnapshot  # noqa: PLC0415

        sl = s.get(Shortlist, sid)
        if sl is None:
            raise HTTPException(404, "Shortlist não encontrada")
        items = []
        for it in s.scalars(select(ShortlistItem).where(ShortlistItem.shortlist_id == sid).order_by(ShortlistItem.id)):
            snap = s.scalar(select(PlayerSnapshot).where(PlayerSnapshot.player_id == it.player_id)
                            .order_by(PlayerSnapshot.run_id.desc()).limit(1))
            items.append({"player_id": it.player_id, "name": snap.name if snap else "?", "age": snap.age if snap else None,
                          "club": snap.club_name if snap else None, "ca": snap.ca if snap else None,
                          "pa": snap.pa if snap else None, "market_value": snap.market_value if snap else None,
                          "note": it.note, "source": it.source, "added_at": it.added_at})
        return {"id": sl.id, "name": sl.name, "items": items}

    @app.post("/api/stats/shortlists/{sid}/items")
    def add_items(sid: int, body: ShortlistItemsIn, s: Session = Depends(get_session)):
        if s.get(Shortlist, sid) is None:
            raise HTTPException(404, "Shortlist não encontrada")
        existing = set(s.scalars(select(ShortlistItem.player_id).where(ShortlistItem.shortlist_id == sid)))
        added = 0
        for pid in dict.fromkeys(body.player_ids):
            if pid in existing or s.get(Player, pid) is None:
                continue
            s.add(ShortlistItem(shortlist_id=sid, player_id=pid, note=body.note, source=body.source, added_at=datetime.now()))
            added += 1
        s.commit()
        return {"added": added}

    @app.delete("/api/stats/shortlists/{sid}/items/{player_id}")
    def remove_item(sid: int, player_id: int, s: Session = Depends(get_session)):
        it = s.scalar(select(ShortlistItem).where(ShortlistItem.shortlist_id == sid, ShortlistItem.player_id == player_id))
        if it is None:
            raise HTTPException(404, "Jogador não está na shortlist")
        s.delete(it)
        s.commit()
        return {"removed": player_id}

    @app.delete("/api/stats/shortlists/{sid}")
    def delete_shortlist(sid: int, s: Session = Depends(get_session)):
        sl = s.get(Shortlist, sid)
        if sl is None:
            raise HTTPException(404, "Shortlist não encontrada")
        s.delete(sl)
        s.commit()
        return {"deleted": sid}

    @app.get("/api/stats/shortlists/{sid}/export")
    def export_shortlist(sid: int, s: Session = Depends(get_session)):
        data = get_shortlist(sid, s)
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["player_id", "nome", "idade", "clube", "CA", "PA", "valor", "nota", "origem", "adicionado"])
        for it in data["items"]:
            w.writerow([it["player_id"], it["name"], it["age"], it["club"], it["ca"], it["pa"], it["market_value"],
                        it["note"] or "", it["source"] or "", it["added_at"]])
        return _csv_response(buf, f"shortlist-{sid}.csv")


def _row(ctx: Ctx, i: int) -> dict[str, Any]:
    from fm27si.stats.queries import player_row  # noqa: PLC0415

    return player_row(ctx, i)


def _csv(items: list[dict], columns: list[str], ctx: Ctx) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    head = ["player_id", "nome", "idade", "clube", "competição", "posição", "minutos", "CA", "PA", "valor", "salário"]
    for k in columns:
        label = ctx.cat.view_label(k)
        head += [label, f"{label} — percentil", f"{label} — ranking", f"{label} — universo"]
    w.writerow(head)
    for it in items:
        row = [it["player_id"], it["name"], it["age"], it["club"], it["competition"], it["position"], it["minutes"],
               it["ca"], it["pa"], it["market_value"], it["wage"]]
        for k in columns:
            c = it["metrics"][k]
            row += [c["value"], c["percentile"], c["rank"], c["universe"]]
        w.writerow(["" if v is None else v for v in row])
    return _csv_response(buf, "pesquisa.csv")


def _csv_response(buf: io.StringIO, name: str) -> StreamingResponse:
    data = "﻿" + buf.getvalue()  # BOM para o Excel abrir em UTF-8
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
