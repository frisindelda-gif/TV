"""Catálogo global de métricas (dados).

Fonte: especificação "Statistical Scouting" do utilizador. Todas as métricas do documento
estão aqui, independentemente de um save as fornecer. Disponibilidade é decidida por save.

Uma métrica é definida uma vez e reutilizada em várias posições. "Golos" e "Golos por 90
minutos" são a MESMA métrica com duas vistas (``total`` e ``p90``): nunca há duas fórmulas
para a mesma coisa.

Expressões (fórmulas)
    {"field": f}          campo de origem
    {"metric": m}         outra métrica (com as suas próprias alternativas)
    {"add": [e, ...]}     soma — NULL se faltar qualquer parcela
    {"sub": [a, b]}       a − b
    {"div": [a, b]}       a / b — NULL se b for 0 ou NULL
    {"pct": [a, b]}       100 × a / b — NULL se b for 0 ou NULL
``formulas`` é uma lista por ordem de preferência: a primeira que der valor é usada.
"""

from __future__ import annotations

from typing import Any


def F(name: str) -> dict:
    return {"field": name}


def M(name: str) -> dict:
    return {"metric": name}


def ADD(*e: dict) -> dict:
    return {"add": list(e)}


def SUB(a: dict, b: dict) -> dict:
    return {"sub": [a, b]}


def DIV(a: dict, b: dict) -> dict:
    return {"div": [a, b]}


def PCT(a: dict, b: dict) -> dict:
    return {"pct": [a, b]}


METRICS: list[dict[str, Any]] = []


def _add(id: str, name: str, category: str, description: str, *, type: str, unit: str, formulas: list[dict],
         per90: bool, percentile: bool = True, direction: str = "higher", composite: bool = True,
         alt_name: str | None = None, composed: bool = False, min_minutes: int | None = None) -> None:
    METRICS.append({
        "id": id, "name": name, "alt_name": alt_name, "description": description, "category": category,
        "type": type, "unit": unit, "formulas": formulas, "per90": per90, "percentile": percentile,
        "direction": direction, "composite": composite, "composed": composed,
        "eligibility": {"min_minutes": min_minutes},
    })


def count(id: str, name: str, category: str, description: str, *, field: str | None = None, alt: list[dict] | None = None,
          direction: str = "higher", per90: bool = True, alt_name: str | None = None, unit: str = "count",
          composite: bool = True, percentile: bool = True) -> None:
    _add(id, name, category, description, type="count", unit=unit, formulas=[F(field or id), *(alt or [])],
         per90=per90, direction=direction, alt_name=alt_name, composite=composite, percentile=percentile)


def pct(id: str, name: str, category: str, description: str, num: dict, den: dict, *, direction: str = "higher",
        alt_name: str | None = None) -> None:
    _add(id, name, category, description, type="percentage", unit="percent", formulas=[PCT(num, den)], per90=False,
         direction=direction, alt_name=alt_name)


def derived(id: str, name: str, category: str, description: str, expr: dict, *, type: str = "derived_count",
            unit: str = "count", per90: bool = True, direction: str = "higher", composed: bool = False,
            first_field: str | None = None, alt_name: str | None = None) -> None:
    formulas = ([F(first_field)] if first_field else []) + [expr]
    _add(id, name, category, description, type=type, unit=unit, formulas=formulas, per90=per90, direction=direction,
         composed=composed, alt_name=alt_name)


LOWER = "lower"

# ---------------------------------------------------------------- tempo de jogo
count("minutes", "Minutos jogados", "general", "Minutos em campo.", per90=False, unit="minutes", composite=False)
count("appearances", "Jogos", "general", "Jogos disputados.", per90=False, unit="matches", composite=False,
      alt=[ADD(F("starts"), F("sub_appearances"))])
count("starts", "Jogos como titular", "general", "Jogos como titular.", per90=False, unit="matches", composite=False)

# ------------------------------------------------------------------ guarda-redes
count("saves", "Defesas", "goalkeeping", "Remates enquadrados defendidos.",
      alt=[ADD(F("saves_held"), F("saves_parried"), F("saves_tipped"))])
count("shots_on_target_faced", "Remates enquadrados enfrentados", "goalkeeping", "Remates à baliza enfrentados.",
      direction=LOWER)
pct("save_pct", "Percentagem de defesas", "goalkeeping", "Defesas / remates enquadrados enfrentados × 100.",
    M("saves"), M("shots_on_target_faced"))
count("goals_conceded", "Golos sofridos", "goalkeeping", "Golos sofridos.", direction=LOWER)
count("clean_sheets", "Jogos sem sofrer golos", "goalkeeping", "Jogos sem sofrer golos.", per90=False, unit="matches")
pct("clean_sheet_pct", "Percentagem de jogos sem sofrer golos", "goalkeeping",
    "Jogos sem sofrer golos / jogos disputados × 100.", M("clean_sheets"), M("appearances"))
