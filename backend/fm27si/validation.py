"""Validação de CA, PA, atributos e campos base.

A validação nunca altera valores: devolve uma lista de problemas. O importador guarda os
problemas ao lado do registo, para que um valor suspeito fique visível em vez de ser
"corrigido" em silêncio.

Severidades:
- ``error``: valor impossível no FM (p.ex. CA 0 ou 250, atributo 0). Sinal forte de offset
  errado / layout mudado. O registo é importado mas marcado com ``quality = "error"``.
- ``warning``: possível mas invulgar (p.ex. atributo > 20 de um save editado, CA > PA).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fm27si.catalog import ATTRIBUTES, PLAYER_ATTRIBUTE_KEYS, PERSONALITY_KEYS, POSITION_KEYS
from fm27si.schemas import NormalizedPlayer

Severity = Literal["error", "warning"]

CA_MIN, CA_MAX = 1, 200
PA_MIN, PA_MAX = 1, 200
# A base de dados do FM pode guardar PA negativo (um intervalo, p.ex. -9 ou -95) em vez de
# um valor fixo. Aceitamos qualquer código negativo até -200 e guardamo-lo tal como vem; a
# tradução código→intervalo não é feita aqui (seria uma interpretação não verificada).
PA_RANGE_CODES = frozenset(range(-200, 0))
ATTR_MIN, ATTR_MAX = 1, 20
ATTR_EDITED_MAX = 25  # saves editados podem guardar até 125 bruto (= 25)
POS_MIN, POS_MAX = 1, 20


@dataclass(frozen=True)
class Issue:
    severity: Severity
    field: str
    code: str
    message: str
    value: object = None


def validate_player(p: NormalizedPlayer, *, expect_full_attributes: bool = True) -> list[Issue]:
    issues: list[Issue] = []

    def add(sev: Severity, field: str, code: str, msg: str, value: object = None) -> None:
        issues.append(Issue(sev, field, code, msg, value))

    # --- CA / PA ---
    if p.ca is None:
        add("warning", "ca", "missing", "CA não disponível na fonte")
    elif not CA_MIN <= p.ca <= CA_MAX:
        add("error", "ca", "out_of_range", f"CA fora de {CA_MIN}..{CA_MAX}", p.ca)

    if p.pa is None:
        if p.pa_range_code is None:
            add("warning", "pa", "missing", "PA não disponível na fonte")
        elif p.pa_range_code not in PA_RANGE_CODES:
            add("error", "pa_range_code", "invalid", "Código de intervalo de PA inválido", p.pa_range_code)
    elif not PA_MIN <= p.pa <= PA_MAX:
        add("error", "pa", "out_of_range", f"PA fora de {PA_MIN}..{PA_MAX}", p.pa)

    if (
        p.ca is not None
        and p.pa is not None
        and CA_MIN <= p.ca <= CA_MAX
        and PA_MIN <= p.pa <= PA_MAX
        and p.ca > p.pa
    ):
        add("warning", "ca", "ca_above_pa", "CA superior a PA (save editado ou leitura errada?)", (p.ca, p.pa))

    # --- Atributos ---
    unknown = set(p.attributes) - set(ATTRIBUTES)
    for k in sorted(unknown):
        add("error", f"attributes.{k}", "unknown_key", "Chave de atributo fora do catálogo")

    for k, v in p.attributes.items():
        if k in unknown:
            continue
        if not isinstance(v, int) or isinstance(v, bool):
            add("error", f"attributes.{k}", "not_int", "Atributo não inteiro", v)
        elif v < ATTR_MIN or v > ATTR_EDITED_MAX:
            add("error", f"attributes.{k}", "out_of_range", f"Atributo fora de {ATTR_MIN}..{ATTR_MAX}", v)
        elif v > ATTR_MAX:
            add("warning", f"attributes.{k}", "edited_scale", "Atributo acima de 20 (save editado?)", v)

    if expect_full_attributes:
        missing = [k for k in PLAYER_ATTRIBUTE_KEYS if k not in p.attributes]
        if missing:
            add("warning", "attributes", "incomplete", f"{len(missing)} atributos em falta", missing)
        missing_pers = [k for k in PERSONALITY_KEYS if k not in p.attributes]
        if missing_pers:
            add("warning", "attributes", "personality_incomplete", f"{len(missing_pers)} atributos de personalidade em falta", missing_pers)

    # Um bloco de atributos todo igual (p.ex. todos 1) é típico de offset errado.
    core = [p.attributes[k] for k in PLAYER_ATTRIBUTE_KEYS if k in p.attributes]
    if len(core) >= 20 and len(set(core)) == 1:
        add("error", "attributes", "constant_block", "Todos os atributos iguais — provável leitura errada", core[0])

    # --- Posições ---
    for k, v in p.positions.items():
        if k not in POSITION_KEYS:
            add("error", f"positions.{k}", "unknown_key", "Posição desconhecida")
        elif not POS_MIN <= v <= POS_MAX:
            add("error", f"positions.{k}", "out_of_range", f"Posição fora de {POS_MIN}..{POS_MAX}", v)

    # --- Campos base ---
    if p.age is not None and not 12 <= p.age <= 60:
        add("warning", "age", "implausible", "Idade improvável para um jogador", p.age)
    if p.height_cm is not None and p.height_cm != 0 and not 140 <= p.height_cm <= 215:
        add("warning", "height_cm", "implausible", "Altura improvável", p.height_cm)
    if p.market_value is not None and p.market_value < 0:
        add("error", "market_value", "negative", "Valor negativo", p.market_value)
    if p.contract and p.contract.wage_weekly is not None and p.contract.wage_weekly < 0:
        add("error", "contract.wage_weekly", "negative", "Salário negativo", p.contract.wage_weekly)
    if not p.name or p.name.strip() in {"", "?"}:
        add("warning", "name", "missing", "Nome em falta")

    return issues


def quality_of(issues: list[Issue]) -> str:
    if any(i.severity == "error" for i in issues):
        return "error"
    if any(i.severity == "warning" for i in issues):
        return "warning"
    return "ok"
