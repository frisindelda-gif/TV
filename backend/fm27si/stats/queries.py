"""Serviços de consulta: StatisticalRankingService, AdvancedPlayerFilterService,
PlayerComparisonService, PlayerStatisticalProfileService, Market Opportunities, Overview.

Tudo é executado no backend, vetorizado, sobre os dados em cache da importação. O pedido de
pesquisa é um JSON validado (``SearchRequest``): pode ser construído pela interface ou, no
futuro, por um assistente de linguagem natural.
"""

from __future__ import annotations

import math
from typing import Any, Literal, Union

import numpy as np
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fm27si.orm import CompositeScoreDefinition, ImportRun, PlayerSnapshot, SaveMetricAvailability, ShortlistItem
from fm27si.stats import repository
from fm27si.stats.catalog import CATEGORY_LABEL, PROFILE_TABS, Catalog
from fm27si.stats.catalog_data import POSITION_GROUPS
from fm27si.stats.composites import CompositeSpec
from fm27si.stats.composites import compute as compute_composite
from fm27si.stats.data import POS_TO_GROUP, SCOPES, RunStats
from fm27si.stats.mapping import PROFILE_LABEL
from fm27si.stats.percentiles import UNKNOWN_COMPETITION, PercentileResult, Universe

# ------------------------------------------------------------------ pedidos


class UniverseIn(BaseModel):
    competition: Literal["same", "all"] = "same"
    position_level: Literal["group", "position", "all"] = "group"
    min_minutes: int = Field(450, ge=0, le=6000)
    min_sample: int = Field(10, ge=3, le=1000)
    shortlist_id: int | None = None


class BaseFilters(BaseModel):
    group: str | None = None
    position: str | None = None
    competition: str | None = None
    club: str | None = None
    nationality: str | None = None
    foot: Literal["left", "right", "both"] | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_minutes: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    max_wage: float | None = None
    contract_within_days: int | None = Field(None, description="Contrato termina nos próximos N dias")
    listed: bool | None = None
    loan_listed: bool | None = None
    min_potential_gap: int | None = Field(None, description="PA − CA mínimo")
    name: str | None = None

    @model_validator(mode="after")
    def _known(self) -> BaseFilters:
        if self.group and self.group not in POSITION_GROUPS:
            raise ValueError(f"grupo desconhecido: {self.group}")
        if self.position and self.position not in POS_TO_GROUP:
            raise ValueError(f"posição desconhecida: {self.position}")
        return self


class Condition(BaseModel):
    metric: str
    kind: Literal["value", "percentile"] = "value"
    min: float | None = None
    max: float | None = None


class ConditionGroup(BaseModel):
    op: Literal["and", "or"] = "and"
    conditions: list[Union[Condition, "ConditionGroup"]] = Field(default_factory=list)


ConditionGroup.model_rebuild()


class SortSpec(BaseModel):
    by: Literal["value", "percentile", "composite", "age", "market_value", "wage", "minutes", "name", "ca", "pa"] = "value"
    metric: str | None = None
    composite_id: int | None = None
    order: Literal["asc", "desc"] = "desc"


class SearchRequest(BaseModel):
    run_id: int | None = None
    career_id: int | None = None
    scope: Literal["club", "league"] = "club"
    filters: BaseFilters = Field(default_factory=BaseFilters)
    conditions: ConditionGroup | None = None
    universe: UniverseIn = Field(default_factory=UniverseIn)
    sort: SortSpec = Field(default_factory=SortSpec)
    columns: list[str] = Field(default_factory=list, max_length=20)
    composite_ids: list[int] = Field(default_factory=list, max_length=6)
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


# ------------------------------------------------------------------ contexto


