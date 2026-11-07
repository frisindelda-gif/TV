"""Modelo de avaliação ORIGINAL (proposta inicial).

ATENÇÃO: a especificação "Position Metrics" do utilizador ainda não foi recebida. Estes
pesos são uma proposta de partida, baseada no papel de cada atributo no FM, para o motor
ter algo a calcular. São dados: o Position Lab permite alterá-los e, quando a
especificação chegar, basta substituir este ficheiro (o motor não muda).

Notação: ``"~atributo"`` = atributo invertido (mais é pior).
Pesos são relativos: só a proporção dentro de cada métrica/posição/função conta.
"""

from __future__ import annotations

from fm27si.evaluation.spec import EvaluationSpec

ORIGINAL_KEY = "original"
ORIGINAL_NAME = "Modelo original (proposta inicial)"


def _m(key: str, name: str, category: str, description: str, positions: list[str] | None = None, **weights: float) -> dict:
    attrs = []
    for attr, w in weights.items():
        invert = attr.startswith("inv_")
        attrs.append({"attribute": attr[4:] if invert else attr, "weight": w, "invert": invert})
    return {"key": key, "name": name, "category": category, "description": description,
            "positions": positions or [], "attributes": attrs}


def _w(**weights: float) -> list[dict]:
    return [{"metric": k, "weight": v} for k, v in weights.items()]


