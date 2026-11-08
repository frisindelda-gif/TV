"""SaveMetricDiscoveryService: campos estatísticos de um save que o catálogo não conhece.

Para cada campo não mapeado: identifica-o, infere significado provável, unidade, tipo,
posições, procura um equivalente no catálogo e cria uma PROPOSTA. Nada entra no catálogo
sem aprovação explícita (``approve``).
"""

from __future__ import annotations

import re
from typing import Any

from fm27si.stats.catalog import Catalog
from fm27si.stats.mapping import IGNORED_RAW

# Significados conhecidos de campos do fmsave (documentação do fmsave / nomes do FM).
KNOWN_HINTS: dict[str, dict[str, Any]] = {
    "expected_goals": {"name": "Golos esperados (xG)", "meaning": "Soma da probabilidade de golo dos remates do jogador.",
                       "unit": "goals", "type": "value", "category": "finishing", "groups": ["ST", "W", "AM", "WM"]},
    "non_penalty_expected_goals": {"name": "xG sem penáltis (npxG)", "meaning": "Golos esperados excluindo penáltis.",
                                   "unit": "goals", "type": "value", "category": "finishing", "groups": ["ST", "W", "AM", "WM"]},
    "expected_assists": {"name": "Assistências esperadas (xA)", "meaning": "Probabilidade de golo dos remates criados pelos passes do jogador.",
                         "unit": "goals", "type": "value", "category": "creation", "groups": ["AM", "W", "WM", "CM", "ST", "FB"]},
    "average_rating": {"name": "Nota média", "meaning": "Nota média do jogo (escala 1–10).", "unit": "rating",
                       "type": "value", "category": "general", "per90": False, "groups": []},
    "player_of_the_match": {"name": "Melhor em campo", "meaning": "Prémios de melhor em campo.", "unit": "count",
                            "type": "count", "category": "general", "per90": False, "groups": []},
    "goals_outside_box": {"name": "Golos de fora da área", "meaning": "Golos marcados de fora da área.",
                          "unit": "count", "type": "count", "category": "finishing", "groups": ["ST", "W", "AM", "CM"],
                          "equivalent": "goals"},
    "free_kick_shots": {"name": "Remates de livre", "meaning": "Remates diretos de livre.", "unit": "count",
                        "type": "count", "category": "finishing", "groups": ["AM", "W", "CM"]},
    "penalties_taken": {"name": "Penáltis marcados (tentados)", "meaning": "Penáltis batidos.", "unit": "count",
                        "type": "count", "category": "finishing", "groups": ["ST", "AM", "W"], "equivalent": "penalty_goals"},
    "open_play_key_passes": {"name": "Passes-chave em jogo corrido", "meaning": "Passes-chave excluindo bolas paradas.",
                             "unit": "count", "type": "count", "category": "creation", "groups": ["AM", "W", "WM", "CM"],
                             "equivalent": "key_passes"},
    "open_play_crosses_attempted": {"name": "Cruzamentos em jogo corrido tentados", "meaning": "Cruzamentos excluindo bolas paradas.",
                                    "unit": "count", "type": "count", "category": "creation", "groups": ["FB", "WM", "W"],
                                    "equivalent": "crosses_attempted"},
    "open_play_crosses_completed": {"name": "Cruzamentos em jogo corrido completos", "meaning": "Cruzamentos completos excluindo bolas paradas.",
                                    "unit": "count", "type": "count", "category": "creation", "groups": ["FB", "WM", "W"],
                                    "equivalent": "crosses_completed"},
    "offsides": {"name": "Foras de jogo", "meaning": "Vezes apanhado em fora de jogo.", "unit": "count", "type": "count",
                 "category": "finishing", "direction": "lower", "groups": ["ST", "W"]},
    "distance_km": {"name": "Distância percorrida", "meaning": "Quilómetros percorridos em jogo.", "unit": "km",
                    "type": "value", "category": "duels", "groups": ["CM", "DM", "FB", "WM", "W", "AM", "ST", "CB"]},
    "high_intensity_sprints": {"name": "Sprints de alta intensidade", "meaning": "Sprints de alta intensidade.",
                               "unit": "count", "type": "count", "category": "duels", "groups": ["FB", "WM", "W", "ST"]},
    "key_headers": {"name": "Cabeceamentos decisivos", "meaning": "Cabeceamentos que evitaram/originaram perigo.",
                    "unit": "count", "type": "count", "category": "duels", "groups": ["CB", "ST"]},
    "key_tackles": {"name": "Desarmes decisivos", "meaning": "Desarmes que travaram uma ocasião clara.",
                    "unit": "count", "type": "count", "category": "defending", "groups": ["CB", "FB", "DM"],
                    "equivalent": "tackles_won"},
}

_TOKENS_PT = {
    "goal": "golo", "goals": "golos", "shot": "remate", "shots": "remates", "pass": "passe", "passes": "passes",
    "cross": "cruzamento", "crosses": "cruzamentos", "tackle": "desarme", "tackles": "desarmes", "won": "ganhos",
    "lost": "perdidos", "attempted": "tentados", "completed": "completos", "key": "chave", "header": "cabeceamento",
    "headers": "cabeceamentos", "distance": "distância", "sprints": "sprints", "save": "defesa", "saves": "defesas",
    "expected": "esperados", "penalty": "penálti", "penalties": "penáltis", "box": "área", "open": "aberto",
    "play": "jogo", "fouls": "faltas", "offsides": "foras de jogo",
}


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t and t not in {"per", "of", "the", "a"}}


def _equivalent(raw: str, cat: Catalog) -> tuple[str | None, float]:
    rt = _tokens(raw)
    best, score = None, 0.0
    for mid in cat.metrics:
        mt = _tokens(mid)
        if not mt:
            continue
        j = len(rt & mt) / len(rt | mt)
        if j > score:
            best, score = mid, j
    return (best, round(score, 2)) if score >= 0.34 else (None, round(score, 2))


def infer(raw: str, sample: dict[str, Any], cat: Catalog) -> dict[str, Any]:
    hint = KNOWN_HINTS.get(raw, {})
    integer = (sample.get("integer_share") or 0) >= 0.999
    unit = hint.get("unit") or ("km" if raw.endswith("_km") else "percent" if raw.endswith(("_pct", "_percent"))
                                else "goals" if "expected" in raw else "count" if integer else "value")
    mtype = hint.get("type") or ("percentage" if unit == "percent" else "count" if integer else "value")
    eq = hint.get("equivalent")
    eq_score = 1.0 if eq else None
    if not eq:
        eq, eq_score = _equivalent(raw, cat)
    words = [_TOKENS_PT.get(t, t) for t in re.split(r"[_\W]+", raw) if t]
    return {
        "name": hint.get("name") or " ".join(words).capitalize(),
        "meaning": hint.get("meaning") or "Significado inferido apenas pelo nome do campo; confirmar no jogo.",
        "meaning_source": "known" if hint else "name_heuristic",
        "unit": unit,
        "type": mtype,
        "direct": True,
        "category": hint.get("category", "custom"),
        "direction": hint.get("direction", "higher"),
        "per90": hint.get("per90", mtype in ("count", "value")),
        "groups": hint.get("groups", []),
        "equivalent_metric": eq,
        "equivalent_similarity": eq_score,
        "recommendation": ("Já existe uma métrica semelhante no catálogo: avaliar se é a mesma coisa antes de aprovar."
                           if eq else "Sem equivalente no catálogo: candidata a nova métrica."),
    }


def unmapped_fields(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in inventory if f["mapped_field"] is None and f["raw_key"] not in IGNORED_RAW]
