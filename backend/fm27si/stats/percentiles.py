"""PercentileCalculationService: universos de comparação, percentis e rankings.

Percentil = 100 × (abaixo + 0,5 × empatados) / elegíveis — calculado dentro de cada
universo (partição). Para métricas em que menos é melhor, a ordem é invertida, por isso
100 é sempre o melhor. Sem amostra suficiente não há percentil.

Universo por defeito (secção 4.1): mesma época (importação) e âmbito, mesma competição,
mesmo grupo de posição, mesma métrica e unidade (a vista), minutos mínimos.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal

import numpy as np

from fm27si.stats.catalog import Catalog
from fm27si.stats.data import RunStats

MIN_MINUTES_OPTIONS = (450, 900, 1350, 1800)
UNKNOWN_COMPETITION = "Competição não identificada"


@dataclass(frozen=True)
class Universe:
    competition: Literal["same", "all"] = "same"
    position_level: Literal["group", "position", "all"] = "group"
    min_minutes: int = 450
    min_sample: int = 10
    population: tuple[int, ...] | None = None  # snapshot ids escolhidos pelo utilizador
    population_label: str | None = None

    def describe(self) -> str:
        parts = [
            "mesma competição" if self.competition == "same" else "todas as competições",
            {"group": "mesmo grupo de posição", "position": "mesma posição", "all": "todas as posições"}[self.position_level],
            f"≥ {self.min_minutes} minutos",
        ]
        if self.population is not None:
            parts.append(f"população: {self.population_label or f'{len(self.population)} jogadores selecionados'}")
        return ", ".join(parts)


@dataclass
class PercentileResult:
    key: str
    values: np.ndarray
    percentile: np.ndarray
    rank: np.ndarray
    universe_size: np.ndarray  # jogadores com valor no universo de cada jogador
    eligible: np.ndarray
    partition: np.ndarray  # chave do universo de cada jogador
    partitions: dict[str, dict]  # chave → estatísticas do universo

    def stats_for(self, i: int) -> dict | None:
        return self.partitions.get(self.partition[i])


def partition_keys(rd: RunStats, u: Universe) -> np.ndarray:
    comp = [c or UNKNOWN_COMPETITION for c in rd.competitions] if u.competition == "same" else ["*"] * rd.n
    if u.position_level == "group":
        pos = rd.groups
    elif u.position_level == "position":
        pos = rd.positions
    else:
        pos = ["*"] * rd.n
    return np.array([None if p is None else f"{c}|{p}" for c, p in zip(comp, pos, strict=True)], dtype=object)


def eligible_mask(rd: RunStats, u: Universe) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        m = ~np.isnan(rd.minutes) & (rd.minutes >= u.min_minutes)
    if u.population is not None:
        m &= np.isin(rd.snapshot_ids, np.array(u.population, dtype=np.int64))
    return m


def _partition_index(rd: RunStats, u: Universe):
    """Chaves de universo + grupos de índices, calculados uma vez por (dados, competição, posição)."""
    ck = ("__partitions__", u.competition, u.position_level)
    hit = rd._view_cache.get(ck)
    if hit is None:
        parts = partition_keys(rd, u)
        groups: dict[str, np.ndarray] = {}
        valid = [i for i, p in enumerate(parts) if p is not None]
        if valid:
            keys = parts[valid]
            order = np.argsort(keys.astype(str), kind="stable")
            sorted_keys = keys[order].astype(str)
            uniq, starts = np.unique(sorted_keys, return_index=True)
            bounds = list(starts) + [len(sorted_keys)]
            valid_arr = np.array(valid)[order]
            for j, k in enumerate(uniq):
                groups[str(k)] = valid_arr[bounds[j]:bounds[j + 1]]
        hit = (parts, groups)
        rd._view_cache[ck] = hit
    return hit


def compute(rd: RunStats, catalog: Catalog, key: str, u: Universe) -> PercentileResult:
    metric, _view = catalog.parse_view(key)
    values = rd.view(catalog, key)
    parts, groups = _partition_index(rd, u)
    elig_base = eligible_mask(rd, u)
    elig = elig_base & np.array([p is not None for p in parts], dtype=bool)
    n = rd.n
    pct = np.full(n, np.nan)
    rank = np.full(n, np.nan)
    size = np.zeros(n)
    stats: dict[str, dict] = {}
    if metric.percentile:
        higher = metric.direction == "higher"
        for k, gidx in groups.items():
            idx = gidx[elig_base[gidx]]
            if not len(idx):
                continue
            vals = values[idx]
            ok = ~np.isnan(vals)
            vv = vals[ok]
            N = len(vv)
            comp, _, pos = k.partition("|")
            info = {
                "competition": comp, "position": pos, "eligible": len(idx), "with_value": N,
                "coverage": round(N / len(idx), 4) if len(idx) else None,
                "mean": float(np.mean(vv)) if N else None, "median": float(np.median(vv)) if N else None,
                "best": (float(np.max(vv)) if higher else float(np.min(vv))) if N else None,
                "worst": (float(np.min(vv)) if higher else float(np.max(vv))) if N else None,
                "sufficient": N >= u.min_sample,
            }
            stats[k] = info
            size[idx] = N
            if N < u.min_sample:
                continue
            sv = vv if higher else -vv
            srt = np.sort(sv)
            left = np.searchsorted(srt, sv, "left")
            right = np.searchsorted(srt, sv, "right")
            sel = idx[ok]
            pct[sel] = 100.0 * (left + 0.5 * (right - left)) / N
            rank[sel] = N - right + 1  # 1 + nº de jogadores estritamente melhores
    return PercentileResult(key, values, pct, rank, size, elig, parts, stats)


class PercentileCache:
    def __init__(self, size: int = 512):
        self._d: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.size = size

    def get(self, rd: RunStats, catalog: Catalog, key: str, u: Universe, catalog_version: str) -> PercentileResult:
        ck = (rd.token, catalog_version, key, u)
        with self._lock:
            if ck in self._d:
                self._d.move_to_end(ck)
                return self._d[ck]
        res = compute(rd, catalog, key, u)
        with self._lock:
            self._d[ck] = res
            while len(self._d) > self.size:
                self._d.popitem(last=False)
        return res

    def clear(self) -> None:
        with self._lock:
            self._d.clear()


PCT_CACHE = PercentileCache()