METRICS = [
    # ---------------------------------------------------------------- técnicas
    _m("passing", "Passe", "technical", "Precisão e qualidade do passe em circulação.",
       passing=5, first_touch=2, technique=2, composure=1),
    _m("ball_control", "Controlo de bola", "technical", "Receção e proteção da bola sob pressão.",
       first_touch=5, technique=3, balance=1, composure=1),
    _m("dribbling", "Drible", "technical", "Capacidade de ultrapassar adversários com bola.",
       dribbling=5, agility=2, technique=2, balance=1, flair=1),
    _m("finishing", "Finalização", "technical", "Eficácia na conclusão dentro da área.",
       finishing=6, composure=3, technique=1, first_touch=1),
    _m("long_shots", "Remate de longe", "technical", "Ameaça de golo de fora da área.",
       long_shots=6, technique=2, composure=1),
    _m("crossing", "Cruzamento", "technical", "Qualidade dos cruzamentos.",
       crossing=6, technique=2, vision=1),
    _m("heading", "Jogo de cabeça", "technical", "Ganhar e direcionar bolas pelo ar.",
       heading=6, jumping_reach=3, bravery=1),
    _m("tackling", "Desarme", "technical", "Recuperar a bola em duelo sem falta.",
       tackling=6, decisions=1, aggression=1, bravery=1),
    _m("set_pieces", "Bolas paradas", "technical", "Livres, cantos e penáltis.",
       free_kick_taking=4, corners=3, penalty_taking=2, technique=1),
    _m("creative_passing", "Passe criativo", "technical", "Passes que desequilibram (visão + execução).",
       vision=4, passing=3, technique=2, flair=1),
    # ----------------------------------------------------------------- mentais
    _m("decision_making", "Tomada de decisão", "mental", "Escolher bem e a tempo.",
       decisions=5, anticipation=2, composure=2),
    _m("composure", "Frieza", "mental", "Rendimento sob pressão e em jogos grandes.",
       composure=5, important_matches=1, decisions=1),
    _m("concentration", "Concentração e regularidade", "mental", "Evitar quebras de atenção e de rendimento.",
       concentration=5, consistency=2, decisions=1),
    _m("work_ethic", "Ética de trabalho", "mental", "Esforço e vontade ao longo do jogo.",
       work_rate=4, determination=3, stamina=1),
    _m("leadership", "Liderança", "mental", "Influência sobre os colegas.",
       leadership=5, determination=2, composure=1),
    _m("creativity", "Criatividade", "mental", "Imprevisibilidade e imaginação.",
       flair=4, vision=3, technique=1, decisions=1),
    _m("bravery", "Coragem e agressividade", "mental", "Disponibilidade para o choque.",
       bravery=4, aggression=3, determination=1),
    # ----------------------------------------------------------------- físicas
    _m("speed", "Velocidade", "physical", "Velocidade máxima e arranque.",
       pace=5, acceleration=5),
    _m("agility", "Agilidade e equilíbrio", "physical", "Mudanças de direção e estabilidade.",
       agility=5, balance=3, acceleration=1),
    _m("strength", "Força", "physical", "Força nos duelos corpo a corpo.",
       strength=6, balance=2),
    _m("stamina", "Resistência", "physical", "Manter a intensidade durante 90 minutos.",
       stamina=5, natural_fitness=3),
    _m("durability", "Durabilidade", "physical", "Condição física e resistência a lesões.",
       natural_fitness=4, inv_injury_proneness=4, stamina=1),
    # ----------------------------------------------------------------- táticas
    _m("positioning", "Posicionamento defensivo", "tactical", "Ocupar o espaço certo sem bola.",
       positioning=5, anticipation=3, concentration=2, decisions=1),
    _m("marking", "Marcação", "tactical", "Acompanhar e anular o adversário direto.",
       marking=5, positioning=2, concentration=1, strength=1),
    _m("pressing", "Pressão", "tactical", "Pressionar e recuperar alto.",
       work_rate=4, aggression=2, stamina=2, acceleration=1, teamwork=1, anticipation=1),
    _m("off_the_ball", "Movimentação sem bola", "tactical", "Desmarcações e ataque ao espaço.",
       off_the_ball=5, anticipation=3, acceleration=1, decisions=1),
    _m("teamwork", "Disciplina tática", "tactical", "Cumprir o plano coletivo.",
       teamwork=5, work_rate=2, positioning=1, decisions=1),
    # -------------------------------------------------------------- específicas
    _m("gk_shot_stopping", "Defesa de remates", "position_specific", "Parar remates à baliza.", ["GK"],
       reflexes=5, one_on_ones=2, handling=2, agility=2, positioning=2),
    _m("gk_handling", "Segurança de mãos", "position_specific", "Agarrar sem dar recargas.", ["GK"],
       handling=5, concentration=2, composure=1),
    _m("gk_aerial", "Domínio aéreo", "position_specific", "Sair a cruzamentos e dominar a área.", ["GK"],
       aerial_reach=4, command_of_area=4, jumping_reach=1, bravery=1),
    _m("gk_distribution", "Distribuição", "position_specific", "Repor e iniciar a construção.", ["GK"],
       kicking=4, throwing=3, passing=2, vision=1),
    _m("gk_sweeping", "Saídas da baliza", "position_specific", "Jogar fora da área como líbero.", ["GK"],
       rushing_out=3, acceleration=2, anticipation=2, decisions=2, one_on_ones=1),
    _m("gk_communication", "Comando e comunicação", "position_specific", "Organizar a defesa.", ["GK"],
       communication=4, command_of_area=2, leadership=2, concentration=1),
    _m("aerial_defending", "Defesa aérea", "position_specific", "Dominar a própria área pelo ar.", ["DC"],
       heading=3, jumping_reach=3, strength=2, positioning=2, bravery=1),
    _m("flank_support", "Apoio no corredor", "position_specific", "Subir e descer o corredor.", ["DR", "DL"],
       stamina=3, pace=2, crossing=2, work_rate=2, off_the_ball=1),
    _m("screening", "Proteção da defesa", "position_specific", "Fechar linhas à frente dos centrais.", ["DM"],
       positioning=3, anticipation=3, tackling=2, teamwork=1, concentration=1),
    _m("wide_threat", "Ameaça pelos corredores", "position_specific", "Desequilibrar por fora.",
       ["MR", "ML", "AMR", "AML"],
       dribbling=3, acceleration=3, crossing=2, flair=1, off_the_ball=1),
    _m("box_threat", "Ameaça na área", "position_specific", "Aparecer e concluir na área.", ["ST", "AMC", "AMR", "AML"],
       off_the_ball=3, finishing=3, anticipation=2, composure=2, heading=1),
    _m("hold_up", "Jogo de costas", "position_specific", "Segurar a bola e ligar o jogo.", ["ST"],
       strength=3, first_touch=3, balance=2, heading=1, teamwork=1),
]