class Ctx:
    """Uma importação + catálogo + universo: tudo o que uma consulta precisa."""

    def __init__(self, s: Session, run: ImportRun, scope: str, uni: UniverseIn | None = None):
        self.s, self.run = s, run
        self.rd, self.cat, self.version = repository.run_stats(s, run, scope)
        uni = uni or UniverseIn()
        population, label = None, None
        if uni.shortlist_id is not None:
            pids = set(s.scalars(select(ShortlistItem.player_id).where(ShortlistItem.shortlist_id == uni.shortlist_id)))
            population = tuple(int(x) for x in self.rd.snapshot_ids[np.isin(self.rd.player_ids, list(pids))])
            label = f"shortlist #{uni.shortlist_id}"
        self.universe = Universe(uni.competition, uni.position_level, uni.min_minutes, uni.min_sample, population, label)
        self._avail: dict[str, SaveMetricAvailability] | None = None

    def pct(self, key: str, u: Universe | None = None) -> PercentileResult:
        return repository.percentiles(self.rd, self.cat, self.version, key, u or self.universe)

    def availability(self) -> dict[str, SaveMetricAvailability]:
        if self._avail is None:
            self._avail = {a.metric_key: a for a in self.s.scalars(
                select(SaveMetricAvailability).where(SaveMetricAvailability.run_id == self.run.id))}
        return self._avail

    def composite(self, row: CompositeScoreDefinition):
        spec = CompositeSpec(name=row.name, group_key=row.group_key, components=row.components, min_coverage=row.min_coverage)
        return compute_composite(self.rd, spec, self.pct, self.universe)


def _f(v) -> float | None:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), 4)


def base_mask(rd: RunStats, f: BaseFilters) -> np.ndarray:
    m = np.ones(rd.n, dtype=bool)
    if f.group:
        m &= np.array([g == f.group for g in rd.groups], dtype=bool)
    if f.position:
        m &= np.array([p == f.position for p in rd.positions], dtype=bool)
    if f.competition:
        m &= np.array([(c or UNKNOWN_COMPETITION) == f.competition for c in rd.competitions], dtype=bool)
    if f.club:
        q = f.club.lower()
        m &= np.array([bool(c) and q in c.lower() for c in rd.clubs], dtype=bool)
    if f.name:
        q = f.name.lower()
        m &= np.array([q in n.lower() for n in rd.names], dtype=bool)
    if f.nationality:
        m &= np.array([f.nationality in ns for ns in rd.nationalities], dtype=bool)
    if f.foot:
        m &= np.array([ft == f.foot for ft in rd.feet], dtype=bool)
    with np.errstate(invalid="ignore"):
        if f.min_age is not None:
            m &= rd.age >= f.min_age
        if f.max_age is not None:
            m &= rd.age <= f.max_age
        if f.min_minutes is not None:
            m &= rd.minutes >= f.min_minutes
        if f.min_value is not None:
            m &= rd.market_value >= f.min_value
        if f.max_value is not None:
            m &= rd.market_value <= f.max_value
        if f.max_wage is not None:
            m &= rd.wage <= f.max_wage
        if f.contract_within_days is not None:
            m &= (rd.contract_days >= 0) & (rd.contract_days <= f.contract_within_days)
        if f.min_potential_gap is not None:
            m &= (rd.pa - rd.ca) >= f.min_potential_gap
    if f.listed is not None:
        m &= rd.listed == f.listed
    if f.loan_listed is not None:
        m &= rd.loan_listed == f.loan_listed
    return m


def condition_mask(ctx: Ctx, g: ConditionGroup) -> np.ndarray:
    parts = []
    for c in g.conditions:
        if isinstance(c, ConditionGroup):
            parts.append(condition_mask(ctx, c))
            continue
        ctx.cat.parse_view(c.metric)
        vals = ctx.pct(c.metric).percentile if c.kind == "percentile" else ctx.rd.view(ctx.cat, c.metric)
        m = ~np.isnan(vals)  # dado em falta nunca satisfaz uma condição
        with np.errstate(invalid="ignore"):
            if c.min is not None:
                m &= vals >= c.min
            if c.max is not None:
                m &= vals <= c.max
        parts.append(m)
    if not parts:
        return np.ones(ctx.rd.n, dtype=bool)
    return np.logical_and.reduce(parts) if g.op == "and" else np.logical_or.reduce(parts)


