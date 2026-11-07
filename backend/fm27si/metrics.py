"""Métricas de desempenho e percentis por posição.

Tudo aqui é DERIVADO de estatísticas lidas (nunca estimado): taxas por 90 minutos,
percentagens e percentis em relação aos jogadores do mesmo grupo de posição na mesma
importação. Um valor sem denominador válido (p.ex. 0 remates) fica ``None``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from fm27si.schemas import SeasonStats

MIN_MINUTES_FOR_PERCENTILE = 450  # ~5 jogos completos; abaixo disso a amostra é pequena demais

Group = Literal["attack", "creation", "defence", "physical", "goalkeeping", "general"]


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    group: Group
    unit: Literal["per90", "pct", "total", "rating", "minutes"]
    num: str  # campo (ou expressão simples "a+b") do numerador
    den: str | None = None  # para percentagens; None em per90/total
    higher_is_better: bool = True
    gk_only: bool = False
    outfield_only: bool = False


METRICS: tuple[MetricDef, ...] = (
    # Ataque
    MetricDef("goals_90", "Golos /90", "attack", "per90", "goals", outfield_only=True),
    MetricDef("xg_90", "xG /90", "attack", "per90", "expected_goals", outfield_only=True),
    MetricDef("npxg_90", "xG sem penáltis /90", "attack", "per90", "non_penalty_expected_goals", outfield_only=True),
    MetricDef("shots_90", "Remates /90", "attack", "per90", "shots", outfield_only=True),
    MetricDef("shots_on_target_pct", "Remates à baliza %", "attack", "pct", "shots_on_target", "shots", outfield_only=True),
    MetricDef("conversion_pct", "Conversão %", "attack", "pct", "goals", "shots", outfield_only=True),
    MetricDef("goals_minus_xg", "Golos − xG", "attack", "total", "goals-expected_goals", outfield_only=True),
    # Criação
    MetricDef("assists_90", "Assistências /90", "creation", "per90", "assists", outfield_only=True),
    MetricDef("xa_90", "xA /90", "creation", "per90", "expected_assists", outfield_only=True),
    MetricDef("key_passes_90", "Passes decisivos /90", "creation", "per90", "key_passes", outfield_only=True),
    MetricDef("ccc_90", "Ocasiões claras criadas /90", "creation", "per90", "clear_cut_chances_created", outfield_only=True),
    MetricDef("progressive_passes_90", "Passes progressivos /90", "creation", "per90", "progressive_passes"),
    MetricDef("pass_pct", "Passes certos %", "creation", "pct", "passes_completed", "passes_attempted"),
    MetricDef("cross_pct", "Cruzamentos certos %", "creation", "pct", "crosses_completed", "crosses_attempted", outfield_only=True),
    MetricDef("dribbles_90", "Dribles /90", "creation", "per90", "dribbles", outfield_only=True),
    # Defesa
    MetricDef("tackles_90", "Desarmes ganhos /90", "defence", "per90", "tackles_completed", outfield_only=True),
    MetricDef("tackle_pct", "Desarmes ganhos %", "defence", "pct", "tackles_completed", "tackles_attempted", outfield_only=True),
    MetricDef("interceptions_90", "Interceções /90", "defence", "per90", "interceptions", outfield_only=True),
    MetricDef("possession_won_90", "Posse ganha /90", "defence", "per90", "possession_won", outfield_only=True),
    MetricDef("pressures_90", "Pressões ganhas /90", "defence", "per90", "pressures_completed", outfield_only=True),
    MetricDef("headers_won_90", "Cabeceamentos ganhos /90", "defence", "per90", "headers_won", outfield_only=True),
    MetricDef("aerial_pct", "Duelos aéreos ganhos %", "defence", "pct", "headers_won", "aerial_challenges_attempted", outfield_only=True),
    MetricDef("clearances_90", "Alívios /90", "defence", "per90", "clearances", outfield_only=True),
    MetricDef("blocks_90", "Bloqueios /90", "defence", "per90", "blocks", outfield_only=True),
    # Físico / disciplina
    MetricDef("distance_90", "Distância (km) /90", "physical", "per90", "distance_km"),
    MetricDef("sprints_90", "Sprints /90", "physical", "per90", "high_intensity_sprints", outfield_only=True),
    MetricDef("possession_lost_90", "Posse perdida /90", "physical", "per90", "possession_lost", higher_is_better=False),
    MetricDef("fouls_90", "Faltas cometidas /90", "physical", "per90", "fouls_made", higher_is_better=False),
    MetricDef("mistakes", "Erros que deram golo", "physical", "total", "mistakes_leading_to_goal", higher_is_better=False),
    # Guarda-redes
    MetricDef("save_pct", "Defesas %", "goalkeeping", "pct", "saves_held+saves_parried+saves_tipped", "shots_on_target_faced", gk_only=True),
    MetricDef("xgp_90", "Golos evitados (xGP) /90", "goalkeeping", "per90", "expected_goals_prevented", gk_only=True),
    MetricDef("goals_allowed_90", "Golos sofridos /90", "goalkeeping", "per90", "goals_allowed", higher_is_better=False, gk_only=True),
    MetricDef("clean_sheet_pct", "Jogos sem sofrer %", "goalkeeping", "pct", "clean_sheets", "appearances", gk_only=True),
    # Geral
    MetricDef("average_rating", "Nota média", "general", "rating", "average_rating"),
    MetricDef("minutes", "Minutos", "general", "minutes", "minutes"),
    MetricDef("appearances", "Jogos", "general", "total", "appearances"),
)
METRIC_BY_KEY = {m.key: m for m in METRICS}

POSITION_GROUPS: dict[str, str] = {
    "GK": "Guarda-redes",
    "CB": "Defesas centrais",
    "FB": "Laterais",
    "DM": "Médios defensivos",
    "CM": "Médios centro",
    "WM": "Extremos / alas",
    "AM": "Médios ofensivos",
    "ST": "Pontas-de-lança",
}
_POS_TO_GROUP = {
    "GK": "GK", "SW": "CB", "DC": "CB", "DL": "FB", "DR": "FB", "WBL": "FB", "WBR": "FB",
    "DM": "DM", "MC": "CM", "ML": "WM", "MR": "WM", "AML": "WM", "AMR": "WM", "AMC": "AM", "ST": "ST",
}

# Métricas mostradas no radar de cada grupo (as que mais distinguem a função).
RADAR: dict[str, tuple[str, ...]] = {
    "GK": ("save_pct", "xgp_90", "goals_allowed_90", "clean_sheet_pct", "pass_pct", "progressive_passes_90", "average_rating"),
    "CB": ("headers_won_90", "aerial_pct", "interceptions_90", "tackles_90", "clearances_90", "pass_pct", "progressive_passes_90", "average_rating"),
    "FB": ("tackles_90", "interceptions_90", "key_passes_90", "cross_pct", "dribbles_90", "progressive_passes_90", "distance_90", "average_rating"),
    "DM": ("tackles_90", "interceptions_90", "possession_won_90", "pass_pct", "progressive_passes_90", "pressures_90", "distance_90", "average_rating"),
    "CM": ("pass_pct", "progressive_passes_90", "key_passes_90", "xa_90", "tackles_90", "possession_won_90", "distance_90", "average_rating"),
    "WM": ("goals_90", "xg_90", "xa_90", "key_passes_90", "dribbles_90", "cross_pct", "sprints_90", "average_rating"),
    "AM": ("goals_90", "xg_90", "xa_90", "key_passes_90", "ccc_90", "dribbles_90", "pass_pct", "average_rating"),
    "ST": ("goals_90", "npxg_90", "shots_90", "shots_on_target_pct", "conversion_pct", "xa_90", "headers_won_90", "average_rating"),
}

_EXCLUDED_KINDS = {"international", "calendar_year_overall", "calendar_year_international", "non_competitive"}


def position_group(natural: list[str], accomplished: list[str] | None = None) -> str | None:
    for p in [*natural, *(accomplished or [])]:
        g = _POS_TO_GROUP.get(p)
        if g:
            return g
    return None


def aggregate(lines: list[SeasonStats]) -> dict[str, float] | None:
    """Junta as linhas da época: usa 'overall' quando existe, senão soma as competições de clube."""
    overall = [s for s in lines if s.competition_kind == "overall"]
    use = overall or [s for s in lines if s.competition_kind not in _EXCLUDED_KINDS]
    if not use:
        return None
    tot: dict[str, float] = defaultdict(float)
    present: set[str] = set()
    rating_w = 0.0
    rating_sum = 0.0
    for s in use:
        base = s.model_dump(exclude={"season", "competition_kind", "club_name", "extra", "average_rating"})
        for k, v in [*base.items(), *s.extra.items()]:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                tot[k] += v
                present.add(k)
        apps = (s.starts or 0) + (s.sub_appearances or 0)
        if s.average_rating is not None and apps:
            w = s.extra.get("rated_appearances") or apps
            rating_sum += s.average_rating * float(w)
            rating_w += float(w)
    out = {k: tot[k] for k in present}
    out["appearances"] = float((tot.get("starts") or 0) + (tot.get("sub_appearances") or 0))
    if rating_w:
        out["average_rating"] = rating_sum / rating_w
    return out


def _expr(totals: dict[str, float], expr: str) -> float | None:
    if "-" in expr:
        a, b = expr.split("-", 1)
        va, vb = totals.get(a), totals.get(b)
        return None if va is None or vb is None else va - vb
    parts = expr.split("+")
    vals = [totals.get(p) for p in parts]
    return None if any(v is None for v in vals) else float(sum(vals))  # type: ignore[arg-type]


def compute(lines: list[SeasonStats], group: str | None) -> tuple[dict[str, float | None], float]:
    """Devolve (métricas, minutos). Métricas sem dados ficam None."""
    totals = aggregate(lines)
    if not totals:
        return {}, 0.0
    minutes = totals.get("minutes") or 0.0
    is_gk = group == "GK"
    out: dict[str, float | None] = {}
    for m in METRICS:
        if (m.gk_only and not is_gk) or (m.outfield_only and is_gk):
            continue
        num = _expr(totals, m.num)
        if num is None:
            out[m.key] = None
            continue
        if m.unit == "per90":
            out[m.key] = round(num * 90 / minutes, 3) if minutes > 0 else None
        elif m.unit == "pct":
            den = _expr(totals, m.den or "")
            out[m.key] = round(100 * num / den, 1) if den else None
        elif m.unit == "rating":
            out[m.key] = round(num, 2)
        else:
            out[m.key] = round(num, 2)
    return out, minutes


def percentiles(rows: list[tuple[int, str | None, float, dict[str, float | None]]]) -> dict[int, dict[str, float]]:
    """Percentil (0–100) de cada métrica dentro do grupo de posição, só com amostra suficiente.

    ``rows``: (snapshot_id, grupo, minutos, métricas). Percentil = % de pares abaixo + metade
    dos empatados. Para métricas em que menos é melhor, o percentil é invertido.
    """
    by_group: dict[str, list[tuple[int, dict[str, float | None]]]] = defaultdict(list)
    for sid, group, minutes, vals in rows:
        if group and minutes >= MIN_MINUTES_FOR_PERCENTILE:
            by_group[group].append((sid, vals))
    out: dict[int, dict[str, float]] = defaultdict(dict)
    for _group, members in by_group.items():
        if len(members) < 5:
            continue  # grupo pequeno demais para comparar
        for m in METRICS:
            if m.unit == "minutes":
                continue
            vals = sorted(v[m.key] for _, v in members if v.get(m.key) is not None)  # type: ignore[misc]
            n = len(vals)
            if n < 5:
                continue
            for sid, v in members:
                x = v.get(m.key)
                if x is None:
                    continue
                below = _count_below(vals, x)
                equal = _count_equal(vals, x)
                pct = 100.0 * (below + 0.5 * equal) / n
                out[sid][m.key] = round(pct if m.higher_is_better else 100.0 - pct, 1)
    return out


def _count_below(sorted_vals: list[float], x: float) -> int:
    import bisect  # noqa: PLC0415

    return bisect.bisect_left(sorted_vals, x)


def _count_equal(sorted_vals: list[float], x: float) -> int:
    import bisect  # noqa: PLC0415

    return bisect.bisect_right(sorted_vals, x) - bisect.bisect_left(sorted_vals, x)