POSITIONS = [
    {"key": "GK", "metrics": _w(gk_shot_stopping=30, gk_handling=15, gk_aerial=15, gk_communication=10,
                                gk_distribution=10, gk_sweeping=5, decision_making=5, concentration=5, composure=3)},
    {"key": "DC", "metrics": _w(positioning=20, marking=15, tackling=15, heading=10, aerial_defending=10, strength=8,
                                concentration=8, decision_making=5, bravery=5, speed=5, passing=4, composure=4)},
    {"key": "DR", "metrics": _w(tackling=12, positioning=10, marking=8, speed=12, stamina=10, flank_support=12,
                                crossing=8, work_ethic=6, pressing=6, decision_making=5, passing=5, dribbling=4,
                                concentration=4, teamwork=4)},
    {"key": "DL", "metrics": _w(tackling=12, positioning=10, marking=8, speed=12, stamina=10, flank_support=12,
                                crossing=8, work_ethic=6, pressing=6, decision_making=5, passing=5, dribbling=4,
                                concentration=4, teamwork=4)},
    {"key": "DM", "metrics": _w(screening=18, positioning=12, tackling=12, passing=12, decision_making=10, teamwork=8,
                                work_ethic=6, concentration=6, composure=6, pressing=5, stamina=5, strength=4,
                                ball_control=4)},
    {"key": "MC", "metrics": _w(passing=15, decision_making=12, ball_control=10, teamwork=8, work_ethic=8, stamina=8,
                                creative_passing=8, off_the_ball=6, composure=6, tackling=5, pressing=5, long_shots=3,
                                positioning=3)},
    {"key": "MR", "metrics": _w(wide_threat=15, crossing=14, speed=10, stamina=10, work_ethic=8, dribbling=8, passing=8,
                                off_the_ball=7, teamwork=6, decision_making=5, ball_control=5, pressing=4)},
    {"key": "ML", "metrics": _w(wide_threat=15, crossing=14, speed=10, stamina=10, work_ethic=8, dribbling=8, passing=8,
                                off_the_ball=7, teamwork=6, decision_making=5, ball_control=5, pressing=4)},
    {"key": "AMC", "metrics": _w(creative_passing=16, ball_control=12, passing=10, creativity=10, decision_making=10,
                                 box_threat=8, off_the_ball=8, dribbling=8, long_shots=6, composure=6, agility=4)},
    {"key": "AMR", "metrics": _w(wide_threat=16, dribbling=14, speed=14, off_the_ball=8, ball_control=8, crossing=8,
                                 creativity=7, finishing=6, agility=6, decision_making=5, box_threat=4, pressing=4)},
    {"key": "AML", "metrics": _w(wide_threat=16, dribbling=14, speed=14, off_the_ball=8, ball_control=8, crossing=8,
                                 creativity=7, finishing=6, agility=6, decision_making=5, box_threat=4, pressing=4)},
    {"key": "ST", "metrics": _w(finishing=22, box_threat=14, off_the_ball=12, composure=8, ball_control=8, speed=8,
                                heading=6, hold_up=6, decision_making=5, strength=4, agility=3, pressing=4)},
]