def metric_cell(ctx: Ctx, key: str, i: int) -> dict[str, Any]:
    m, view = ctx.cat.parse_view(key)
    p = ctx.pct(key)
    st = p.stats_for(i)
    total_key = m.id
    return {
        "key": key, "value": _f(p.values[i]),
        "total": _f(ctx.rd.view(ctx.cat, total_key)[i]) if view == "p90" else _f(p.values[i]),
        "percentile": _f(p.percentile[i]), "rank": _f(p.rank[i]), "universe": int(p.universe_size[i]),
        "universe_mean": _f(st["mean"]) if st else None, "universe_median": _f(st["median"]) if st else None,
    }


def run_search(ctx: Ctx, req: SearchRequest) -> dict[str, Any]:
    rd, cat = ctx.rd, ctx.cat
    mask = base_mask(rd, req.filters)
    if req.conditions and req.conditions.conditions:
        mask &= condition_mask(ctx, req.conditions)
    comp_rows = [ctx.s.get(CompositeScoreDefinition, cid) for cid in req.composite_ids]
    comp_rows = [c for c in comp_rows if c is not None]
    comp_results = {c.id: ctx.composite(c) for c in comp_rows}

    sort = req.sort
    if sort.by in ("value", "percentile"):
        key = sort.metric or (req.columns[0] if req.columns else "minutes")
        cat.parse_view(key)
        col = ctx.pct(key).percentile if sort.by == "percentile" else rd.view(cat, key)
    elif sort.by == "composite":
        if sort.composite_id not in comp_results:
            row = ctx.s.get(CompositeScoreDefinition, sort.composite_id) if sort.composite_id else None
            if row is None:
                raise ValueError("Composite Score desconhecido")
            comp_results[row.id] = ctx.composite(row)
            comp_rows.append(row)
        col = comp_results[sort.composite_id].score
    elif sort.by == "name":
        col = None
    else:
        col = {"age": rd.age, "market_value": rd.market_value, "wage": rd.wage, "minutes": rd.minutes,
               "ca": rd.ca, "pa": rd.pa}[sort.by]

    idx = np.nonzero(mask)[0]
    if col is None:
        idx = np.array(sorted(idx, key=lambda i: rd.names[i].lower(), reverse=sort.order == "desc"), dtype=int)
    else:
        v = col[idx]
        nan_last = np.isnan(v)
        keyv = np.where(nan_last, np.inf, -v if sort.order == "desc" else v)
        idx = idx[np.lexsort((rd.snapshot_ids[idx], keyv))]
    total = len(idx)
    page = idx[req.offset:req.offset + req.limit]
    items = []
    for i in page:
        it = player_row(ctx, int(i))
        it["metrics"] = {k: metric_cell(ctx, k, int(i)) for k in req.columns}
        it["composites"] = {str(cid): {"score": _f(r.score[i]), "coverage": _f(r.coverage[i])}
                            for cid, r in comp_results.items()}
        items.append(it)
    summary = {}
    for k in req.columns[:6]:
        p = ctx.pct(k)
        parts = {pp for pp in p.partition[idx] if pp is not None} if total else set()
        summary[k] = [{"partition": pp, **p.partitions[pp]} for pp in sorted(parts) if pp in p.partitions][:20]
    return {
        "run_id": ctx.run.id, "scope": req.scope, "scope_label": SCOPES[req.scope], "total": total, "items": items,
        "universe": ctx.universe.describe(), "universe_summary": summary,
        "composites": [{"id": c.id, "name": c.name, "group": c.group_key} for c in comp_rows],
        "notes": _notes(ctx, idx),
    }


def _notes(ctx: Ctx, idx: np.ndarray) -> list[str]:
    notes = []
    comps = {ctx.rd.competitions[i] for i in idx}
    if None in comps:
        notes.append("Há jogadores sem competição identificada no save: o universo junta todas as competições.")
    if len(comps - {None}) > 1 and ctx.universe.competition == "same":
        notes.append("Resultados de várias competições: cada percentil é calculado dentro da competição do jogador "
                     "e não é diretamente comparável entre competições.")
    groups = {ctx.rd.groups[i] for i in idx}
    if len(groups) > 1 and ctx.universe.position_level != "all":
        notes.append("Jogadores de posições diferentes: cada percentil compara com a posição do próprio jogador.")
    return notes


