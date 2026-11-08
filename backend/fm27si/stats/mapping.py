"""MetricMappingService: campos de um save → campos de origem canónicos.

Um perfil por fonte de dados. A leitura do save continua independente do catálogo: se um
campo do save não estiver aqui, vai para a descoberta automática (``discovery.py``).

``confidence``:
- ``direct``  o significado coincide com o campo canónico;
- ``assumed`` correspondência pelo nome, ainda não confirmada contra o ecrã do FM27.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldMapping:
    raw: str
    field: str
    confidence: str  # direct | assumed
    note: str = ""


# Chaves tal como ficam guardadas em season_stats (colunas + extra) pelo conector fmsave.
_FMSAVE: list[FieldMapping] = [
    FieldMapping("minutes", "minutes", "direct"),
    FieldMapping("starts", "starts", "direct"),
    FieldMapping("sub_appearances", "sub_appearances", "direct"),
    FieldMapping("goals", "goals", "direct"),
    FieldMapping("assists", "assists", "direct"),
    FieldMapping("yellow_cards", "yellow_cards", "direct"),
    FieldMapping("red_cards", "red_cards", "direct"),
    FieldMapping("clean_sheets", "clean_sheets", "direct"),
    FieldMapping("shots", "shots", "direct"),
    FieldMapping("shots_on_target", "shots_on_target", "direct"),
    FieldMapping("shots_outside_box", "shots_outside_box", "direct"),
    FieldMapping("penalties_scored", "penalty_goals", "direct"),
    FieldMapping("passes_attempted", "passes_attempted", "direct"),
    FieldMapping("passes_completed", "passes_completed", "direct"),
    FieldMapping("progressive_passes", "progressive_passes", "assumed", "O FM não diz se são tentados ou completos."),
    FieldMapping("key_passes", "key_passes", "direct"),
    FieldMapping("clear_cut_chances_created", "big_chances_created", "assumed", "Ocasiões claras criadas (FM: CCC)."),
    FieldMapping("crosses_attempted", "crosses_attempted", "direct"),
    FieldMapping("crosses_completed", "crosses_completed", "direct"),
    FieldMapping("dribbles", "dribbles_completed", "assumed", "FM 'Dribbles Made' = dribles bem-sucedidos."),
    FieldMapping("aerial_challenges_attempted", "aerial_duels", "direct"),
    FieldMapping("headers_won", "aerial_duels_won", "assumed", "Cabeceamentos ganhos usados como duelos aéreos ganhos."),
    FieldMapping("tackles_attempted", "tackles_attempted", "direct"),
    FieldMapping("tackles_completed", "tackles_won", "direct"),
    FieldMapping("interceptions", "interceptions", "direct"),
    FieldMapping("possession_won", "recoveries", "assumed", "FM 'Possession Won' usado como recuperações."),
    FieldMapping("possession_lost", "possession_lost", "direct"),
    FieldMapping("pressures_attempted", "pressures", "direct"),
    FieldMapping("pressures_completed", "pressures_successful", "direct"),
    FieldMapping("blocks", "blocks", "assumed"),
    FieldMapping("shots_blocked", "shots_blocked", "assumed", "No FM é uma estatística defensiva (remates bloqueados)."),
    FieldMapping("clearances", "clearances", "direct"),
    FieldMapping("fouls_made", "fouls_committed", "direct"),
    FieldMapping("fouls_against", "fouls_suffered", "direct"),
    FieldMapping("mistakes_leading_to_goal", "errors_leading_to_goal", "direct"),
    FieldMapping("goals_allowed", "goals_conceded", "direct"),
    FieldMapping("saves_held", "saves_held", "direct"),
    FieldMapping("saves_parried", "saves_parried", "direct"),
    FieldMapping("saves_tipped", "saves_tipped", "direct"),
    FieldMapping("shots_on_target_faced", "shots_on_target_faced", "direct"),
    FieldMapping("expected_goals_prevented", "goals_prevented", "direct"),
]

# Campos guardados que não são estatísticas de rendimento (não vão para a descoberta).
IGNORED_RAW = {"rated_appearances"}

PROFILES: dict[str, dict[str, FieldMapping]] = {"fmsave": {m.raw: m for m in _FMSAVE}}

# Que perfil usar para cada conector. A demonstração imita os campos do fmsave.
CONNECTOR_PROFILE = {"save_file": "fmsave", "synthetic": "fmsave", "live_memory": None}

PROFILE_LABEL = {"fmsave": "Save .fm (fmsave)"}


def profile_for(connector: str, custom: dict[str, FieldMapping] | None = None) -> tuple[str | None, dict[str, FieldMapping]]:
    name = CONNECTOR_PROFILE.get(connector)
    if name is None:
        return None, {}
    return name, {**PROFILES[name], **(custom or {})}
