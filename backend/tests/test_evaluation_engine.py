"""Motor de avaliação: fórmulas, dados em falta, confiança, reprodutibilidade e cada posição."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from fm27si.catalog import ATTRIBUTES
from fm27si.evaluation.defaults import original_spec
from fm27si.evaluation.engine import (
    attribute_matrix,
    compile_spec,
    confidence,
    describe_metric,
    evaluate_batch,
    evaluate_player,
    normalize,
)
from fm27si.evaluation.spec import POSITIONS, EvaluationSpec

SPEC = original_spec()
MIRRORS = {"DR": "DL", "DL": "DR", "MR": "ML", "ML": "MR", "AMR": "AML", "AML": "AMR"}


def tiny_spec(**over) -> EvaluationSpec:
    """Especificação mínima para testar fórmulas com números redondos."""
    data = {
        "min_coverage": 0.6,
        "metrics": [
            {"key": "m_speed", "name": "Velocidade", "category": "physical",
             "attributes": [{"attribute": "pace", "weight": 3}, {"attribute": "acceleration", "weight": 1}]},
            {"key": "m_fragile", "name": "Robustez", "category": "physical",
             "attributes": [{"attribute": "injury_proneness", "weight": 1, "invert": True}]},
            {"key": "m_finish", "name": "Finalização", "category": "technical",
             "attributes": [{"attribute": "finishing", "weight": 1}]},
        ],
        "positions": [{"key": k, "metrics": [{"metric": "m_speed", "weight": 1}, {"metric": "m_finish", "weight": 3}]}
                      for k in POSITIONS],
        "roles": [{"key": "r_runner", "name": "Corredor", "positions": ["ST"],
                   "metrics": [{"metric": "m_speed", "weight": 1}]}],
    }
    data.update(over)
    return EvaluationSpec.model_validate(data)


def ev(spec, attrs, status="verified"):
    out = evaluate_player(spec, attrs, status)
    return (
        {m["key"]: m for m in out["metrics"]},
        {p["key"]: p for p in out["positions"]},
        {r["key"]: r for r in out["roles"]},
    )


# ------------------------------------------------------------------ fórmulas

def test_normalization_scale():
    raw = np.array([[1, 20, 10.5, 25, np.nan]], dtype=float)
    n = normalize(raw)[0]
    assert n[0] == 0 and n[1] == 100 and n[2] == pytest.approx(50)
    assert n[3] == 100  # save editado: limitado
    assert math.isnan(n[4])  # em falta continua desconhecido


def test_weighted_metric_formula():
    m, _, _ = ev(tiny_spec(), {"pace": 20, "acceleration": 1, "finishing": 10})
    # (3×100 + 1×0) / 4 = 75
    assert m["m_speed"]["score"] == 75.0 and m["m_speed"]["coverage"] == 1.0
    assert m["m_finish"]["score"] == pytest.approx(round(9 / 19 * 100, 1))


def test_inverted_attribute():
    m, _, _ = ev(tiny_spec(), {"injury_proneness": 20})
    assert m["m_fragile"]["score"] == 0.0
    m, _, _ = ev(tiny_spec(), {"injury_proneness": 1})
    assert m["m_fragile"]["score"] == 100.0


def test_missing_attribute_is_not_zero():
    # Só pace (peso 3 de 4): média dos disponíveis = 100, cobertura 0,75.
    m, _, _ = ev(tiny_spec(), {"pace": 20})
    assert m["m_speed"]["score"] == 100.0
    assert m["m_speed"]["coverage"] == 0.75
    assert m["m_speed"]["missing"] == ["acceleration"]


def test_below_min_coverage_is_not_calculated():
    m, p, r = ev(tiny_spec(), {"acceleration": 20})  # cobertura 0,25 < 0,6
    assert m["m_speed"]["score"] is None
    assert m["m_finish"]["score"] is None
    assert p["ST"]["score"] is None and r["r_runner"]["score"] is None


def test_position_and_role_formula():
    _, p, r = ev(tiny_spec(), {"pace": 20, "acceleration": 20, "finishing": 1})
    # posição: (1×100 + 3×0) / 4 = 25 ; função: só velocidade = 100
    assert p["ST"]["score"] == 25.0 and r["r_runner"]["score"] == 100.0


def test_position_coverage_combines_metric_coverage():
    _, p, _ = ev(tiny_spec(), {"pace": 20, "finishing": 20})
    # velocidade com cobertura 0,75 (peso 1), finalização 1,0 (peso 3): (0,75 + 3) / 4
    assert p["ST"]["coverage"] == pytest.approx(0.9375, abs=1e-3)
    assert p["ST"]["confidence"] == "medium"


def test_confidence_levels():
    assert confidence(1.0, "verified") == "high"
    assert confidence(1.0, "unconfirmed") == "medium"
    assert confidence(0.9, "verified") == "medium"
    assert confidence(0.7, "verified") == "low"
    assert confidence(1.0, "estimate") == "low"


def test_batch_equals_single_player_and_is_deterministic():
    rng = np.random.default_rng(1)
    rows = [{k: int(v) for k, v in zip(ATTRIBUTES, rng.integers(1, 21, len(ATTRIBUTES)), strict=True)} for _ in range(30)]
    c = compile_spec(SPEC)
    a = evaluate_batch(c, attribute_matrix(rows))
    b = evaluate_batch(c, attribute_matrix(rows))
    assert np.array_equal(a.position_scores, b.position_scores, equal_nan=True)
    for i in (0, 7, 29):
        single = {p["key"]: p["score"] for p in evaluate_player(SPEC, rows[i])["positions"]}
        for j, k in enumerate(c.position_keys):
            assert single[k] == round(float(a.position_scores[i, j]), 1)


def test_scores_bounded_0_100():
    c = compile_spec(SPEC)
    lo = evaluate_batch(c, attribute_matrix([dict.fromkeys(ATTRIBUTES, 1)]))
    hi = evaluate_batch(c, attribute_matrix([dict.fromkeys(ATTRIBUTES, 20)]))
    # tudo no mínimo → 0 exceto métricas com atributos invertidos
    assert np.nanmin(lo.metric_scores) >= 0 and np.nanmax(hi.metric_scores) <= 100
    assert np.nanmax(hi.position_scores) <= 100 and np.nanmin(lo.position_scores) >= 0


def test_disabled_role_not_computed():
    spec = original_spec()
    spec.roles[0].enabled = False
    keys = {r["key"] for r in evaluate_player(spec, dict.fromkeys(ATTRIBUTES, 10))["roles"]}
    assert spec.roles[0].key not in keys and len(keys) == len(spec.roles) - 1


def test_spec_hash_changes_with_weights():
    a = original_spec()
    b = original_spec()
    assert a.spec_hash() == b.spec_hash()
    b.metrics[0].attributes[0].weight += 1
    assert a.spec_hash() != b.spec_hash()


def test_describe_metric_has_formula_and_usage():
    d = describe_metric(SPEC, "finishing")
    assert "n(finishing)" in d["formula"] and sum(d["attribute_shares"].values()) == pytest.approx(1)
    assert "ST" in d["used_by_positions"] and "inside_forward" in d["used_by_roles"]


# ------------------------------------------------------------- validação

@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d["metrics"][0]["attributes"].append({"attribute": "magia", "weight": 1}), "atributo desconhecido"),
        (lambda d: d["metrics"][0]["attributes"].__setitem__(0, {"attribute": "pace", "weight": 0}), "greater than 0"),
        (lambda d: d["positions"].pop(), "faltam modelos"),
        (lambda d: d["roles"][0]["metrics"].append({"metric": "nao_existe", "weight": 1}), "métricas desconhecidas"),
        (lambda d: d["metrics"].append(dict(d["metrics"][0])), "repetidas"),
        (lambda d: d["roles"][0].__setitem__("positions", ["XX"]), "posições desconhecidas"),
    ],
)
def test_spec_validation(mutate, msg):
    data = SPEC.model_dump()
    mutate(data)
    with pytest.raises(ValidationError, match=msg):
        EvaluationSpec.model_validate(data)


def test_original_spec_covers_all_requested_positions_and_roles():
    assert {p.key for p in SPEC.positions} == set(POSITIONS)
    assert len(POSITIONS) == 12
    assert {r.name for r in SPEC.roles} == {
        "Guarda-redes líbero", "Defesa central com bola", "Defesa lateral ofensivo", "Médio recuperador de bolas",
        "Construtor de jogo recuado", "Médio área a área", "Mezzala", "Organizador avançado", "Extremo invertido",
        "Avançado interior", "Avançado pressionante", "Falso nove", "Homem-alvo",
    }
    assert all(r.availability == "unconfirmed" for r in SPEC.roles)  # nada confirmado sem o jogo
    cats = {m.category for m in SPEC.metrics}
    assert cats == {"technical", "mental", "physical", "tactical", "position_specific"}


# ------------------------------------------------------- uma posição de cada vez

def _importance(position: str) -> dict[str, float]:
    """Peso efetivo de cada atributo numa posição (Σ peso da métrica × quota do atributo)."""
    pos = SPEC.position(position)
    total = sum(w.weight for w in pos.metrics)
    out: dict[str, float] = {}
    for w in pos.metrics:
        m = SPEC.metric(w.metric)
        mt = sum(a.weight for a in m.attributes)
        for a in m.attributes:
            if not a.invert:
                out[a.attribute] = out.get(a.attribute, 0) + w.weight / total * a.weight / mt
    return out


def archetype(position: str, top: int = 10) -> dict[str, int]:
    imp = _importance(position)
    best = sorted(imp, key=imp.get, reverse=True)[:top]
    attrs = dict.fromkeys(ATTRIBUTES, 7)
    attrs.update(dict.fromkeys(best, 18))
    return attrs


@pytest.mark.parametrize("position", list(POSITIONS))
def test_each_position_archetype_ranks_its_position_first(position):
    _, p, _ = ev(SPEC, archetype(position))
    scores = {k: v["score"] for k, v in p.items()}
    best = max(scores.values())
    allowed = {position, MIRRORS.get(position)}
    winners = {k for k, v in scores.items() if v == best}
    assert winners & allowed, f"{position}: melhor foi {winners} ({scores})"
    assert scores[position] >= 70


@pytest.mark.parametrize("position", list(POSITIONS))
def test_each_position_improves_with_its_key_attribute(position):
    base = dict.fromkeys(ATTRIBUTES, 10)
    key = max(_importance(position), key=_importance(position).get)
    _, p1, _ = ev(SPEC, base)
    _, p2, _ = ev(SPEC, {**base, key: 18})
    assert p2[position]["score"] > p1[position]["score"]


@pytest.mark.parametrize("position", list(POSITIONS))
def test_each_position_all_20_is_100_and_all_1_is_0(position):
    _, hi, _ = ev(SPEC, dict.fromkeys(ATTRIBUTES, 20))
    assert hi[position]["score"] >= 96  # só "durabilidade" (lesões invertidas) puxa para baixo
    _, lo, _ = ev(SPEC, {**dict.fromkeys(ATTRIBUTES, 1), "injury_proneness": 20})
    assert lo[position]["score"] == 0.0


@pytest.mark.parametrize("role", [r.key for r in SPEC.roles])
def test_each_role_responds_to_its_metrics(role):
    r = SPEC.role(role)
    top_metric = max(r.metrics, key=lambda w: w.weight).metric
    attrs = dict.fromkeys(ATTRIBUTES, 8)
    _, _, before = ev(SPEC, attrs)
    for a in SPEC.metric(top_metric).attributes:
        if not a.invert:
            attrs[a.attribute] = 18
    _, _, after = ev(SPEC, attrs)
    assert after[role]["score"] > before[role]["score"]


def test_weights_documentation_is_up_to_date():
    from pathlib import Path

    from fm27si.evaluation.defaults import ORIGINAL_NAME
    from fm27si.evaluation.docs import weights_markdown

    doc = Path(__file__).resolve().parents[2] / "docs" / "07-PESOS.md"
    expected = weights_markdown(SPEC, f"07 — Pesos: {ORIGINAL_NAME}")
    assert doc.read_text(encoding="utf-8") == expected, "corra: fm27si weights-doc"