def player_row(ctx: Ctx, i: int) -> dict[str, Any]:
    rd = ctx.rd
    return {
        "player_id": int(rd.player_ids[i]), "snapshot_id": int(rd.snapshot_ids[i]), "name": rd.names[i],
        "age": _f(rd.age[i]), "club": rd.clubs[i], "competition": rd.competitions[i] or UNKNOWN_COMPETITION,
        "position": rd.positions[i], "group": rd.groups[i], "natural_positions": rd.natural_positions[i],
        "nationalities": rd.nationalities[i], "foot": rd.feet[i], "height": _f(rd.height[i]),
        "ca": _f(rd.ca[i]), "pa": _f(rd.pa[i]), "market_value": _f(rd.market_value[i]), "wage": _f(rd.wage[i]),
        "contract_expires": rd.contract_expires[i], "minutes": _f(rd.minutes[i]),
        "listed": bool(rd.listed[i]), "loan_listed": bool(rd.loan_listed[i]),
    }


# ---------------------------------------------------------------- comparação


def compare(ctx: Ctx, player_ids: list[int], keys: list[str], composite_rows: list[CompositeScoreDefinition]) -> dict[str, Any]:
    idxs = []
    for pid in player_ids:
        i = ctx.rd.index_of_player(pid)
        if i is None:
            raise LookupError(f"jogador {pid} sem estatísticas nesta importação")
        idxs.append(i)
    comps = {c.id: ctx.composite(c) for c in composite_rows}
    players = []
    for i in idxs:
        row = player_row(ctx, i)
        row["metrics"] = {k: metric_cell(ctx, k, i) for k in keys}
        row["composites"] = {str(cid): {"score": _f(r.score[i]), "coverage": _f(r.coverage[i])} for cid, r in comps.items()}
        players.append(row)
    warnings = []
    if len({p["group"] for p in players}) > 1:
        warnings.append("Os jogadores têm posições diferentes: cada percentil é relativo à posição do próprio jogador.")
    if len({p["competition"] for p in players}) > 1:
        warnings.append("Os jogadores jogam em competições diferentes: os percentis não são diretamente comparáveis.")
    return {"players": players, "metrics": [{"key": k, "label": ctx.cat.view_label(k), "unit": ctx.cat.view_unit(k),
                                             "direction": ctx.cat.parse_view(k)[0].direction} for k in keys],
            "composites": [{"id": c.id, "name": c.name, "group": c.group_key} for c in composite_rows],
            "universe": ctx.universe.describe(), "warnings": warnings}


# ------------------------------------------------------------ perfil estatístico


