"""MetricAvailabilityService / MetricValidationService.

Decide, para UMA importação, o estado de cada métrica do catálogo global. Nunca altera o
catálogo: uma métrica indisponível continua lá, apenas marcada.

AVAILABLE    existe diretamente no save (fórmula = um campo presente).
CALCULABLE   calculável a partir de campos presentes.
PARTIAL      só existem alguns dos campos necessários.
UNAVAILABLE  não existe informação suficiente.
INVALID      os campos existem mas os dados não permitem um cálculo fiável.
CUSTOM       métrica personalizada (aprovada a partir da descoberta) disponível neste save.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from fm27si.stats.catalog import Catalog
from fm27si.stats.data import RunStats

INVALID_SHARE = 0.01  # > 1 % de valores impossíveis → INVALID


def _leaf_fields(expr: dict) -> set[str]:
    (op, arg), = expr.items()
    if op == "field":
        return {arg}
    if op == "metric":
        return set()
    out: set[str] = set()
    for a in arg:
        out |= _leaf_fields(a)
    return out


def evaluate(cat: Catalog, present: set[str]) -> dict[str, dict[str, Any]]:
    """Estado estrutural (sem olhar para os valores) de todas as métricas."""
    memo: dict[str, dict[str, Any]] = {}

    def expr_ok(e: dict) -> tuple[bool, set[str], set[str]]:
        """(calculável, campos em falta, campos presentes) — expande métricas referidas."""
        (op, arg), = e.items()
        if op == "field":
            return (arg in present, set() if arg in present else {arg}, {arg} if arg in present else set())
        if op == "metric":
            st = status(arg)
            return st["computable"], set(st["missing"]), set(st["present"])
        oks, miss, pres = True, set(), set()
        for a in arg:
            ok, m, p = expr_ok(a)
            oks &= ok
            miss |= m
            pres |= p
        return oks, miss, pres

    def status(mid: str) -> dict[str, Any]:
        if mid in memo:
            return memo[mid]
        memo[mid] = {"computable": False, "missing": [], "present": [], "formula": None}  # proteção a ciclos
        m = cat.metrics[mid]
        closest: set[str] | None = None  # campos em falta na alternativa mais próxima
        all_present: set[str] = set()
        chosen = None
        for i, f in enumerate(m.formulas):
            ok, miss, pres = expr_ok(f)
            all_present |= pres
            if closest is None or (pres and len(miss) < len(closest)):
                closest = miss
            if ok and chosen is None:
                chosen = i
        memo[mid] = {
            "computable": chosen is not None,
            "formula": chosen,
            "direct": chosen == 0 and "field" in m.formulas[0],
            "missing": sorted(closest or set()) if chosen is None else [],
            "present": sorted(all_present),
        }
        return memo[mid]

    for mid in cat.metrics:
        status(mid)
    return memo


def compute_availability(cat: Catalog, rd: RunStats | None, connector: str) -> list[dict[str, Any]]:
    names = {k: v[0] for k, v in cat.fields.items()}
    if rd is None or rd.n == 0:
        reason = ("A leitura da memória (FMSuperScout) não inclui estatísticas de jogo."
                  if connector == "live_memory" else "Esta importação não contém estatísticas de jogo.")
        return [{"metric_key": mid, "status": "UNAVAILABLE", "formula_index": None, "players_with_value": 0,
                 "missing_fields": sorted(set().union(*cat.required_fields(mid)))[:12], "reason": reason}
                for mid in cat.metrics]

    present = {f for j, f in enumerate(rd.fields) if not np.isnan(rd.x[:, j]).all()}
    structural = evaluate(cat, present)
    out = []
    for mid, st in structural.items():
        m = cat.metrics[mid]
        col = rd.result.column(mid)
        with_value = int((~np.isnan(col)).sum())
        invalid_rows = rd.result.invalid.get(mid, 0)
        missing_labels = [names.get(f, f) for f in st["missing"]]
        if st["computable"]:
            texts = cat.formula_texts(mid)
            if with_value == 0:
                status, reason = "INVALID", "Os campos existem mas nenhum jogador tem um valor calculável (p.ex. denominadores sempre zero)."
            elif invalid_rows > INVALID_SHARE * max(with_value + invalid_rows, 1):
                status, reason = "INVALID", (f"{invalid_rows} valores impossíveis (p.ex. percentagem acima de 100 % "
                                             "ou contagem negativa): os dados não permitem um cálculo fiável.")
            elif not m.builtin:
                status, reason = "CUSTOM", "Métrica personalizada, validada a partir de um campo deste save."
            elif st["direct"]:
                status, reason = "AVAILABLE", "Campo existente no save."
            else:
                status, reason = "CALCULABLE", f"Calculada: {texts[st['formula']]}."
        elif st["present"]:
            status = "PARTIAL"
            reason = f"Existem alguns campos, mas faltam: {', '.join(missing_labels)}."
        else:
            status = "UNAVAILABLE"
            reason = (f"O save não contém {', '.join(missing_labels) or 'os campos necessários'} e não existem "
                      "dados suficientes para calcular este indicador.")
        out.append({"metric_key": mid, "status": status, "formula_index": st["formula"],
                    "players_with_value": with_value, "missing_fields": st["missing"], "reason": reason})
    return out


def field_inventory(rd: RunStats | None) -> list[dict[str, Any]]:
    if rd is None:
        return []
    out = []
    for raw, n in sorted(rd.raw_presence.items()):
        vals = np.array(rd.raw_values.get(raw, []), dtype=float)
        fm = rd.mapping.get(raw)
        out.append({
            "raw_key": raw, "data_source": rd.profile, "mapped_field": fm.field if fm else None,
            "confidence": fm.confidence if fm else None, "players_with_value": int(n),
            "min_value": float(vals.min()) if len(vals) else None, "max_value": float(vals.max()) if len(vals) else None,
            "mean_value": float(vals.mean()) if len(vals) else None,
            "integer_share": float(np.mean(np.isclose(vals, np.round(vals)))) if len(vals) else None,
        })
    return out
