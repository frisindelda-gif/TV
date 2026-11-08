"""CompositeScoreService: perfis estatísticos configuráveis.

Composite Score = Σ (percentil da componente × peso) / Σ pesos DISPONÍVEIS.
- Componentes sem dados para o jogador ficam de fora (não penalizam); a cobertura mostra
  quanto do modelo foi usado. Abaixo da cobertura mínima o score não é apresentado.
- É sempre um indicador CALCULADO a partir de percentis, nunca uma estatística observada.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator

from fm27si.stats.catalog import Catalog
from fm27si.stats.catalog_data import POSITION_GROUPS
from fm27si.stats.data import RunStats
from fm27si.stats.percentiles import PercentileResult, Universe


class CompositeComponent(BaseModel):
    metric: str  # vista: "x" ou "x@p90"
    weight: float = Field(gt=0, le=100)
    invert: bool = False


class CompositeSpec(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    group_key: str
    components: list[CompositeComponent] = Field(min_length=1, max_length=30)
    min_coverage: float = Field(0.6, ge=0.1, le=1.0)

    @field_validator("group_key")
    @classmethod
    def _group(cls, v: str) -> str:
        if v not in POSITION_GROUPS:
            raise ValueError(f"grupo de posição desconhecido: {v}")
        return v

    @model_validator(mode="after")
    def _unique(self) -> CompositeSpec:
        keys = [c.metric for c in self.components]
        if len(keys) != len(set(keys)):
            raise ValueError("componente repetida")
        return self

    def validate_against(self, cat: Catalog) -> None:
        for c in self.components:
            m, _ = cat.parse_view(c.metric)  # KeyError se não existir
            if not m.composite:
                raise ValueError(f"{c.metric} não pode ser usada em Composite Scores")
            if not m.percentile:
                raise ValueError(f"{c.metric} não tem percentil")


@dataclass
class CompositeResult:
    score: np.ndarray
    coverage: np.ndarray
    component_pct: np.ndarray  # n × componentes (NaN = de fora)
    members: np.ndarray  # jogadores avaliados (grupo do modelo + minutos mínimos)
    components: list[CompositeComponent]
    percentiles: list[PercentileResult]


def compute(rd: RunStats, spec: CompositeSpec, pct_for, universe: Universe) -> CompositeResult:
    """``pct_for(key, universe)`` devolve o PercentileResult (com cache) de cada componente."""
    weights = np.array([c.weight for c in spec.components], dtype=float)
    results = [pct_for(c.metric, universe) for c in spec.components]
    p = np.column_stack([r.percentile for r in results]) if results else np.zeros((rd.n, 0))
    inv = np.array([c.invert for c in spec.components])
    p = np.where(inv, 100.0 - p, p)
    members = results[0].eligible.copy()
    if universe.position_level != "all":
        members &= np.array([g == spec.group_key for g in rd.groups], dtype=bool)
    avail = ~np.isnan(p)
    wsum = avail.astype(float) @ weights
    coverage = wsum / weights.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        score = np.where(avail, p, 0.0) @ weights / np.where(wsum > 0, wsum, np.nan)
    score = np.where(members & (coverage >= spec.min_coverage - 1e-9), score, np.nan)
    coverage = np.where(members, coverage, np.nan)
    return CompositeResult(score, coverage, np.where(members[:, None], p, np.nan), members, spec.components, results)
