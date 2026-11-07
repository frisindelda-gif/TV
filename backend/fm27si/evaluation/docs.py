"""Gera a documentação dos pesos a partir da especificação (fonte única de verdade)."""

from __future__ import annotations

from fm27si.catalog import ATTRIBUTES
from fm27si.evaluation.spec import POSITIONS, EvaluationSpec, formula_text

_CAT = {"technical": "Técnicas", "mental": "Mentais", "physical": "Físicas", "tactical": "Táticas",
        "position_specific": "Específicas da posição"}


def weights_markdown(spec: EvaluationSpec, title: str) -> str:
    out = [
        f"# {title}",
        "",
        "> Gerado automaticamente por `fm27si weights-doc` a partir do modelo original.",
        "> Não editar à mão. **Proposta inicial**: a especificação \"Position Metrics\" do",
        "> utilizador ainda não foi recebida; estes pesos serão substituídos por ela.",
        "",
        f"Hash do modelo: `{spec.spec_hash()}` · cobertura mínima: {spec.min_coverage:.0%}",
        "",
        "Normalização: `n(a) = (a − 1) / 19 × 100`. Métrica = média ponderada dos atributos",
        "disponíveis; posição/função = média ponderada das métricas calculadas. Percentagens",
        "abaixo = quota de cada peso no total.",
        "",
        "## Métricas",
    ]
    for cat, label in _CAT.items():
        ms = [m for m in spec.metrics if m.category == cat]
        if not ms:
            continue
        out += ["", f"### {label}", ""]
        for m in ms:
            total = sum(a.weight for a in m.attributes)
            scope = ", ".join(POSITIONS[p][0] for p in m.positions) if m.positions else "todas"
            attrs = ", ".join(
                f"{ATTRIBUTES[a.attribute].label}{' (invertido)' if a.invert else ''} {a.weight / total:.0%}"
                for a in m.attributes
            )
            out.append(f"- **{m.name}** (`{m.key}`; posições: {scope}) — {m.description}  ")
            out.append(f"  Atributos: {attrs}  ")
            out.append(f"  Fórmula: `{formula_text(m)}`")
    out += ["", "## Posições", "", "| Posição | Métricas (quota do peso) |", "|---|---|"]
    names = {m.key: m.name for m in spec.metrics}
    for p in spec.positions:
        total = sum(w.weight for w in p.metrics)
        ws = ", ".join(f"{names[w.metric]} {w.weight / total:.0%}" for w in sorted(p.metrics, key=lambda x: -x.weight))
        out.append(f"| {POSITIONS[p.key][0]} — {POSITIONS[p.key][1]} | {ws} |")
    out += ["", "## Funções táticas", "",
            "Todas por confirmar no FM27 instalado (`availability: unconfirmed`).", "",
            "| Função | Posições | Métricas (quota do peso) |", "|---|---|---|"]
    for r in spec.roles:
        total = sum(w.weight for w in r.metrics)
        ws = ", ".join(f"{names[w.metric]} {w.weight / total:.0%}" for w in sorted(r.metrics, key=lambda x: -x.weight))
        pos = ", ".join(POSITIONS[p][0] for p in r.positions)
        out.append(f"| {r.name} | {pos} | {ws} |")
    return "\n".join(out) + "\n"
