"""Catálogo canónico de atributos.

Uma única fonte de verdade para as chaves usadas na base de dados e na API. Cada conector
traduz os nomes da sua fonte para estas chaves; nada fora deste módulo deve inventar chaves.

Categorias seguem o ecrã de perfil do FM: técnicos, mentais, físicos, guarda-redes, e os
escondidos (atributos ocultos + personalidade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Category = Literal["technical", "mental", "physical", "goalkeeping", "hidden", "personality"]


@dataclass(frozen=True)
class AttributeDef:
    key: str
    label: str
    category: Category
    fmss_key: str | None  # chave no dump.json do FMSuperScout
    fmsave_field: str | None  # campo em fmsave.Attributes / fmsave.Personality


_ATTRS: tuple[AttributeDef, ...] = (
    # Técnicos (14)
    AttributeDef("corners", "Cantos", "technical", "Corners", "corners"),
    AttributeDef("crossing", "Cruzamentos", "technical", "Crossing", "crossing"),
    AttributeDef("dribbling", "Drible", "technical", "Dribbling", "dribbling"),
    AttributeDef("finishing", "Finalização", "technical", "Finishing", "finishing"),
    AttributeDef("first_touch", "Primeiro toque", "technical", "FirstTouch", "first_touch"),
    AttributeDef("free_kick_taking", "Livres", "technical", "FreeKicks", "free_kick_taking"),
    AttributeDef("heading", "Cabeceamento", "technical", "Heading", "heading"),
    AttributeDef("long_shots", "Remates de longe", "technical", "LongShots", "long_shots"),
    AttributeDef("long_throws", "Lançamentos longos", "technical", "LongThrows", "long_throws"),
    AttributeDef("marking", "Marcação", "technical", "Marking", "marking"),
    AttributeDef("passing", "Passe", "technical", "Passing", "passing"),
    AttributeDef("penalty_taking", "Penáltis", "technical", "PenaltyTaking", "penalty_taking"),
    AttributeDef("tackling", "Desarme", "technical", "Tackling", "tackling"),
    AttributeDef("technique", "Técnica", "technical", "Technique", "technique"),
    # Mentais (14)
    AttributeDef("aggression", "Agressividade", "mental", "Aggression", "aggression"),
    AttributeDef("anticipation", "Antecipação", "mental", "Anticipation", "anticipation"),
    AttributeDef("bravery", "Coragem", "mental", "Bravery", "bravery"),
    AttributeDef("composure", "Compostura", "mental", "Composure", "composure"),
    AttributeDef("concentration", "Concentração", "mental", "Concentration", "concentration"),
    AttributeDef("decisions", "Decisões", "mental", "Decisions", "decisions"),
    AttributeDef("determination", "Determinação", "mental", "Determination", "determination"),
    AttributeDef("flair", "Talento", "mental", "Flair", "flair"),
    AttributeDef("leadership", "Liderança", "mental", "Leadership", "leadership"),
    AttributeDef("off_the_ball", "Sem bola", "mental", "OffTheBall", "off_the_ball"),
    AttributeDef("positioning", "Posicionamento", "mental", "Positioning", "positioning"),
    AttributeDef("teamwork", "Trabalho de equipa", "mental", "Teamwork", "teamwork"),
    AttributeDef("vision", "Visão", "mental", "Vision", "vision"),
    AttributeDef("work_rate", "Índice de trabalho", "mental", "WorkRate", "work_rate"),
    # Físicos (8)
    AttributeDef("acceleration", "Aceleração", "physical", "Acceleration", "acceleration"),
    AttributeDef("agility", "Agilidade", "physical", "Agility", "agility"),
    AttributeDef("balance", "Equilíbrio", "physical", "Balance", "balance"),
    AttributeDef("jumping_reach", "Impulsão", "physical", "JumpingReach", "jumping_reach"),
    AttributeDef("natural_fitness", "Forma física natural", "physical", "NaturalFitness", "natural_fitness"),
    AttributeDef("pace", "Velocidade", "physical", "Pace", "pace"),
    AttributeDef("stamina", "Resistência", "physical", "Stamina", "stamina"),
    AttributeDef("strength", "Força", "physical", "Strength", "strength"),
    # Guarda-redes (11)
    AttributeDef("aerial_reach", "Alcance aéreo", "goalkeeping", "AerialReach", "aerial_reach"),
    AttributeDef("command_of_area", "Domínio da área", "goalkeeping", "CommandOfArea", "command_of_area"),
    AttributeDef("communication", "Comunicação", "goalkeeping", "Communication", "communication"),
    AttributeDef("eccentricity", "Excentricidade", "goalkeeping", "Eccentricity", "eccentricity"),
    AttributeDef("handling", "Jogo de mãos", "goalkeeping", "Handling", "handling"),
    AttributeDef("kicking", "Pontapé", "goalkeeping", "Kicking", "kicking"),
    AttributeDef("one_on_ones", "Um para um", "goalkeeping", "OneOnOnes", "one_on_ones"),
    AttributeDef("punching", "Tendência p/ socar", "goalkeeping", "Punching", "punching"),
    AttributeDef("reflexes", "Reflexos", "goalkeeping", "Reflexes", "reflexes"),
    AttributeDef("rushing_out", "Saídas", "goalkeeping", "RushingOut", "rushing_out"),
    AttributeDef("throwing", "Lançamento", "goalkeeping", "Throwing", "throwing"),
    # Escondidos (5)
    AttributeDef("consistency", "Consistência", "hidden", "Consistency", "consistency"),
    AttributeDef("dirtiness", "Jogo sujo", "hidden", "Dirtiness", "dirtiness"),
    AttributeDef("important_matches", "Jogos importantes", "hidden", "ImportantMatches", "important_matches"),
    AttributeDef("injury_proneness", "Propensão a lesões", "hidden", "InjuryProneness", "injury_proneness"),
    AttributeDef("versatility", "Versatilidade", "hidden", "Versatility", "versatility"),
    # Personalidade (8, escondidos)
    AttributeDef("adaptability", "Adaptabilidade", "personality", "adaptability", "adaptability"),
    AttributeDef("ambition", "Ambição", "personality", "ambition", "ambition"),
    AttributeDef("controversy", "Controvérsia", "personality", "controversy", "controversy"),
    AttributeDef("loyalty", "Lealdade", "personality", "loyalty", "loyalty"),
    AttributeDef("pressure", "Pressão", "personality", "pressure", "pressure"),
    AttributeDef("professionalism", "Profissionalismo", "personality", "professionalism", "professionalism"),
    AttributeDef("sportsmanship", "Desportivismo", "personality", "sportsmanship", "sportsmanship"),
    AttributeDef("temperament", "Temperamento", "personality", "temperament", "temperament"),
)

ATTRIBUTES: dict[str, AttributeDef] = {a.key: a for a in _ATTRS}
PLAYER_ATTRIBUTE_KEYS: tuple[str, ...] = tuple(a.key for a in _ATTRS if a.category != "personality")
PERSONALITY_KEYS: tuple[str, ...] = tuple(a.key for a in _ATTRS if a.category == "personality")

POSITION_KEYS: tuple[str, ...] = (
    "GK", "SW", "DL", "DC", "DR", "DM", "ML", "MC", "MR", "AML", "AMC", "AMR", "ST", "WBL", "WBR",
)


def category_of(key: str) -> Category:
    return ATTRIBUTES[key].category


assert len(PLAYER_ATTRIBUTE_KEYS) == 52, len(PLAYER_ATTRIBUTE_KEYS)
assert len(PERSONALITY_KEYS) == 8