def profile(ctx: Ctx, player_id: int, composite_rows: list[CompositeScoreDefinition]) -> dict[str, Any] | None:
    i = ctx.rd.index_of_player(player_id)
    if i is None:
        return None
    cat, rd = ctx.cat, ctx.rd
    group = rd.groups[i]
    avail = ctx.availability()
    mapped_by_field = {fm.field: fm for fm in rd.mapping.values()}

    def source_of(mid: str) -> str:
        a = avail.get(mid)
        if a is None or a.status in ("UNAVAILABLE", "PARTIAL", "INVALID"):
            return "—"
        fields = cat.required_fields(mid)[a.formula_index or 0]
        raws = [f"{mapped_by_field[f].raw} ({mapped_by_field[f].confidence})" for f in sorted(fields) if f in mapped_by_field]
        label = PROFILE_LABEL.get(rd.profile or "", rd.profile or "")
        return f"{label}: {', '.join(raws)}" if raws else label

    def row(key: str) -> dict[str, Any]:
        m, view = cat.parse_view(key)
        a = avail.get(m.id)
        cell = metric_cell(ctx, key, i)
        return {**cell, "label": cat.view_label(key), "unit": cat.view_unit(key), "metric": m.id, "view": view,
                "category": m.category, "direction": m.direction, "type": m.type, "composed": m.composed,
                "status": a.status if a else "UNAVAILABLE", "reason": a.reason if a else "", "source": source_of(m.id)}

    group_items: list[str] = []
    for _t, items in cat.position_map.get(group or "", []):
        for it in items:
            if it not in group_items:
                group_items.append(it)

    def keys_for(categories: tuple[str, ...]) -> list[str]:
        own = [k for k in group_items if cat.parse_view(k)[0].category in categories]
        others = []
        for m in cat.metrics.values():
            if m.category in categories:
                for k in ([m.id, f"{m.id}@p90"] if m.per90 else [m.id]):
                    if k not in own:
                        others.append(k)
        return own + others

    tabs = {}
    for tab, (label, cats) in PROFILE_TABS.items():
        rows = [row(k) for k in keys_for(cats)]
        tabs[tab] = {"label": label, "rows": rows}
    comps = []
    for c in composite_rows:
        r = ctx.composite(c)
        comps.append({"id": c.id, "name": c.name, "group": c.group_key, "score": _f(r.score[i]),
                      "coverage": _f(r.coverage[i]), "applies": c.group_key == group,
                      "components": [{"metric": comp.metric, "label": cat.view_label(comp.metric), "weight": comp.weight,
                                      "percentile": _f(r.component_pct[i, j])}
                                     for j, comp in enumerate(r.components)]})
    pct_rows = sorted((r for t in tabs.values() for r in t["rows"] if r["percentile"] is not None),
                      key=lambda r: -r["percentile"])
    seen = set()
    pct_unique = [r for r in pct_rows if not (r["key"] in seen or seen.add(r["key"]))]
    overview_keys = [k for k in group_items if avail.get(cat.parse_view(k)[0].id) is not None
                     and avail[cat.parse_view(k)[0].id].status in ("AVAILABLE", "CALCULABLE", "CUSTOM")][:12]
    return {
        "player": player_row(ctx, i), "group_label": POSITION_GROUPS.get(group or "", ("—",))[0],
        "universe": ctx.universe.describe(), "scope_label": SCOPES[rd.scope],
        "overview": [row(k) for k in overview_keys], "composites": comps, "tabs": tabs,
        "percentiles": pct_unique,
        "categories": CATEGORY_LABEL,
    }


def history(s: Session, player_id: int, keys: list[str], scope: str) -> list[dict[str, Any]]:
    """Evolução: valores do jogador em cada importação da carreira com estatísticas."""
    snaps = s.execute(select(PlayerSnapshot.run_id).where(PlayerSnapshot.player_id == player_id)
                      .order_by(PlayerSnapshot.run_id)).scalars().all()
    out = []
    for run_id in snaps:
        run = s.get(ImportRun, run_id)
        ctx = Ctx(s, run, scope)
        i = ctx.rd.index_of_player(player_id)
        if i is None:
            continue
        out.append({"run_id": run_id, "game_date": run.game_date.isoformat() if run.game_date else None,
                    "season": run.season_label, "minutes": _f(ctx.rd.minutes[i]),
                    "values": {k: metric_cell(ctx, k, i) for k in keys}})
    return out


# ---------------------------------------------------------------- mercado


class MarketRequest(BaseModel):
    run_id: int | None = None
    career_id: int | None = None
    scope: Literal["club", "league"] = "club"
    filters: BaseFilters = Field(default_factory=BaseFilters)
    universe: UniverseIn = Field(default_factory=UniverseIn)
    composite_id: int | None = None
    metric: str | None = None
    min_performance: float = Field(70, ge=0, le=100, description="Score/percentil mínimo de desempenho")
    sort: Literal["performance", "value", "value_per_point", "contract"] = "performance"
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


