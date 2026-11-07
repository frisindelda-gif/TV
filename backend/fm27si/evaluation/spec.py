"""Esquema de uma especificação de avaliação (o que o Position Lab edita).

Uma especificação é DADOS, não código: métricas (atributos + pesos), posições (métricas +
pesos) e funções táticas (métricas + pesos). O motor (``engine.py``) só a lê.

Regras:
- Métricas referem atributos do catálogo (``fm27si.catalog``); posições e funções referem
  métricas. Assim cada atributo existe uma única vez e os indicadores calculados nunca
  se confundem com atributos originais.
- Pesos são relativos (só a proporção conta) e têm de ser > 0.
- ``invert`` serve para atributos em que mais é pior (p.ex. propensão a lesões).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fm27si.catalog import ATTRIBUTES

MetricCategory = Literal["technical", "mental", "physical", "tactical", "position_specific"]

# As 12 posições pedidas, com o código FM interno (usado nas classificações de posição) e o
# código português mostrado na interface.
POSITIONS: dict[str, tuple[str, str]] = {
    "GK": ("GR", "Guarda-redes"),
    "DR": ("DD", "Defesa direito"),
    "DC": ("DC", "Defesa central"),
    "DL": ("DE", "Defesa esquerdo"),
    "DM": ("MDC", "Médio defensivo"),
    "MC": ("MC", "Médio centro"),
    "MR": ("MD", "Médio direito"),
    "AMC": ("MO", "Médio ofensivo"),
    "ML": ("ME", "Médio esquerdo"),
    "AMR": ("AD", "Extremo direito"),
    "ST": ("PL", "Ponta de lança"),
    "AML": ("AE", "Extremo esquerdo"),
}

# Grupos dos rankings: a pontuação do grupo é a melhor das posições do grupo em que o
# jogador é competente.
RANKING_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "GK": ("Guarda-redes", ("GK",)),
    "CB": ("Centrais", ("DC",)),
    "FB": ("Laterais", ("DR", "DL")),
    "DM": ("Médios defensivos", ("DM",)),
    "CM": ("Médios centro", ("MC",)),
    "AM": ("Médios ofensivos", ("AMC",)),
    "W": ("Extremos e alas", ("AMR", "AML", "MR", "ML")),
    "ST": ("Avançados", ("ST",)),
}

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttributeWeight(_M):
    attribute: str
    weight: float = Field(gt=0, le=100)
    invert: bool = False

    @field_validator("attribute")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in ATTRIBUTES:
            raise ValueError(f"atributo desconhecido: {v}")
        return v


class MetricWeight(_M):
    metric: str
    weight: float = Field(gt=0, le=100)


class MetricSpec(_M):
    key: str
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    category: MetricCategory
    positions: list[str] = Field(default_factory=list, description="Posições a que se aplica; vazio = todas")
    attributes: list[AttributeWeight] = Field(min_length=1)

    @field_validator("key")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError("chave inválida (minúsculas, números e _, 2–49 caracteres)")
        return v

    @model_validator(mode="after")
    def _unique_attrs(self) -> MetricSpec:
        keys = [a.attribute for a in self.attributes]
        if len(keys) != len(set(keys)):
            raise ValueError(f"métrica {self.key}: atributo repetido")
        bad = [p for p in self.positions if p not in POSITIONS]
        if bad:
            raise ValueError(f"métrica {self.key}: posições desconhecidas {bad}")
        return self


class PositionSpec(_M):
    key: str
    metrics: list[MetricWeight] = Field(min_length=1)

    @field_validator("key")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in POSITIONS:
            raise ValueError(f"posição desconhecida: {v}")
        return v


class RoleSpec(_M):
    key: str
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    positions: list[str] = Field(min_length=1)
    metrics: list[MetricWeight] = Field(min_length=1)
    enabled: bool = True
    # "unconfirmed" até ser confirmado no FM27 instalado. Nunca marcar "confirmed" sem ver o jogo.
    availability: Literal["confirmed", "unconfirmed"] = "unconfirmed"

    @field_validator("key")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError("chave inválida")
        return v

    @model_validator(mode="after")
    def _positions(self) -> RoleSpec:
        bad = [p for p in self.positions if p not in POSITIONS]
        if bad:
            raise ValueError(f"função {self.key}: posições desconhecidas {bad}")
        return self


class EvaluationSpec(_M):
    schema_version: Literal[1] = 1
    min_coverage: float = Field(0.6, ge=0.1, le=1.0, description="Abaixo disto o resultado não é calculado")
    metrics: list[MetricSpec] = Field(min_length=1)
    positions: list[PositionSpec]
    roles: list[RoleSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _references(self) -> EvaluationSpec:
        mkeys = [m.key for m in self.metrics]
        if len(mkeys) != len(set(mkeys)):
            raise ValueError("chaves de métrica repetidas")
        known = set(mkeys)
        pkeys = [p.key for p in self.positions]
        if len(pkeys) != len(set(pkeys)):
            raise ValueError("posição repetida")
        missing_pos = sorted(set(POSITIONS) - set(pkeys))
        if missing_pos:
            raise ValueError(f"faltam modelos para as posições {missing_pos}")
        rkeys = [r.key for r in self.roles]
        if len(rkeys) != len(set(rkeys)):
            raise ValueError("chaves de função repetidas")
        for owner, refs in [*((f"posição {p.key}", p.metrics) for p in self.positions),
                            *((f"função {r.key}", r.metrics) for r in self.roles)]:
            names = [w.metric for w in refs]
            if len(names) != len(set(names)):
                raise ValueError(f"{owner}: métrica repetida")
            unknown = [n for n in names if n not in known]
            if unknown:
                raise ValueError(f"{owner}: métricas desconhecidas {unknown}")
        return self

    # ------------------------------------------------------------------ util
    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def spec_hash(self) -> str:
        """Identifica exatamente os pesos usados: mesmo hash + mesmos atributos = mesmo resultado."""
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()[:16]

    def metric(self, key: str) -> MetricSpec:
        return next(m for m in self.metrics if m.key == key)

    def position(self, key: str) -> PositionSpec:
        return next(p for p in self.positions if p.key == key)

    def role(self, key: str) -> RoleSpec:
        return next(r for r in self.roles if r.key == key)


def formula_text(metric: MetricSpec) -> str:
    """Fórmula legível de uma métrica, gerada a partir dos pesos (nunca escrita à mão)."""
    total = sum(a.weight for a in metric.attributes)
    parts = []
    for a in metric.attributes:
        term = f"(100 − n({a.attribute}))" if a.invert else f"n({a.attribute})"
        parts.append(f"{a.weight:g}×{term}")
    return f"({' + '.join(parts)}) / {total:g}, com n(a) = (a − 1) / 19 × 100"