count("penalties_faced", "Penáltis enfrentados", "goalkeeping", "Penáltis enfrentados.", per90=False)
count("penalties_saved", "Penáltis defendidos", "goalkeeping", "Penáltis defendidos.", per90=False)
pct("penalty_save_pct", "Percentagem de penáltis defendidos", "goalkeeping",
    "Penáltis defendidos / penáltis enfrentados × 100.", M("penalties_saved"), M("penalties_faced"))
_add("goals_prevented", "Golos evitados", "goalkeeping",
     "Golos esperados dos remates enquadrados enfrentados menos golos sofridos (só se existir xG sofrido).",
     type="value", unit="goals", per90=True,
     formulas=[F("goals_prevented"), SUB(F("xg_on_target_faced"), M("goals_conceded"))])
count("claims", "Saídas", "goalkeeping", "Saídas da baliza.", alt_name="Saídas totais")
count("claims_successful", "Saídas bem-sucedidas", "goalkeeping", "Saídas que resolveram o lance.")
pct("claim_success_pct", "Percentagem de saídas bem-sucedidas", "goalkeeping",
    "Saídas bem-sucedidas / saídas × 100.", M("claims_successful"), M("claims"))
count("crosses_faced", "Cruzamentos enfrentados", "goalkeeping", "Cruzamentos enfrentados.")
count("crosses_claimed", "Cruzamentos intercetados", "goalkeeping", "Cruzamentos agarrados ou socados.")
pct("cross_claim_pct", "Percentagem de cruzamentos intercetados", "goalkeeping",
    "Cruzamentos intercetados / cruzamentos enfrentados × 100.", M("crosses_claimed"), M("crosses_faced"))

# ----------------------------------------------------------------------- passe
count("passes_attempted", "Passes tentados", "passing", "Passes tentados.")
count("passes_completed", "Passes completos", "passing", "Passes completos.")
pct("pass_pct", "Percentagem de passes completos", "passing", "Passes completos / passes tentados × 100.",
    M("passes_completed"), M("passes_attempted"), alt_name="Precisão de passe")
count("long_passes_attempted", "Passes longos tentados", "passing", "Passes longos tentados.")
count("long_passes_completed", "Passes longos completos", "passing", "Passes longos completos.")
pct("long_pass_pct", "Percentagem de passes longos completos", "passing",
    "Passes longos completos / passes longos tentados × 100.", M("long_passes_completed"), M("long_passes_attempted"))
count("progressive_passes", "Passes progressivos", "passing", "Passes progressivos.")
count("progressive_passes_completed", "Passes progressivos completos", "passing", "Passes progressivos completos.")
count("final_third_passes", "Passes para o último terço", "passing", "Passes para o último terço.")
count("final_third_passes_completed", "Passes para o último terço completos", "passing", "Passes completos para o último terço.")
count("progression_zone_passes", "Passes para zonas de progressão", "passing", "Passes para zonas de progressão.")
count("line_breaking_passes", "Passes que quebram linhas", "passing", "Passes que ultrapassam linhas adversárias.",
      alt_name="Passes que ultrapassam linhas adversárias")
count("vertical_passes", "Passes verticais", "passing", "Passes verticais.")
count("vertical_passes_completed", "Passes verticais completos", "passing", "Passes verticais completos.")
count("passes_received", "Passes recebidos", "passing", "Passes recebidos.")
count("first_time_passes", "Passes de primeira", "passing", "Passes ao primeiro toque.")
count("one_twos", "Paredes e combinações concluídas", "passing", "Combinações curtas concluídas.")

# --------------------------------------------------------------------- criação
count("key_passes", "Passes-chave", "creation", "Passes que resultam num remate.")
count("chances_created", "Ocasiões criadas", "creation", "Ocasiões de golo criadas.")
count("big_chances_created", "Grandes ocasiões criadas", "creation", "Ocasiões claras criadas.")
count("assists", "Assistências", "creation", "Assistências.")
count("decisive_passes", "Passes decisivos", "creation", "Passes que deixam um colega a finalizar com vantagem.")
count("box_passes", "Passes para a área", "creation", "Passes que entram na área adversária.",
      alt_name="Passes para a área adversária")
count("through_balls", "Passes em profundidade", "creation", "Passes nas costas da defesa.")
count("crosses_attempted", "Cruzamentos tentados", "creation", "Cruzamentos tentados.")
count("crosses_completed", "Cruzamentos completos", "creation", "Cruzamentos completos.")
pct("cross_pct", "Percentagem de cruzamentos completos", "creation",
    "Cruzamentos completos / cruzamentos tentados × 100.", M("crosses_completed"), M("crosses_attempted"))
count("box_crosses", "Cruzamentos para a área", "creation", "Cruzamentos para a área.")
count("low_crosses", "Cruzamentos rasteiros", "creation", "Cruzamentos rasteiros.")
count("danger_zone_crosses", "Cruzamentos para zonas de perigo", "creation", "Cruzamentos para a zona de finalização.",
      alt_name="Cruzamentos em zonas de perigo")

