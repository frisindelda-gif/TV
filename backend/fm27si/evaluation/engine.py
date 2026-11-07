"""Motor de avaliação: atributos (1–20) → métricas → posições e funções (0–100).

Independente da base de dados e da interface. Funções puras e deterministas: o mesmo
``spec_hash`` com os mesmos atributos dá sempre o mesmo resultado.

Fórmulas
--------
1. Normalização de um atributo: ``n(a) = (a − 1) / 19 × 100`` (1 → 0, 20 → 100). Valores
   acima de 20 (saves editados) ficam limitados a 100. Atributo em falta = desconhecido,
   NUNCA zero. Atributos invertidos usam ``100 − n(a)``.
2. Métrica = média ponderada dos atributos DISPONÍVEIS:
   ``Σ wᵢ·n(aᵢ) / Σ wᵢ`` (soma só sobre os disponíveis).
   Cobertura = peso disponível / peso total. Se cobertura < ``min_coverage`` a métrica não
   é calculada (fica vazia).
3. Posição e função = média ponderada das MÉTRICAS calculadas, com a mesma regra.
   Cobertura = Σ (peso da métrica × cobertura da métrica) / Σ pesos.
4. Confiança: alta (cobertura ≥ 95 % e atributos verificados), média (≥ 80 % ou
   atributos não confirmados), baixa (< 80 % ou dados estimados/sintéticos).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import numpy as np

from fm27si.catalog import ATTRIBUTES
from fm27si.evaluation.spec import POSITIONS, EvaluationSpec, formula_text

Confidence = Literal["high", "medium", "low"]
ATTR_KEYS: tuple[str, ...] = tuple(ATTRIBUTES)
_ATTR_INDEX = {k: i for i, k in enumerate(ATTR_KEYS)}


@dataclass(frozen=True)
class CompiledSpec:
    spec: EvaluationSpec
    spec_hash: str
    metric_keys: tuple[str, ...]
    wp: np.ndarray  # métricas × atributos (pesos normais)
    wi: np.ndarray  # métricas × atributos (pesos invertidos)
    position_keys: tuple[str, ...]
    pw: np.ndarray  # posições × métricas
    role_keys: tuple[str, ...]  # só funções ativas
    rw: np.ndarray  # funções × métricas
    min_coverage: float


def compile_spec(spec: EvaluationSpec) -> CompiledSpec:
    return _compile_cached(spec.canonical_json())


@lru_cache(maxsize=16)
def _compile_cached(canonical: str) -> CompiledSpec:
    spec = EvaluationSpec.model_validate_json(canonical)
    mkeys = tuple(m.key for m in spec.metrics)
    midx = {k: i for i, k in enumerate(mkeys)}
    wp = np.zeros((len(mkeys), len(ATTR_KEYS)))
    wi = np.zeros_like(wp)
    for i, m in enumerate(spec.metrics):
        for a in m.attributes:
            (wi if a.invert else wp)[i, _ATTR_INDEX[a.attribute]] = a.weight
    pkeys = tuple(p.key for p in spec.positions)
    pw = np.zeros((len(pkeys), len(mkeys)))
    for i, p in enumerate(spec.positions):
        for w in p.metrics:
            pw[i, midx[w.metric]] = w.weight
    roles = [r for r in spec.roles if r.enabled]
    rkeys = tuple(r.key for r in roles)
    rw = np.zeros((len(rkeys), len(mkeys)))
    for i, r in enumerate(roles):
        for w in r.metrics:
            rw[i, midx[w.metric]] = w.weight
    return CompiledSpec(spec, spec.spec_hash(), mkeys, wp, wi, pkeys, pw, rkeys, rw, spec.min_coverage)


# ----------------------------------------------------------------------- cálculo

def attribute_matrix(rows: list[dict[str, int | None]]) -> np.ndarray:
    """Lista de dicionários de atributos → matriz n × 60 (NaN = em falta)."""
    out = np.full((len(rows), len(ATTR_KEYS)), np.nan)
    for i, r in enumerate(rows):
        for k, v in r.items():
            j = _ATTR_INDEX.get(k)
            if j is not None and v is not None and v >= 1:
                out[i, j] = v
    return out


def normalize(raw: np.ndarray) -> np.ndarray:
    """1–20 → 0–100. NaN mantém-se NaN (desconhecido, não zero)."""
    return np.clip((raw - 1.0) / 19.0 * 100.0, 0.0, 100.0)


def _weighted(values: np.ndarray, coverage_in: np.ndarray, w: np.ndarray, wi: np.ndarray | None, min_cov: float):
    """Média ponderada com dados em falta.

    values: n × k (NaN = em falta); coverage_in: n × k (cobertura de cada entrada, 0..1);
    w, wi: saídas × k. Devolve (scores, coverage) n × saídas.
    """
    known = ~np.isnan(values)
    v0 = np.where(known, values, 0.0)
    wt = w if wi is None else w + wi
    num = v0 @ w.T
    if wi is not None:
        num = num + (np.where(known, 100.0 - values, 0.0)) @ wi.T
    den = known.astype(float) @ wt.T
    total = wt.sum(axis=1)
    total = np.where(total > 0, total, np.nan)
    coverage = (np.where(known, coverage_in, 0.0) @ wt.T) / total
    with np.errstate(invalid="ignore", divide="ignore"):
        scores = np.where((den > 0) & (coverage >= min_cov - 1e-9), num / den, np.nan)
    return scores, np.nan_to_num(coverage)


@dataclass(frozen=True)
class BatchResult:
    metric_scores: np.ndarray
    metric_coverage: np.ndarray
    position_scores: np.ndarray
    position_coverage: np.ndarray
    role_scores: np.ndarray
    role_coverage: np.ndarray


def evaluate_batch(c: CompiledSpec, raw_attributes: np.ndarray) -> BatchResult:
    n = normalize(raw_attributes)
    attr_cov = (~np.isnan(n)).astype(float)
    ms, mc = _weighted(n, attr_cov, c.wp, c.wi, c.min_coverage)
    ps, pc = _weighted(ms, mc, c.pw, None, c.min_coverage)
    if len(c.role_keys):
        rs, rc = _weighted(ms, mc, c.rw, None, c.min_coverage)
    else:
        rs = rc = np.zeros((raw_attributes.shape[0], 0))
    return BatchResult(ms, mc, ps, pc, rs, rc)


def confidence(coverage: float, data_status: str | None) -> Confidence:
    if data_status == "estimate":
        return "low"
    if coverage < 0.8:
        return "low"
    if coverage < 0.95 or data_status not in ("verified",):
        return "medium"
    return "high"


def _r(x: float) -> float | None:
    return None if x is None or np.isnan(x) else round(float(x), 1)


# ------------------------------------------------------------------- um jogador

def evaluate_player(spec: EvaluationSpec, attrs: dict[str, int | None], data_status: str | None = None) -> dict:
    """Avaliação detalhada de um jogador (perfil, Position Lab). Usa o mesmo cálculo do lote."""
    c = compile_spec(spec)
    raw = attribute_matrix([attrs])
    res = evaluate_batch(c, raw)
    norm = normalize(raw)[0]

    metrics = []
    for i, m in enumerate(spec.metrics):
        used, missing = [], []
        for a in m.attributes:
            j = _ATTR_INDEX[a.attribute]
            if np.isnan(raw[0, j]):
                missing.append(a.attribute)
            else:
                nv = float(norm[j])
                used.append({
                    "attribute": a.attribute,
                    "value": int(raw[0, j]),
                    "normalized": round(nv, 1),
                    "weight": a.weight,
                    "invert": a.invert,
                })
        cov = float(res.metric_coverage[0, i])
        metrics.append({
            "key": m.key,
            "name": m.name,
            "category": m.category,
            "score": _r(res.metric_scores[0, i]),
            "coverage": round(cov, 3),
            "confidence": confidence(cov, data_status),
            "attributes": used,
            "missing": missing,
        })

    def block(keys, scores, cover, names):
        out = []
        for i, k in enumerate(keys):
            cov = float(cover[0, i])
            out.append({"key": k, "name": names[k], "score": _r(scores[0, i]), "coverage": round(cov, 3),
                        "confidence": confidence(cov, data_status)})
        return sorted(out, key=lambda x: (x["score"] is None, -(x["score"] or 0), x["key"]))

    pos_names = {k: POSITIONS[k][1] for k in c.position_keys}
    role_names = {r.key: r.name for r in spec.roles}
    return {
        "spec_hash": c.spec_hash,
        "metrics": metrics,
        "positions": block(c.position_keys, res.position_scores, res.position_coverage, pos_names),
        "roles": block(c.role_keys, res.role_scores, res.role_coverage, role_names),
    }


def describe_metric(spec: EvaluationSpec, key: str) -> dict:
    m = spec.metric(key)
    total = sum(a.weight for a in m.attributes)
    return {
        **m.model_dump(),
        "formula": formula_text(m),
        "attribute_shares": {a.attribute: round(a.weight / total, 4) for a in m.attributes},
        "used_by_positions": [p.key for p in spec.positions if any(w.metric == key for w in p.metrics)],
        "used_by_roles": [r.key for r in spec.roles if any(w.metric == key for w in r.metrics)],
    }
