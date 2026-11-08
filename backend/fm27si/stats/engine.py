"""DerivedMetricEngine: calcula todas as métricas do catálogo a partir dos campos de origem.

Vetorizado (numpy): uma matriz jogadores × campos (NaN = em falta) → matriz jogadores ×
métricas. O mesmo código serve um jogador ou 100 000.

Regras (secção 17 do pedido):
- campo em falta → NULL (nunca zero);
- soma/diferença com uma parcela em falta → NULL;
- divisão/percentagem com denominador 0 ou em falta → NULL;
- por 90 só com minutos > 0;
- percentagens impossíveis (< 0 ou > 100) → NULL e contadas como inválidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fm27si.stats.catalog import Catalog


@dataclass
class EngineResult:
    metric_ids: list[str]
    values: np.ndarray  # n × M (totais / valores)
    formula_used: np.ndarray  # n × M, índice da fórmula usada (-1 = nenhuma)
    invalid: dict[str, int] = field(default_factory=dict)  # métrica → linhas inválidas descartadas

    def column(self, metric_id: str) -> np.ndarray:
        return self.values[:, self.metric_ids.index(metric_id)]


class DerivedMetricEngine:
    def __init__(self, catalog: Catalog, field_keys: list[str]):
        self.catalog = catalog
        self.field_index = {k: i for i, k in enumerate(field_keys)}

    def compute(self, x: np.ndarray) -> EngineResult:
        n = x.shape[0]
        memo: dict[str, np.ndarray] = {}
        used: dict[str, np.ndarray] = {}
        invalid: dict[str, int] = {}
        nan = np.full(n, np.nan)

        def ev(expr: dict) -> np.ndarray:
            (op, arg), = expr.items()
            if op == "field":
                j = self.field_index.get(arg)
                return nan if j is None else x[:, j]
            if op == "metric":
                return metric(arg)
            vals = [ev(a) for a in arg]
            if op == "add":
                return np.sum(np.vstack(vals), axis=0)  # NaN se faltar uma parcela
            a, b = vals
            if op == "sub":
                return a - b
            with np.errstate(divide="ignore", invalid="ignore"):
                ok = ~np.isnan(b) & (b != 0) & ~np.isnan(a)
                q = np.where(ok, a / np.where(ok, b, 1.0), np.nan)
            return q * 100.0 if op == "pct" else q

        def metric(mid: str) -> np.ndarray:
            if mid in memo:
                return memo[mid]
            m = self.catalog.metrics[mid]
            out = np.full(n, np.nan)
            which = np.full(n, -1, dtype=np.int8)
            for i, f in enumerate(m.formulas):
                v = ev(f)
                take = np.isnan(out) & ~np.isnan(v)
                out = np.where(take, v, out)
                which = np.where(take, i, which)
            if m.type == "percentage":
                bad = (out < -1e-9) | (out > 100 + 1e-9)
                if bad.any():
                    invalid[mid] = int(bad.sum())
                    out = np.where(bad, np.nan, out)
                    which = np.where(bad, -1, which)
            elif m.type in ("count", "derived_count"):
                bad = out < -1e-9
                if bad.any():
                    invalid[mid] = int(bad.sum())
                    out = np.where(bad, np.nan, out)
            memo[mid] = out
            used[mid] = which
            return out

        ids = list(self.catalog.metrics)
        cols = [metric(m) for m in ids]
        values = np.column_stack(cols) if cols else np.zeros((n, 0))
        formula_used = np.column_stack([used[m] for m in ids]) if ids else np.zeros((n, 0), dtype=np.int8)
        return EngineResult(ids, values, formula_used, invalid)


def per90(total: np.ndarray, minutes: np.ndarray) -> np.ndarray:
    """(total / minutos) × 90 — NULL sem minutos válidos."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ok = ~np.isnan(minutes) & (minutes > 0) & ~np.isnan(total)
        return np.where(ok, total / np.where(ok, minutes, 1.0) * 90.0, np.nan)
