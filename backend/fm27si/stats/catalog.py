"""GlobalMetricCatalogService / MetricDefinitionService.

Junta as métricas built-in (``catalog_data``) com as personalizadas aprovadas (BD), valida
as definições e responde a perguntas sobre o catálogo. Não sabe nada de saves.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from fm27si.stats import catalog_data as data
from fm27si.stats.source_fields import SOURCE_FIELDS

MetricType = Literal["count", "percentage", "ratio", "derived_count", "value"]
View = Literal["total", "p90"]

CATEGORY_LABEL: dict[str, str] = {
    "general": "Geral", "goalkeeping": "Guarda-redes", "passing": "Passe", "creation": "Criação",
    "participation": "Participação", "progression": "Progressão", "defending": "Defesa", "duels": "Duelos",
    "discipline": "Disciplina", "pressing": "Pressão", "possession": "Segurança na posse",
    "finishing": "Finalização", "custom": "Personalizadas",
}

# Separadores do perfil estatístico → categorias.
PROFILE_TABS: dict[str, tuple[str, tuple[str, ...]]] = {
    "defensive": ("Defensive", ("goalkeeping", "defending", "discipline")),
    "passing": ("Passing", ("passing", "possession", "participation")),
    "progression": ("Progression", ("progression",)),
    "attacking": ("Attacking", ("finishing", "creation")),
    "physical_duels": ("Physical/Duels", ("duels",)),
    "pressing": ("Pressing", ("pressing",)),
}

UNIT_LABEL = {"count": "", "percent": "%", "minutes": "min", "matches": "jogos", "goals": "golos", "metres": "m",
              "ratio": "", "km": "km"}


class MetricDefinition(BaseModel):
    id: str
    name: str
    alt_name: str | None = None
    description: str
    category: str
    type: MetricType
    unit: str
    formulas: list[dict[str, Any]] = Field(min_length=1)
    per90: bool
    percentile: bool = True
    direction: Literal["higher", "lower"] = "higher"
    composite: bool = True
    composed: bool = False
    eligibility: dict[str, Any] = Field(default_factory=dict)
    validation_status: Literal["defined", "custom"] = "defined"
    data_source: str = "Estatísticas de jogo do save (ver disponibilidade por importação)"
    builtin: bool = True

    @model_validator(mode="after")
    def _rules(self) -> MetricDefinition:
        if self.type == "percentage" and self.per90:
            raise ValueError(f"{self.id}: percentagens não têm valor por 90")
        if self.type == "ratio" and self.per90:
            raise ValueError(f"{self.id}: rácios não têm valor por 90")
        return self


def expr_fields(expr: dict, metrics: dict[str, MetricDefinition], _seen: frozenset = frozenset()) -> set[str]:
    """Campos de origem de uma expressão (expande métricas referidas pela 1.ª fórmula disponível)."""
    if "field" in expr:
        return {expr["field"]}
    if "metric" in expr:
        m = expr["metric"]
        if m in _seen:
            raise ValueError(f"referência circular em {m}")
        return expr_fields(metrics[m].formulas[0], metrics, _seen | {m})
    out: set[str] = set()
    for sub in next(iter(expr.values())):
        out |= expr_fields(sub, metrics, _seen)
    return out


def expr_text(expr: dict, metrics: dict[str, MetricDefinition], fields: dict[str, str]) -> str:
    if "field" in expr:
        return fields.get(expr["field"], expr["field"])
    if "metric" in expr:
        return metrics[expr["metric"]].name if expr["metric"] in metrics else expr["metric"]
    (op, args), = expr.items()
    parts = [expr_text(a, metrics, fields) for a in args]
    if op == "add":
        return " + ".join(parts)
    if op == "sub":
        return f"{parts[0]} − {parts[1]}"
    if op == "div":
        return f"{parts[0]} / {parts[1]}"
    if op == "pct":
        return f"{parts[0]} / {parts[1]} × 100"
    raise ValueError(op)


class Catalog:
    """Catálogo efetivo: built-in + personalizadas. Imutável depois de criado."""

    def __init__(self, custom: list[dict] | None = None, custom_fields: dict[str, tuple[str, str, str]] | None = None):
        self.fields: dict[str, tuple[str, str, str]] = {**SOURCE_FIELDS, **(custom_fields or {})}
        defs = [MetricDefinition(**m) for m in data.METRICS]
        defs += [MetricDefinition(**{**m, "builtin": False, "validation_status": "custom"}) for m in (custom or [])]
        self.metrics: dict[str, MetricDefinition] = {}
        for d in defs:
            if d.id in self.metrics:
                raise ValueError(f"métrica repetida: {d.id}")
            self.metrics[d.id] = d
        self._validate()
        self.position_map = data.POSITION_MAP
        self.transversal = data.TRANSVERSAL
        self.groups = data.POSITION_GROUPS
        self.custom_positions: dict[str, list[str]] = {m["id"]: m.get("groups", []) for m in (custom or [])}

    # ----------------------------------------------------------- validação
    def _validate(self) -> None:
        for m in self.metrics.values():
            for f in m.formulas:
                self._check_expr(f, m.id)
            expr_fields(m.formulas[0], self.metrics, frozenset({m.id}))  # deteta ciclos

    def _check_expr(self, e: dict, owner: str) -> None:
        if not isinstance(e, dict) or len(e) != 1:
            raise ValueError(f"{owner}: expressão inválida {e}")
        (op, arg), = e.items()
        if op == "field":
            if arg not in self.fields:
                raise ValueError(f"{owner}: campo de origem desconhecido {arg}")
        elif op == "metric":
            if arg not in self.metrics:
                raise ValueError(f"{owner}: métrica desconhecida {arg}")
        elif op in ("add", "sub", "div", "pct"):
            if op in ("sub", "div", "pct") and len(arg) != 2:
                raise ValueError(f"{owner}: {op} precisa de 2 operandos")
            for a in arg:
                self._check_expr(a, owner)
        else:
            raise ValueError(f"{owner}: operação desconhecida {op}")

    # ----------------------------------------------------------------- vistas
    def parse_view(self, key: str) -> tuple[MetricDefinition, View]:
        mid, _, view = key.partition("@")
        if mid not in self.metrics:
            raise KeyError(f"métrica desconhecida: {mid}")
        m = self.metrics[mid]
        if view == "p90":
            if not m.per90:
                raise KeyError(f"{mid} não tem valor por 90 minutos")
            return m, "p90"
        if view:
            raise KeyError(f"vista desconhecida: {view}")
        return m, "total"

    def view_label(self, key: str) -> str:
        m, view = self.parse_view(key)
        return f"{m.name} por 90 minutos" if view == "p90" else m.name

    def view_unit(self, key: str) -> str:
        m, view = self.parse_view(key)
        return f"{m.unit}/90" if view == "p90" else m.unit

    def all_views(self) -> list[str]:
        out = []
        for m in self.metrics.values():
            out.append(m.id)
            if m.per90:
                out.append(f"{m.id}@p90")
        return out

    # ------------------------------------------------------------- posições
    @cached_property
    def metric_groups(self) -> dict[str, list[str]]:
        """Métrica → grupos de posição em que aparece no mapa."""
        out: dict[str, set[str]] = {m: set() for m in self.metrics}
        for g, sections in self.position_map.items():
            for _title, items in sections:
                for it in items:
                    out[it.partition("@")[0]].add(g)
        for mid, groups in self.custom_positions.items():
            out[mid] |= set(groups)
        order = list(self.groups)
        return {m: sorted(gs, key=order.index) for m, gs in out.items()}

    def required_fields(self, metric_id: str) -> list[set[str]]:
        """Campos necessários por cada fórmula alternativa."""
        m = self.metrics[metric_id]
        return [expr_fields(f, self.metrics, frozenset({metric_id})) for f in m.formulas]

    def formula_texts(self, metric_id: str) -> list[str]:
        m = self.metrics[metric_id]
        names = {k: v[0] for k, v in self.fields.items()}
        return [expr_text(f, self.metrics, names) for f in m.formulas]

    def describe(self, metric_id: str) -> dict[str, Any]:
        m = self.metrics[metric_id]
        return {
            **m.model_dump(),
            "category_label": CATEGORY_LABEL.get(m.category, m.category),
            "groups": self.metric_groups.get(metric_id, []),
            "formula_texts": self.formula_texts(metric_id),
            "source_fields": [sorted(s) for s in self.required_fields(metric_id)],
            "is_direct": "field" in m.formulas[0] and len(m.formulas) == 1,
        }


_DEFAULT: Catalog | None = None


def default_catalog() -> Catalog:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Catalog()
    return _DEFAULT