# ------------------------------------------------------------- toques/condução
count("touches", "Toques na bola", "participation", "Toques na bola.", alt_name="Toques totais")
count("att_half_touches", "Toques no meio-campo ofensivo", "participation", "Toques no meio-campo adversário.")
count("box_touches", "Toques na área adversária", "participation", "Toques na área adversária.", alt_name="Toques na área")
count("carries", "Conduções", "progression", "Conduções de bola.", alt_name="Conduções totais")
count("progressive_carries", "Conduções progressivas", "progression", "Conduções progressivas.")
count("carry_distance", "Distância em condução", "progression", "Distância percorrida com a bola.", unit="metres")
count("carries_into_box", "Conduções para a área", "progression", "Conduções que entram na área.")
count("line_breaking_carries", "Conduções que quebram linhas", "progression", "Conduções que ultrapassam linhas.")
count("dribbles_attempted", "Dribles tentados", "progression", "Dribles tentados.")
count("dribbles_completed", "Dribles completos", "progression", "Dribles bem-sucedidos.")
pct("dribble_success_pct", "Percentagem de dribles bem-sucedidos", "progression",
    "Dribles completos / dribles tentados × 100.", M("dribbles_completed"), M("dribbles_attempted"))
count("players_beaten", "Adversários ultrapassados", "progression", "Adversários ultrapassados.")

# ------------------------------------------------------------------- defesa
count("defensive_actions", "Ações defensivas", "defending", "Ações defensivas totais.", alt_name="Ações defensivas totais")
count("defensive_actions_successful", "Ações defensivas bem-sucedidas", "defending", "Ações defensivas bem-sucedidas.")
count("tackles_attempted", "Desarmes tentados", "defending", "Desarmes tentados.")
count("tackles_won", "Desarmes ganhos", "defending", "Desarmes ganhos.")
pct("tackle_success_pct", "Percentagem de desarmes ganhos", "defending",
    "Desarmes ganhos / desarmes tentados × 100.", M("tackles_won"), M("tackles_attempted"))
count("interceptions", "Interceções", "defending", "Interceções.")
count("cuts", "Cortes", "defending", "Cortes.")
count("clearances", "Alívios", "defending", "Alívios.")
count("shots_blocked", "Remates bloqueados", "defending", "Remates adversários bloqueados.")
count("blocks", "Bloqueios", "defending", "Passes ou cruzamentos bloqueados.")
count("opponent_passes_intercepted", "Passes adversários intercetados", "defending",
      "Passes do adversário intercetados (se a fonte distinguir das interceções).", alt_name="Passes intercetados")
count("recoveries", "Recuperações", "defending", "Recuperações de posse.", alt_name="Recuperações totais")
count("recoveries_def_half", "Recuperações no meio-campo defensivo", "defending", "Recuperações no próprio meio-campo.",
      alt_name="Recuperações defensivas")
count("recoveries_att_half", "Recuperações no meio-campo ofensivo", "defending", "Recuperações no meio-campo adversário.",
      alt_name="Recuperações ofensivas")
derived("recoveries_plus_interceptions", "Recuperações + interceções", "defending",
        "Indicador COMPOSTO: soma de duas métricas diferentes; ver componentes em separado.",
        ADD(M("recoveries"), M("interceptions")), composed=True)
derived("tackles_won_plus_interceptions", "Desarmes ganhos + interceções", "defending",
        "Indicador COMPOSTO: soma de duas métricas diferentes; ver componentes em separado.",
        ADD(M("tackles_won"), M("interceptions")), composed=True)

# ------------------------------------------------------------------- duelos
count("def_duels", "Duelos defensivos disputados", "duels", "Duelos defensivos disputados.")
count("def_duels_won", "Duelos defensivos ganhos", "duels", "Duelos defensivos ganhos.")
pct("def_duel_pct", "Percentagem de duelos defensivos ganhos", "duels",
    "Duelos defensivos ganhos / disputados × 100.", M("def_duels_won"), M("def_duels"))
count("off_duels", "Duelos ofensivos disputados", "duels", "Duelos ofensivos disputados.")
count("off_duels_won", "Duelos ofensivos ganhos", "duels", "Duelos ofensivos ganhos.")
pct("off_duel_pct", "Percentagem de duelos ofensivos ganhos", "duels",
    "Duelos ofensivos ganhos / disputados × 100.", M("off_duels_won"), M("off_duels"))
count("aerial_duels", "Duelos aéreos disputados", "duels", "Duelos aéreos disputados.", alt_name="Bolas aéreas disputadas")
count("aerial_duels_won", "Duelos aéreos ganhos", "duels", "Duelos aéreos ganhos.", alt_name="Bolas aéreas ganhas")
pct("aerial_duel_pct", "Percentagem de duelos aéreos ganhos", "duels",
    "Duelos aéreos ganhos / disputados × 100.", M("aerial_duels_won"), M("aerial_duels"))