# Só as funções indicadas pelo utilizador, todas "unconfirmed" até se confirmar no FM27 instalado.
ROLES = [
    {"key": "sweeper_keeper", "name": "Guarda-redes líbero", "positions": ["GK"],
     "description": "Guarda-redes que joga adiantado e participa na construção.",
     "metrics": _w(gk_sweeping=20, gk_shot_stopping=20, gk_distribution=15, ball_control=8, passing=8, gk_aerial=8,
                   decision_making=8, composure=6, speed=4, gk_communication=3)},
    {"key": "ball_playing_defender", "name": "Defesa central com bola", "positions": ["DC"],
     "description": "Central que inicia a construção com passe.",
     "metrics": _w(passing=15, composure=12, creative_passing=8, ball_control=8, positioning=14, marking=10,
                   tackling=10, heading=10, decision_making=8, concentration=5)},
    {"key": "attacking_fullback", "name": "Defesa lateral ofensivo", "positions": ["DR", "DL"],
     "description": "Lateral com forte participação ofensiva.",
     "metrics": _w(flank_support=18, crossing=14, speed=12, stamina=10, dribbling=8, off_the_ball=8, tackling=8,
                   positioning=6, work_ethic=6, teamwork=5, passing=5)},
    {"key": "ball_winning_midfielder", "name": "Médio recuperador de bolas", "positions": ["DM", "MC"],
     "description": "Médio agressivo focado em recuperar a bola.",
     "metrics": _w(tackling=20, pressing=18, bravery=10, work_ethic=12, stamina=10, positioning=8, teamwork=8,
                   strength=6, decision_making=4, passing=4)},
    {"key": "deep_lying_playmaker", "name": "Construtor de jogo recuado", "positions": ["DM", "MC"],
     "description": "Organiza o jogo a partir de trás.",
     "metrics": _w(passing=20, creative_passing=15, ball_control=12, decision_making=12, composure=10, teamwork=8,
                   positioning=8, concentration=5)},
    {"key": "box_to_box", "name": "Médio área a área", "positions": ["MC"],
     "description": "Médio completo, presente nas duas áreas.",
     "metrics": _w(stamina=14, work_ethic=14, passing=10, tackling=10, off_the_ball=10, pressing=8, decision_making=8,
                   ball_control=6, long_shots=6, finishing=4, teamwork=6, strength=4)},
    {"key": "mezzala", "name": "Mezzala", "positions": ["MC"],
     "description": "Médio interior que ataca o meio-espaço.",
     "metrics": _w(off_the_ball=14, dribbling=12, creative_passing=12, ball_control=12, passing=10, decision_making=8,
                   long_shots=6, creativity=8, work_ethic=6, speed=4, finishing=4, box_threat=4)},
    {"key": "advanced_playmaker", "name": "Organizador avançado", "positions": ["MC", "AMC"],
     "description": "Criativo entre linhas, último passe.",
     "metrics": _w(creative_passing=20, creativity=15, ball_control=14, passing=12, decision_making=12, composure=8,
                   off_the_ball=6, dribbling=6, agility=4)},
    {"key": "inverted_winger", "name": "Extremo invertido", "positions": ["MR", "ML", "AMR", "AML"],
     "description": "Extremo que fecha para dentro para criar.",
     "metrics": _w(dribbling=15, creative_passing=12, passing=10, ball_control=10, wide_threat=10, speed=10,
                   creativity=8, off_the_ball=6, long_shots=5, decision_making=6, crossing=4, agility=4)},
    {"key": "inside_forward", "name": "Avançado interior", "positions": ["AMR", "AML"],
     "description": "Parte da ala para finalizar.",
     "metrics": _w(finishing=15, dribbling=14, off_the_ball=13, speed=13, box_threat=10, composure=8, ball_control=8,
                   agility=6, long_shots=5, decision_making=4, creativity=4)},
    {"key": "pressing_forward", "name": "Avançado pressionante", "positions": ["ST"],
     "description": "Avançado que lidera a pressão.",
     "metrics": _w(pressing=22, work_ethic=15, stamina=12, bravery=8, speed=8, off_the_ball=8, finishing=10,
                   teamwork=7, strength=5, decision_making=5)},
    {"key": "false_nine", "name": "Falso nove", "positions": ["ST"],
     "description": "Avançado que recua para criar.",
     "metrics": _w(creative_passing=15, ball_control=15, passing=12, creativity=12, dribbling=10, decision_making=10,
                   off_the_ball=8, finishing=8, composure=6, agility=4)},
    {"key": "target_man", "name": "Homem-alvo", "positions": ["ST"],
     "description": "Referência física e aérea.",
     "metrics": _w(heading=18, strength=18, hold_up=16, bravery=8, finishing=10, box_threat=8, ball_control=6,
                   teamwork=6, composure=4)},
]


def original_spec() -> EvaluationSpec:
    return EvaluationSpec.model_validate({"min_coverage": 0.6, "metrics": METRICS, "positions": POSITIONS, "roles": ROLES})
