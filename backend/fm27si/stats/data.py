"""Dados estatísticos de uma importação, prontos a analisar (PlayerSeasonStatistics).

As observações vêm de ``season_stats`` (uma linha por jogador × tipo de competição, com a
proveniência da importação). Aqui são agregadas por âmbito, mapeadas para os campos
canónicos e passadas pelo motor de métricas. O resultado fica em cache por importação:
as importações são imutáveis, por isso nada é recalculado ao mudar um filtro.

Âmbitos:
- ``club``  : todas as competições de clube (linha "overall" do jogo se existir; senão
              soma de liga + taças + continentais). Seleções e particulares ficam de fora.
- ``league``: só jogos de liga.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from fm27si.orm import ImportRun, Player, PlayerSnapshot, SeasonStatLine
from fm27si.stats.catalog import Catalog
from fm27si.stats.catalog_data import POSITION_GROUPS
from fm27si.stats.engine import DerivedMetricEngine, EngineResult, per90
from fm27si.stats.mapping import FieldMapping, profile_for

CLUB_KINDS = {"league", "cup", "continental"}
SCOPES = {"club": "Competições de clube", "league": "Só liga"}
_ALIAS_POS = {"WBL": "DL", "WBR": "DR", "SW": "DC"}
POS_TO_GROUP = {p: g for g, (_l, ps) in POSITION_GROUPS.items() for p in ps}
_CORE = ("starts", "sub_appearances", "minutes", "goals", "assists", "average_rating", "player_of_the_match",
         "expected_goals", "expected_assists", "yellow_cards", "red_cards", "clean_sheets")


def primary_position(natural: list | None, accomplished: list | None = None) -> str | None:
    for p in [*(natural or []), *(accomplished or [])]:
        p = _ALIAS_POS.get(p, p)
        if p in POS_TO_GROUP:
            return p
    return None


def preferred_foot(pref: str | None, left: int | None, right: int | None) -> str | None:
    if pref:
        return pref
    if left is None or right is None:
        return None
    if left >= 14 and right >= 14:
        return "both"
    return "right" if right >= left else "left"


@dataclass
class RunStats:
    run_id: int
    scope: str
    profile: str | None
    mapping: dict[str, FieldMapping]
    game_date: date | None
    snapshot_ids: np.ndarray
    player_ids: np.ndarray
    names: list[str]
    clubs: list[str | None]
    competitions: list[str | None]
    positions: list[str | None]
    groups: list[str | None]
    natural_positions: list[list[str]]
    nationalities: list[list[str]]
    feet: list[str | None]
    age: np.ndarray
    ca: np.ndarray
    pa: np.ndarray
    height: np.ndarray
    market_value: np.ndarray
    wage: np.ndarray
    contract_days: np.ndarray  # dias até ao fim do contrato (a partir da data do jogo)
    contract_expires: list[str | None]
    listed: np.ndarray
    loan_listed: np.ndarray
    fields: list[str]
    x: np.ndarray  # n × campos (NaN = em falta)
    raw_presence: dict[str, int]  # chave do save → jogadores com valor
    raw_values: dict[str, list[float]] = field(repr=False, default_factory=dict)
    result: EngineResult | None = None
    token: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)  # identifica este conjunto de dados
    _view_cache: dict[str, np.ndarray] = field(default_factory=dict, repr=False)

    @property
    def n(self) -> int:
        return len(self.snapshot_ids)

    @property
    def minutes(self) -> np.ndarray:
        return self.result.column("minutes")

    def view(self, catalog: Catalog, key: str) -> np.ndarray:
        if key in self._view_cache:
            return self._view_cache[key]
        m, v = catalog.parse_view(key)
        total = self.result.column(m.id)
        out = per90(total, self.minutes) if v == "p90" else total
        self._view_cache[key] = out
        return out

    def index_of_player(self, player_id: int) -> int | None:
        hits = np.nonzero(self.player_ids == player_id)[0]
        return int(hits[0]) if len(hits) else None


def _aggregate(lines: list[tuple[str, dict[str, Any]]], scope: str) -> dict[str, float] | None:
    if scope == "league":
        use = [d for k, d in lines if k == "league"]
    else:
        overall = [d for k, d in lines if k == "overall"]
        use = overall or [d for k, d in lines if k in CLUB_KINDS]
    if not use:
        return None
    out: dict[str, float] = {}
    for d in use:
        for k, v in d.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = out.get(k, 0.0) + float(v)
    return out


def load_run_stats(s: Session, run: ImportRun, catalog: Catalog, scope: str, custom_mappings: dict[str, FieldMapping]) -> RunStats:
    profile, mapping = profile_for(run.connector, custom_mappings)
    S, L = PlayerSnapshot, SeasonStatLine
    lines_by_snap: dict[int, list[tuple[str, dict]]] = {}
    core_cols = [getattr(L, c) for c in _CORE]
    for row in s.execute(select(L.snapshot_id, L.competition_kind, L.extra, *core_cols)
                         .join(S, S.id == L.snapshot_id).where(S.run_id == run.id)):
        d = dict(row.extra or {})
        for c, v in zip(_CORE, row[3:], strict=True):
            if v is not None:
                d[c] = v
        lines_by_snap.setdefault(row.snapshot_id, []).append((row.competition_kind, d))

    meta = s.execute(
        select(S.id, S.player_id, S.name, S.age, S.ca, S.pa, S.market_value, S.wage_weekly, S.contract_expires,
               S.preferred_foot, S.foot_left, S.foot_right, S.height_cm, S.club_name, S.division,
               S.natural_positions, S.accomplished_positions, S.contract, Player.nationalities)
        .join(Player, Player.id == S.player_id)
        .where(S.run_id == run.id)
        .order_by(S.id)
    ).all()
    meta = [r for r in meta if r.id in lines_by_snap]  # só jogadores com estatísticas (sem IN gigante)

    fields = list(catalog.fields)
    fidx = {f: i for i, f in enumerate(fields)}
    n = len(meta)
    x = np.full((n, len(fields)), np.nan)
    presence: dict[str, int] = {}
    raw_values: dict[str, list[float]] = {}
    keep = np.zeros(n, dtype=bool)
    for i, r in enumerate(meta):
        agg = _aggregate(lines_by_snap.get(r.id, []), scope)
        if agg is None:
            continue
        keep[i] = True
        for raw, v in agg.items():
            presence[raw] = presence.get(raw, 0) + 1
            raw_values.setdefault(raw, []).append(v)
            fm = mapping.get(raw)
            if fm is not None and fm.field in fidx:
                x[i, fidx[fm.field]] = v
    meta = [r for i, r in enumerate(meta) if keep[i]]
    x = x[keep]

    gd = run.game_date

    def days(d):
        return float((d - gd).days) if d and gd else np.nan

    def arr(vals):
        return np.array([np.nan if v is None else float(v) for v in vals], dtype=float)

    positions = [primary_position(r.natural_positions, r.accomplished_positions) for r in meta]
    rs = RunStats(
        run_id=run.id, scope=scope, profile=profile, mapping=mapping, game_date=gd,
        snapshot_ids=np.array([r.id for r in meta], dtype=np.int64),
        player_ids=np.array([r.player_id for r in meta], dtype=np.int64),
        names=[r.name for r in meta],
        clubs=[r.club_name for r in meta],
        competitions=[r.division for r in meta],
        positions=positions,
        groups=[POS_TO_GROUP.get(p) if p else None for p in positions],
        natural_positions=[list(r.natural_positions or []) for r in meta],
        nationalities=[list(r.nationalities or []) for r in meta],
        feet=[preferred_foot(r.preferred_foot, r.foot_left, r.foot_right) for r in meta],
        age=arr(r.age for r in meta), ca=arr(r.ca for r in meta), pa=arr(r.pa for r in meta),
        height=arr(r.height_cm for r in meta), market_value=arr(r.market_value for r in meta),
        wage=arr(r.wage_weekly for r in meta),
        contract_days=np.array([days(r.contract_expires) for r in meta], dtype=float),
        contract_expires=[r.contract_expires.isoformat() if r.contract_expires else None for r in meta],
        listed=np.array([bool((r.contract or {}).get("transfer_listed")) for r in meta]),
        loan_listed=np.array([bool((r.contract or {}).get("loan_listed")) for r in meta]),
        fields=fields, x=x, raw_presence=presence, raw_values=raw_values,
    )
    rs.result = DerivedMetricEngine(catalog, fields).compute(x)
    return rs


class RunStatsCache:
    """Cache LRU por (importação, âmbito, versão do catálogo)."""

    def __init__(self, size: int = 6):
        self._d: OrderedDict[tuple, RunStats] = OrderedDict()
        self._lock = threading.Lock()
        self.size = size

    def get(self, key: tuple, build) -> RunStats:
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
        value = build()
        with self._lock:
            self._d[key] = value
            while len(self._d) > self.size:
                self._d.popitem(last=False)
        return value

    def clear(self) -> None:
        with self._lock:
            self._d.clear()


RUN_CACHE = RunStatsCache()