count("duels", "Duelos disputados", "duels", "Duelos totais disputados.", alt_name="Duelos totais disputados")
count("duels_won", "Duelos ganhos", "duels", "Duelos totais ganhos.", alt_name="Duelos totais ganhos")
pct("duel_pct", "Percentagem de duelos ganhos", "duels", "Duelos ganhos / disputados × 100.",
    M("duels_won"), M("duels"), alt_name="Percentagem de duelos totais ganhos")

# --------------------------------------------------------------- disciplina
count("fouls_committed", "Faltas cometidas", "discipline", "Faltas cometidas.", direction=LOWER)
count("fouls_suffered", "Faltas sofridas", "discipline", "Faltas sofridas.")
count("yellow_cards", "Cartões amarelos", "discipline", "Cartões amarelos.", direction=LOWER)
count("red_cards", "Cartões vermelhos", "discipline", "Cartões vermelhos.", direction=LOWER)

# ------------------------------------------------------------------- pressão
count("pressures", "Pressões realizadas", "pressing", "Pressões realizadas.")
count("pressures_successful", "Pressões bem-sucedidas", "pressing", "Pressões bem-sucedidas.")
pct("pressure_success_pct", "Percentagem de pressões bem-sucedidas", "pressing",
    "Pressões bem-sucedidas / realizadas × 100.", M("pressures_successful"), M("pressures"))
count("pressures_att_half", "Pressões no meio-campo adversário", "pressing", "Pressões no meio-campo adversário.")
count("pressures_def_half", "Pressões no meio-campo defensivo", "pressing", "Pressões no próprio meio-campo.")
count("recoveries_after_pressure", "Recuperações após pressão", "pressing", "Recuperações após pressão.")
count("tackles_after_pressure", "Desarmes após pressão", "pressing", "Desarmes após pressão.")
count("interceptions_after_pressure", "Interceções após pressão", "pressing", "Interceções após pressão.")

# --------------------------------------------------------- segurança na posse
count("possession_lost", "Perdas de bola", "possession", "Perdas de posse.", direction=LOWER)
count("possession_lost_def_half", "Perdas de bola no meio-campo defensivo", "possession",
      "Perdas de posse no próprio meio-campo.", direction=LOWER, alt_name="Perdas de posse no meio-campo defensivo")
count("passes_intercepted", "Passes intercetados (sofridos)", "possession",
      "Passes do jogador intercetados pelo adversário.", direction=LOWER, alt_name="Passes intercetados")
count("errors_leading_to_shot", "Erros que originam remates", "possession", "Erros que dão remate.", direction=LOWER)
count("errors_leading_to_goal", "Erros que originam golos", "possession", "Erros que dão golo.", direction=LOWER)
count("control_errors", "Erros de controlo", "possession", "Falhas de receção/controlo.", direction=LOWER)

# ---------------------------------------------------------------- finalização
count("goals", "Golos", "finishing", "Golos marcados.")
count("penalty_goals", "Golos de penálti", "finishing", "Golos de penálti.")
derived("non_penalty_goals", "Golos sem penálti", "finishing", "Golos − golos de penálti.",
        SUB(M("goals"), M("penalty_goals")), first_field="non_penalty_goals")
count("set_piece_goals", "Golos de bola parada", "finishing", "Golos de bola parada.")
count("headed_goals", "Golos de cabeça", "finishing", "Golos de cabeça.")
count("right_foot_goals", "Golos com o pé direito", "finishing", "Golos com o pé direito.")
count("left_foot_goals", "Golos com o pé esquerdo", "finishing", "Golos com o pé esquerdo.")
count("shots", "Remates", "finishing", "Remates.")
count("shots_on_target", "Remates enquadrados", "finishing", "Remates à baliza.")
pct("shot_on_target_pct", "Percentagem de remates enquadrados", "finishing",
    "Remates enquadrados / remates × 100.", M("shots_on_target"), M("shots"))
derived("shots_inside_box", "Remates dentro da área", "finishing", "Remates − remates fora da área.",
        SUB(M("shots"), M("shots_outside_box")), first_field="shots_inside_box")
count("shots_outside_box", "Remates fora da área", "finishing", "Remates de fora da área.")
pct("conversion_pct", "Percentagem de conversão", "finishing", "Golos / remates × 100.", M("goals"), M("shots"),
    alt_name="Percentagem de conversão de remates")
count("big_chances_missed", "Grandes ocasiões falhadas", "finishing", "Ocasiões claras desperdiçadas.", direction=LOWER)
derived("minutes_per_goal", "Minutos por golo", "finishing", "Minutos jogados / golos (sem golos = indefinido).",
        DIV(M("minutes"), M("goals")), type="ratio", unit="minutes", per90=False, direction=LOWER)