def market(ctx: Ctx, req: MarketRequest) -> dict[str, Any]:
    rd = ctx.rd
    if req.composite_id:
        row = ctx.s.get(CompositeScoreDefinition, req.composite_id)
        if row is None:
            raise ValueError("Composite Score desconhecido")
        perf = ctx.composite(row).score
        perf_label = f"Composite: {row.name}"
    elif req.metric:
        ctx.cat.parse_view(req.metric)
        perf = ctx.pct(req.metric).percentile
        perf_label = f"Percentil: {ctx.cat.view_label(req.metric)}"
    else:
        raise ValueError("Escolha um Composite Score ou uma métrica de desempenho")
    mask = base_mask(rd, req.filters) & ~np.isnan(perf)
    with np.errstate(invalid="ignore"):
        mask &= perf >= req.min_performance
    with np.errstate(divide="ignore", invalid="ignore"):
        value_per_point = np.where(perf > 0, rd.market_value / perf, np.nan)
    idx = np.nonzero(mask)[0]
    col = {"performance": -perf, "value": rd.market_value, "value_per_point": value_per_point,
           "contract": np.where(np.isnan(rd.contract_days), np.inf, rd.contract_days)}[req.sort]
    keyv = np.where(np.isnan(col[idx]), np.inf, col[idx])
    idx = idx[np.lexsort((rd.snapshot_ids[idx], keyv))]
    items = []
    for i in idx[req.offset:req.offset + req.limit]:
        it = player_row(ctx, int(i))
        it["performance"] = _f(perf[i])
        it["value_per_point"] = _f(value_per_point[i])
        it["potential_gap"] = _f(rd.pa[i] - rd.ca[i])
        it["contract_days"] = _f(rd.contract_days[i])
        items.append(it)
    return {"total": len(idx), "items": items, "performance_label": perf_label, "universe": ctx.universe.describe(),
            "caveat": "Bons indicadores estatísticos não fazem automaticamente uma boa contratação: confirme "
                      "contexto (liga, papel tático, minutos, idade, personalidade) antes de decidir.",
            "value_per_point_note": "Valor de mercado ÷ score de desempenho (derivado; menor = mais barato por ponto)."}


# ------------------------------------------------------------------ overview


def overview(ctx: Ctx, composite_rows: list[CompositeScoreDefinition]) -> dict[str, Any]:
    rd = ctx.rd
    avail = ctx.availability()
    counts: dict[str, int] = {}
    for a in avail.values():
        counts[a.status] = counts.get(a.status, 0) + 1
    eligible = int(np.sum(rd.minutes >= ctx.universe.min_minutes)) if rd.n else 0
    groups = {}
    for g in POSITION_GROUPS:
        sel = np.array([x == g for x in rd.groups], dtype=bool)
        groups[g] = {"label": POSITION_GROUPS[g][0], "players": int(sel.sum()),
                     "eligible": int((sel & (rd.minutes >= ctx.universe.min_minutes)).sum()) if rd.n else 0}
    tops = []
    for c in composite_rows:
        r = ctx.composite(c)
        order = np.argsort(np.where(np.isnan(r.score), np.inf, -r.score))[:5]
        tops.append({"id": c.id, "name": c.name, "group": c.group_key,
                     "evaluated": int(np.sum(~np.isnan(r.score))),
                     "mean_coverage": _f(np.nanmean(r.coverage)) if np.any(~np.isnan(r.coverage)) else None,
                     "top": [{**player_row(ctx, int(i)), "score": _f(r.score[i]), "coverage": _f(r.coverage[i])}
                             for i in order if not np.isnan(r.score[i])]})
    comps = sorted({c or UNKNOWN_COMPETITION for c in rd.competitions})
    return {"run_id": ctx.run.id, "players_with_stats": rd.n, "eligible": eligible, "availability": counts,
            "catalog_size": len(ctx.cat.metrics), "groups": groups, "composites": tops, "competitions": comps,
            "universe": ctx.universe.describe(), "data_source": PROFILE_LABEL.get(rd.profile or "", rd.profile)}


def catalog_payload(cat: Catalog) -> dict[str, Any]:
    return {
        "metrics": [cat.describe(m) for m in cat.metrics],
        "groups": [{"key": g, "label": label, "positions": list(ps),
                    "sections": [{"title": t, "items": items} for t, items in cat.position_map.get(g, [])]}
                   for g, (label, ps) in POSITION_GROUPS.items()],
        "transversal": [{"title": t, "items": items} for t, items in cat.transversal],
        "categories": CATEGORY_LABEL,
        "tabs": {k: {"label": v[0], "categories": list(v[1])} for k, v in PROFILE_TABS.items()},
        "fields": {k: {"name": v[0], "unit": v[1], "description": v[2]} for k, v in cat.fields.items()},
        "views": [{"key": k, "label": cat.view_label(k), "unit": cat.view_unit(k)} for k in cat.all_views()],
    }