derived("shots_per_goal", "Remates por golo", "finishing", "Remates / golos (sem golos = indefinido).",
        DIV(M("shots"), M("goals")), type="ratio", unit="ratio", per90=False, direction=LOWER)
derived("goal_contributions", "Contribuições para golo", "finishing", "Golos + assistências.",
        ADD(M("goals"), M("assists")))
derived("goal_participations", "Participações em golos", "finishing",
        "Golos + assistências + pré-assistências (exige pré-assistências na fonte).",
        ADD(M("goals"), M("assists"), F("second_assists")))

METRIC_IDS = [m["id"] for m in METRICS]

# ---------------------------------------------------------------------------
# Mapa por posição (grupos do documento) → secções → métricas/vistas.
# "x" = vista principal da métrica (total ou valor); "x@p90" = por 90 minutos.
# ---------------------------------------------------------------------------

POSITION_GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "GK": ("Guarda-redes (GR)", ("GK",)),
    "CB": ("Defesa-central (DC)", ("DC",)),
    "FB": ("Defesa-direito e defesa-esquerdo (DD/DE)", ("DR", "DL")),
    "DM": ("Médio-defensivo (MDC)", ("DM",)),
    "CM": ("Médio-centro (MC)", ("MC",)),
    "WM": ("Médio-direito e médio-esquerdo (MD/ME)", ("MR", "ML")),
    "AM": ("Médio-ofensivo (MO)", ("AMC",)),
    "W": ("Extremo-direito e extremo-esquerdo (AD/AE)", ("AMR", "AML")),
    "ST": ("Ponta de lança (PL)", ("ST",)),
}

_POSSESSION_FULL = ["possession_lost", "possession_lost@p90", "possession_lost_def_half", "passes_intercepted",
                    "errors_leading_to_shot", "errors_leading_to_goal"]
_POSSESSION_SHORT = ["possession_lost", "possession_lost@p90", "passes_intercepted", "errors_leading_to_shot"]

POSITION_MAP: dict[str, list[tuple[str, list[str]]]] = {
    "GK": [
        ("A. Defesa da baliza", ["saves", "saves@p90", "shots_on_target_faced", "save_pct", "goals_conceded",
                                  "goals_conceded@p90", "clean_sheets", "clean_sheet_pct", "penalties_faced",
                                  "penalties_saved", "penalty_save_pct", "goals_prevented"]),
        ("B. Jogo aéreo e controlo da área", ["claims", "claims_successful", "claim_success_pct", "crosses_faced",
                                               "crosses_claimed", "cross_claim_pct", "aerial_duels", "aerial_duels_won",
                                               "aerial_duel_pct"]),
        ("C. Distribuição e construção", ["passes_attempted", "passes_completed", "pass_pct", "long_passes_attempted",
                                           "long_passes_completed", "long_pass_pct", "progressive_passes",
                                           "progressive_passes_completed", "final_third_passes",
                                           "final_third_passes_completed", "progression_zone_passes",
                                           "line_breaking_passes"]),
        ("D. Erros e perdas", ["possession_lost", "possession_lost@p90", "errors_leading_to_shot",
                               "errors_leading_to_goal", "control_errors", "passes_intercepted"]),
    ],
    "CB": [
        ("A. Ações defensivas", ["defensive_actions", "defensive_actions@p90", "defensive_actions_successful",
                                 "defensive_actions_successful@p90", "tackles_attempted", "tackles_won",
                                 "tackle_success_pct", "interceptions", "interceptions@p90", "cuts", "cuts@p90",
                                 "clearances", "clearances@p90", "shots_blocked", "shots_blocked@p90",
                                 "opponent_passes_intercepted", "recoveries", "recoveries@p90", "recoveries_def_half",
                                 "recoveries_att_half"]),
        ("B. Duelos", ["def_duels", "def_duels_won", "def_duel_pct", "aerial_duels", "aerial_duels_won",
                       "aerial_duel_pct", "duels", "duels_won", "duel_pct", "fouls_committed", "fouls_committed@p90",
                       "yellow_cards", "red_cards"]),
        ("C. Construção e distribuição", ["passes_attempted", "passes_completed", "pass_pct", "long_passes_attempted",
                                           "long_passes_completed", "long_pass_pct", "progressive_passes",
                                           "progressive_passes_completed", "final_third_passes",
                                           "final_third_passes_completed", "vertical_passes",
                                           "vertical_passes_completed", "key_passes", "chances_created", "assists",
                                           "assists@p90", "box_passes", "line_breaking_passes"]),
        ("D. Progressão com bola", ["carries", "progressive_carries", "progressive_carries@p90", "carry_distance",
                                    "dribbles_attempted", "dribbles_completed", "dribble_success_pct",
                                    "players_beaten", "line_breaking_carries"]),
        ("E. Segurança na posse", _POSSESSION_FULL),
        ("F. Contribuição ofensiva", ["goals", "goals@p90", "shots", "shots_on_target", "shot_on_target_pct",
                                      "box_touches", "set_piece_goals", "headed_goals"]),
    ],
    "FB": [
        ("A. Contribuição defensiva", ["defensive_actions", "defensive_actions@p90", "defensive_actions_successful",
                                       "recoveries", "recoveries@p90", "tackles_attempted", "tackles_won",
                                       "tackle_success_pct", "interceptions", "cuts", "clearances", "shots_blocked",
                                       "def_duels", "def_duels_won", "def_duel_pct", "aerial_duels",
                                       "aerial_duels_won", "aerial_duel_pct", "fouls_committed", "yellow_cards",
                                       "red_cards"]),
        ("B. Construção e progressão", ["passes_attempted", "passes_completed", "pass_pct", "progressive_passes",
                                        "progressive_passes_completed", "final_third_passes", "box_passes",
                                        "key_passes", "progressive_carries", "progressive_carries@p90",
                                        "dribbles_attempted", "dribbles_completed", "dribble_success_pct",
                                        "players_beaten"]),
        ("C. Criação ofensiva", ["crosses_attempted", "crosses_completed", "cross_pct", "box_crosses", "low_crosses",
                                 "danger_zone_crosses", "chances_created", "big_chances_created", "assists",
                                 "assists@p90", "decisive_passes", "box_passes"]),
        ("D. Finalização", ["goals", "goals@p90", "shots", "shots_on_target", "shot_on_target_pct",
                            "shots_inside_box", "box_touches", "set_piece_goals"]),
        ("E. Segurança na posse", _POSSESSION_FULL),
    ],
    "DM": [
        ("A. Recuperação e proteção defensiva", ["recoveries", "recoveries@p90", "recoveries_def_half",
                                                 "recoveries_att_half", "tackles_attempted", "tackles_won",
                                                 "tackle_success_pct", "interceptions", "interceptions@p90", "cuts",
                                                 "blocks", "defensive_actions", "defensive_actions_successful",
                                                 "shots_blocked", "opponent_passes_intercepted"]),
        ("B. Duelos e capacidade física", ["def_duels", "def_duels_won", "def_duel_pct", "aerial_duels",
                                           "aerial_duels_won", "aerial_duel_pct", "duels", "duels_won", "duel_pct",
                                           "fouls_committed", "fouls_suffered", "yellow_cards", "red_cards"]),
        ("C. Pressão e recuperação após pressão", ["pressures", "pressures_successful", "pressure_success_pct",
                                                   "pressures_att_half", "pressures_def_half",
                                                   "recoveries_after_pressure", "tackles_after_pressure",
                                                   "interceptions_after_pressure"]),
        ("D. Distribuição", ["passes_attempted", "passes_completed", "pass_pct", "long_passes_attempted",
                             "long_passes_completed", "long_pass_pct", "progressive_passes",
                             "progressive_passes_completed", "vertical_passes", "vertical_passes_completed",
                             "final_third_passes", "box_passes", "line_breaking_passes", "key_passes",
                             "chances_created"]),
        ("E. Progressão com bola", ["carries", "progressive_carries", "progressive_carries@p90", "dribbles_attempted",
                                    "dribbles_completed", "dribble_success_pct", "players_beaten"]),
        ("F. Contribuição ofensiva", ["goals", "goals@p90", "assists", "assists@p90", "shots", "shots_on_target",
                                      "box_touches", "chances_created"]),
        ("G. Segurança na posse", ["possession_lost", "possession_lost@p90", "possession_lost_def_half",
                                   "passes_intercepted", "errors_leading_to_shot"]),
    ],
    "CM": [
        ("A. Distribuição e construção", ["passes_attempted", "passes_completed", "pass_pct", "long_passes_attempted",
                                           "long_passes_completed", "long_pass_pct", "progressive_passes",
                                           "progressive_passes_completed", "vertical_passes",
                                           "vertical_passes_completed", "final_third_passes", "box_passes",
                                           "line_breaking_passes", "key_passes", "chances_created",
                                           "big_chances_created", "assists", "decisive_passes"]),
        ("B. Progressão", ["carries", "progressive_carries", "progressive_carries@p90", "dribbles_attempted",
                           "dribbles_completed", "dribble_success_pct", "players_beaten", "carry_distance"]),
        ("C. Recuperação e defesa", ["recoveries", "recoveries@p90", "recoveries_def_half", "recoveries_att_half",
                                     "tackles_attempted", "tackles_won", "tackle_success_pct", "interceptions", "cuts",
                                     "defensive_actions", "defensive_actions_successful", "shots_blocked",
                                     "def_duels", "def_duels_won", "def_duel_pct", "aerial_duels", "aerial_duels_won",
                                     "aerial_duel_pct"]),
        ("D. Pressão", ["pressures", "pressures_successful", "pressure_success_pct", "recoveries_after_pressure",
                        "pressures_att_half", "pressures_def_half"]),
        ("E. Contribuição ofensiva", ["goals", "goals@p90", "assists", "assists@p90", "non_penalty_goals", "shots",
                                      "shots_on_target", "shot_on_target_pct", "chances_created",
                                      "big_chances_created", "box_touches"]),
        ("F. Segurança na posse", ["touches", "possession_lost", "possession_lost@p90", "possession_lost_def_half",
                                   "passes_intercepted", "errors_leading_to_shot"]),
    ],
    "WM": [
        ("A. Criação ofensiva", ["chances_created", "chances_created@p90", "big_chances_created", "key_passes",
                                 "key_passes@p90", "assists", "assists@p90", "box_passes", "through_balls",
                                 "crosses_attempted", "crosses_completed", "cross_pct", "box_crosses", "low_crosses",
                                 "danger_zone_crosses"]),
        ("B. Capacidade de desequilíbrio", ["dribbles_attempted", "dribbles_completed", "dribble_success_pct",
                                            "players_beaten", "players_beaten@p90", "fouls_suffered",
                                            "fouls_suffered@p90", "carries", "progressive_carries",
                                            "progressive_carries@p90"]),
        ("C. Finalização", ["goals", "goals@p90", "non_penalty_goals", "shots", "shots_on_target",
                            "shot_on_target_pct", "shots_inside_box", "shots_outside_box", "conversion_pct",
                            "box_touches"]),
        ("D. Progressão e circulação", ["passes_attempted", "passes_completed", "pass_pct", "progressive_passes",
                                        "progressive_passes_completed", "final_third_passes", "box_passes",
                                        "key_passes"]),
        ("E. Contribuição defensiva", ["recoveries", "recoveries@p90", "tackles_attempted", "tackles_won",
                                       "tackle_success_pct", "interceptions", "cuts", "pressures",
                                       "pressures_successful", "pressure_success_pct", "def_duels", "def_duels_won",
                                       "aerial_duels", "aerial_duels_won"]),
        ("F. Segurança na posse", _POSSESSION_SHORT),
    ],
    "AM": [
        ("A. Criação e criatividade", ["key_passes", "key_passes@p90", "chances_created", "chances_created@p90",
                                       "big_chances_created", "assists", "assists@p90", "through_balls", "box_passes",
                                       "final_third_passes", "line_breaking_passes", "decisive_passes",
                                       "crosses_attempted", "crosses_completed"]),
        ("B. Progressão e desequilíbrio", ["carries", "progressive_carries", "progressive_carries@p90",
                                           "dribbles_attempted", "dribbles_completed", "dribble_success_pct",
                                           "players_beaten", "fouls_suffered", "fouls_suffered@p90"]),
        ("C. Finalização", ["goals", "goals@p90", "non_penalty_goals", "shots", "shots_on_target",
                            "shot_on_target_pct", "shots_inside_box", "shots_outside_box", "conversion_pct",
                            "box_touches", "big_chances_missed"]),
        ("D. Participação no jogo", ["touches", "att_half_touches", "box_touches", "passes_received",
                                     "passes_attempted", "passes_completed", "pass_pct"]),
        ("E. Pressão e contribuição defensiva", ["pressures", "pressures_successful", "pressure_success_pct",
                                                 "recoveries", "recoveries@p90", "tackles_won", "interceptions",
                                                 "def_duels", "def_duels_won", "fouls_committed"]),
        ("F. Segurança na posse", _POSSESSION_SHORT),
    ],
    "W": [
        ("A. Capacidade de desequilíbrio", ["dribbles_attempted", "dribbles_completed", "dribble_success_pct",
                                            "players_beaten", "players_beaten@p90", "fouls_suffered",
                                            "fouls_suffered@p90", "carries", "progressive_carries",
                                            "progressive_carries@p90", "carries_into_box"]),
        ("B. Criação ofensiva", ["chances_created", "chances_created@p90", "big_chances_created", "key_passes",
                                 "key_passes@p90", "assists", "assists@p90", "through_balls", "box_passes",
                                 "crosses_attempted", "crosses_completed", "cross_pct", "low_crosses",
                                 "danger_zone_crosses"]),
        ("C. Finalização", ["goals", "goals@p90", "non_penalty_goals", "shots", "shots_on_target",
                            "shot_on_target_pct", "shots_inside_box", "shots_outside_box", "conversion_pct",
                            "box_touches", "big_chances_missed"]),
        ("D. Progressão", ["passes_attempted", "passes_completed", "pass_pct", "progressive_passes",
                           "progressive_passes_completed", "final_third_passes", "progressive_carries",
                           "line_breaking_passes"]),
        ("E. Contribuição defensiva", ["recoveries", "recoveries@p90", "tackles_attempted", "tackles_won",
                                       "tackle_success_pct", "interceptions", "pressures", "pressures_successful",
                                       "pressure_success_pct", "def_duels", "def_duels_won", "fouls_committed"]),
        ("F. Segurança na posse", _POSSESSION_SHORT),
    ],
    "ST": [
        ("A. Finalização", ["goals", "goals@p90", "non_penalty_goals", "penalty_goals", "shots", "shots@p90",
                            "shots_on_target", "shots_on_target@p90", "shot_on_target_pct", "shots_inside_box",
                            "shots_outside_box", "conversion_pct", "minutes_per_goal", "big_chances_missed",
                            "big_chances_missed@p90", "box_touches", "headed_goals", "right_foot_goals",
                            "left_foot_goals"]),
        ("B. Criação ofensiva", ["assists", "assists@p90", "key_passes", "key_passes@p90", "chances_created",
                                 "big_chances_created", "box_passes", "through_balls", "decisive_passes"]),
        ("C. Participação e ligação", ["touches", "box_touches", "passes_received", "passes_attempted",
                                       "passes_completed", "pass_pct", "final_third_passes", "progressive_passes",
                                       "first_time_passes", "one_twos"]),
        ("D. Mobilidade e progressão", ["dribbles_attempted", "dribbles_completed", "dribble_success_pct", "carries",
                                        "progressive_carries", "fouls_suffered", "fouls_suffered@p90"]),
        ("E. Jogo aéreo e duelos", ["aerial_duels", "aerial_duels_won", "aerial_duel_pct", "off_duels",
                                    "off_duels_won", "off_duel_pct", "duels", "duels_won"]),
        ("F. Pressão e contribuição defensiva", ["pressures", "pressures_successful", "pressure_success_pct",
                                                 "recoveries", "recoveries@p90", "recoveries_att_half", "tackles_won",
                                                 "interceptions"]),
        ("G. Segurança na posse", _POSSESSION_SHORT),
    ],
}

# Secção 3 — métricas transversais e derivadas (todas as posições).
TRANSVERSAL: list[tuple[str, list[str]]] = [
    ("3.1/3.3 Ofensivas derivadas", ["goal_contributions", "goal_contributions@p90", "non_penalty_goals",
                                     "non_penalty_goals@p90", "minutes_per_goal", "goal_participations@p90",
                                     "shots_per_goal", "shots_inside_box@p90"]),
    ("3.4 Defensivas derivadas", ["defensive_actions_successful@p90", "recoveries_plus_interceptions@p90",
                                  "tackles_won_plus_interceptions@p90", "recoveries_def_half@p90",
                                  "recoveries_att_half@p90", "def_duels_won@p90", "aerial_duels_won@p90"]),
    ("3.2 Percentagens e taxas", ["pass_pct", "long_pass_pct", "tackle_success_pct", "aerial_duel_pct",
                                  "def_duel_pct", "duel_pct", "dribble_success_pct", "cross_pct",
                                  "shot_on_target_pct", "conversion_pct", "pressure_success_pct", "clean_sheet_pct",
                                  "penalty_save_pct"]),
]

# Composite Scores iniciais (secção 5). Direção "lower" (p.ex. perdas de bola) já é invertida
# no percentil; ``invert`` permite inverter adicionalmente em modelos personalizados.
COMPOSITES: list[dict[str, Any]] = [
    {"key": "cb_dominant", "name": "Central Defensivo Dominante", "group": "CB", "components": [
        "recoveries@p90", "interceptions@p90", "tackles_won@p90", "aerial_duel_pct", "def_duel_pct",
        "defensive_actions_successful@p90", "shots_blocked@p90"]},
    {"key": "cb_builder", "name": "Central Construtor", "group": "CB", "components": [
        "pass_pct", "progressive_passes@p90", "long_passes_completed@p90", "final_third_passes@p90",
        "progressive_carries@p90", "line_breaking_passes@p90", "possession_lost@p90"]},
    {"key": "dm_ball_winner", "name": "Médio Recuperador", "group": "DM", "components": [
        "recoveries@p90", "interceptions@p90", "tackles_won@p90", "def_duel_pct", "aerial_duel_pct",
        "pressures_successful@p90"]},
    {"key": "cm_creative", "name": "Médio Criativo", "group": "CM", "components": [
        "key_passes@p90", "chances_created@p90", "assists@p90", "progressive_passes@p90", "box_passes@p90",
        "dribbles_completed@p90", "big_chances_created@p90"]},
    {"key": "w_dribbler", "name": "Extremo Desequilibrador", "group": "W", "components": [
        "dribbles_completed@p90", "dribble_success_pct", "progressive_carries@p90", "fouls_suffered@p90",
        "chances_created@p90", "goals@p90", "box_touches@p90"]},
    {"key": "st_finisher", "name": "Ponta de Lança Finalizador", "group": "ST", "components": [
        "non_penalty_goals@p90", "shots_on_target@p90", "shot_on_target_pct", "conversion_pct", "box_touches@p90",
        "minutes_per_goal"]},
]
