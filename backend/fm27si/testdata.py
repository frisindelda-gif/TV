"""Gerador de uma carreira de teste SINTÉTICA.

Não existe aqui nenhum save real (nem pode ser publicado). Para testar o pipeline completo
geramos dumps no formato do FMSuperScout 1.7.x, com ``meta.synthetic = true``. Todos os
nomes e valores são fictícios e determinísticos (semente fixa). Os registos importados a
partir daqui ficam marcados como sintéticos na base de dados.

Cada época simulada:
- jovens evoluem para o PA, veteranos regridem;
- jogadores com 36+ podem retirar-se (desaparecem do dump);
- entram regens de 15–16 anos com Unique IDs novos.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fm27si.catalog import ATTRIBUTES

_FIRST = ["Rui", "Tiago", "João", "Miguel", "André", "Diogo", "Bruno", "Luís", "Pedro", "Nuno",
          "Hugo", "Gonçalo", "Rafael", "Vasco", "Duarte", "Tomás", "Afonso", "Martim", "Simão", "Íñigo"]
_LAST = ["Sardinha", "Valente", "Carvalhal", "Mourato", "Pestana", "Quaresma", "Teixeira", "Brandão",
         "Lobato", "Fontes", "Rebelo", "Seixas", "Moita", "Calado", "Peixoto", "Arruda", "Bettencourt"]
_CLUBS = [("SC Vale Fictício", 6200, "Liga Exemplo"), ("Atlético Serra Nova", 5100, "Liga Exemplo"),
          ("FC Ribeira Imaginária", 4300, "Liga Exemplo"), ("União Planalto Teste", 2500, "Segunda Exemplo")]
_NATS = ["Portugal", "Brasil", "Cabo Verde", "Angola", "Espanha"]
_POS = ["GK", "DL", "DC", "DR", "DM", "MC", "ML", "MR", "AML", "AMC", "AMR", "ST", "WBL", "WBR"]

_FMSS_ATTR = [a.fmss_key for a in ATTRIBUTES.values() if a.category != "personality"]
_PERS = [a.fmss_key for a in ATTRIBUTES.values() if a.category == "personality"]


@dataclass
class _P:
    uid: int
    name: str
    birth_year: int
    birth_doy: int
    nat: str
    club: int
    ca: int
    pa: int
    pos: list[str]
    attrs: dict[str, int]
    pers: dict[str, int]
    height: int
    foot: str
    wage: int
    expires_year: int
    extra: dict = field(default_factory=dict)


class SyntheticCareer:
    def __init__(self, n_players: int = 300, seed: int = 27, start: date = date(2026, 7, 15)) -> None:
        self.rng = random.Random(seed)
        self.date = start
        self.next_uid = 2_000_000_000 + 1
        self.players: list[_P] = [self._new(age=self.rng.randint(16, 35)) for _ in range(n_players)]

    def _uid(self) -> int:
        u = self.next_uid
        self.next_uid += self.rng.randint(1, 50)
        return u

    def _new(self, age: int) -> _P:
        r = self.rng
        pa = int(min(200, max(40, r.gauss(115, 30))))
        growth = max(0.35, min(1.0, (age - 15) / 9))
        ca = max(25, min(pa, int(pa * growth * r.uniform(0.85, 1.0))))
        main = r.choice(_POS)
        pos = [main] + ([r.choice(_POS)] if r.random() < 0.4 and main != "GK" else [])
        attrs = self._attrs_for(ca, main == "GK")
        return _P(
            uid=self._uid(),
            name=f"{r.choice(_FIRST)} {r.choice(_LAST)}",
            birth_year=self.date.year - age,
            birth_doy=r.randint(1, 365),
            nat=r.choice(_NATS),
            club=r.randrange(len(_CLUBS)),
            ca=ca,
            pa=pa,
            pos=list(dict.fromkeys(pos)),
            attrs=attrs,
            pers={k: r.randint(1, 20) for k in _PERS},
            height=r.randint(165, 198),
            foot=r.choice(["Rechts", "Rechts", "Links", "Beide"]),
            wage=int(ca**2 * r.uniform(0.2, 0.6)),
            expires_year=self.date.year + r.randint(0, 4),
        )

    def _attrs_for(self, ca: int, gk: bool) -> dict[str, int]:
        r = self.rng
        base = 2 + ca / 200 * 16
        out = {}
        gk_keys = {a.fmss_key for a in ATTRIBUTES.values() if a.category == "goalkeeping"}
        for k in _FMSS_ATTR:
            b = base if (k in gk_keys) == gk or k not in gk_keys else 2
            out[k] = max(1, min(20, int(r.gauss(b, 2.5))))
        return out

    def advance_season(self) -> None:
        r = self.rng
        self.date = date(self.date.year + 1, self.date.month, self.date.day)
        survivors = []
        for p in self.players:
            age = self.date.year - p.birth_year
            if age >= 36 and r.random() < 0.5:
                continue  # retirado
            if age <= 23:
                delta = r.randint(2, 12)
            elif age <= 29:
                delta = r.randint(-2, 4)
            else:
                delta = r.randint(-8, 0)
            p.ca = max(20, min(p.pa, p.ca + delta))
            for k in p.attrs:
                p.attrs[k] = max(1, min(20, p.attrs[k] + (1 if delta > 4 and r.random() < 0.3 else 0)
                                        - (1 if delta < -3 and r.random() < 0.3 else 0)))
            if r.random() < 0.08:
                p.club = r.randrange(len(_CLUBS))
            survivors.append(p)
        self.players = survivors + [self._new(age=r.randint(15, 16)) for _ in range(max(5, len(survivors) // 20))]

    def dump(self) -> dict:
        players = []
        for p in self.players:
            cname, crep, div = _CLUBS[p.club]
            players.append({
                "id": p.uid,
                "name": p.name,
                "age": self.date.year - p.birth_year - (1 if p.birth_doy > self.date.timetuple().tm_yday else 0),
                "dob": f"{p.birth_year:04d}",
                "birthYear": p.birth_year,
                "birthDoy": p.birth_doy,
                "nat": [p.nat],
                "club": cname,
                "div": div,
                "ca": p.ca,
                "pa": p.pa,
                "wage": p.wage,
                "expires": f"{p.expires_year}-06-30",
                "pos": ", ".join(p.pos),
                "posArr": p.pos,
                "posNat": p.pos[:1],
                "teamType": 0,
                "foot": p.foot,
                "height": p.height,
                "value": int(p.ca**2.6 * 2) if p.ca > 60 else None,
                "askingPrice": None,
                "wageDemand": None,
                "listed": False,
                "loanListed": False,
                "notForSale": False,
                "setForRelease": False,
                "clubRep": crep,
                "worldRep": int(p.ca * 25),
                **{k: v for k, v in p.pers.items()},
                "attrs": dict(p.attrs),
            })
        return {
            "meta": {
                "generated": f"{date.today().isoformat()}T12:00:00",
                "gameDate": self.date.isoformat(),
                "gameDateSource": "memory",
                "gameYear": self.date.year,
                "pluginVersion": "synthetic",
                "host": "synthetic",
                "game": "FM27",
                "gameVersion": "27.0",
                "supportedVersion": "27.0",
                "versionOk": True,
                "manager": "Treinador Teste",
                "myClub": _CLUBS[0][0],
                "myClubRep": _CLUBS[0][1],
                "currency": "GBP",
                "source": "FM27SI synthetic generator (NÃO são dados do jogo)",
                "synthetic": True,
            },
            "players": players,
            "staff": [],
        }


def write_test_career(out_dir: Path, *, players: int = 300, seasons: int = 2, seed: int = 27) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    career = SyntheticCareer(players, seed=seed)
    paths = []
    for i in range(seasons):
        if i:
            career.advance_season()
        p = out_dir / f"dump-season{i + 1}.json"
        p.write_text(json.dumps(career.dump(), ensure_ascii=False, indent=1), encoding="utf-8")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Carreira de DEMONSTRAÇÃO (para a interface): dumps sintéticos + estatísticas fictícias.
# ---------------------------------------------------------------------------

_DEMO_UNAVAILABLE = ["Tudo nesta carreira é fictício (gerado pela app para demonstração)."]

# Taxas base por 90' por grupo de posição (ordem de grandeza de uma liga média).
_BASE = {
    #       golos  assist  passes  prog  drib  desarm interc aereos alivios
    "GK": (0.00, 0.00, 30, 1.0, 0.0, 0.0, 0.3, 0.5, 1.0),
    "CB": (0.04, 0.03, 55, 4.0, 0.2, 2.4, 2.0, 5.0, 4.5),
    "FB": (0.04, 0.10, 45, 4.5, 1.0, 2.6, 1.5, 1.8, 2.0),
    "DM": (0.04, 0.06, 60, 5.5, 0.6, 3.2, 2.0, 2.2, 1.5),
    "CM": (0.08, 0.12, 58, 5.0, 1.0, 2.2, 1.2, 1.5, 0.8),
    "WM": (0.18, 0.17, 35, 3.0, 2.8, 1.2, 0.6, 1.0, 0.3),
    "AM": (0.20, 0.20, 42, 3.5, 2.2, 1.0, 0.5, 0.8, 0.2),
    "ST": (0.42, 0.11, 25, 1.5, 1.4, 0.6, 0.3, 5.0, 0.4),
}


def _f(attr: int) -> float:
    """Fator 0.6–1.4 a partir de um atributo 1–20."""
    return 0.6 + 0.8 * (attr - 1) / 19


def _season_stats(p, group: str, minutes: int, club: str, rng: random.Random):
    from fm27si.schemas import SeasonStats  # noqa: PLC0415

    a = p.attrs
    n90 = minutes / 90
    g, ast, passes, prog, drib, tack, inter, aerial, clear = _BASE[group]

    def cnt(rate: float) -> int:
        return max(0, int(round(rng.gauss(rate * n90, max(0.5, (rate * n90) ** 0.5)))))

    apps = max(1, round(minutes / rng.uniform(70, 88)))
    starts = min(apps, round(minutes / 90))
    xg = g * _f(a["Finishing"]) * _f(a["OffTheBall"]) * n90 * rng.uniform(0.85, 1.15)
    goals = max(0, int(round(rng.gauss(xg * _f(a["Composure"]), max(0.6, xg**0.5)))))
    xa = ast * _f(a["Vision"]) * _f(a["Passing"]) * n90 * rng.uniform(0.85, 1.15)
    shots = cnt(max(0.05, xg / max(n90, 0.1) * 8.5))
    sot = min(shots, int(round(shots * (0.22 + 0.012 * a["Finishing"]))))
    p_att = cnt(passes * _f(a["Teamwork"]))
    p_pct = min(0.94, 0.62 + 0.014 * a["Passing"] + 0.004 * a["Decisions"])
    t_att = cnt(tack * _f(a["WorkRate"]))
    t_pct = min(0.9, 0.48 + 0.016 * a["Tackling"])
    aer = cnt(aerial)
    aer_pct = min(0.85, 0.3 + 0.012 * (a["Heading"] + a["JumpingReach"]))
    pres = cnt(14 * _f(a["WorkRate"]) * _f(a["Stamina"])) if group != "GK" else 0
    crosses = cnt({"FB": 3.0, "WM": 3.5}.get(group, 0.6))
    extra = {
        "shots": shots,
        "shots_on_target": sot,
        "passes_attempted": p_att,
        "passes_completed": int(round(p_att * p_pct)),
        "key_passes": cnt((0.4 + 2.0 * ast / 0.2) * _f(a["Vision"]) * 0.6),
        "clear_cut_chances_created": cnt(ast * 1.2 * _f(a["Vision"])),
        "progressive_passes": cnt(prog * _f(a["Passing"]) * _f(a["Vision"])),
        "crosses_attempted": crosses,
        "crosses_completed": int(round(crosses * min(0.5, 0.12 + 0.014 * a["Crossing"]))),
        "dribbles": cnt(drib * _f(a["Dribbling"]) * _f(a["Flair"])),
        "tackles_attempted": t_att,
        "tackles_completed": int(round(t_att * t_pct)),
        "interceptions": cnt(inter * _f(a["Anticipation"]) * _f(a["Positioning"])),
        "possession_won": cnt((tack + inter) * 1.6 + 1.5),
        "possession_lost": cnt(6 + 6 * (1.4 - _f(a["Technique"]))),
        "pressures_attempted": pres,
        "pressures_completed": int(round(pres * 0.3)),
        "aerial_challenges_attempted": aer,
        "headers_won": int(round(aer * aer_pct)),
        "clearances": cnt(clear * _f(a["Heading"])),
        "blocks": cnt({"CB": 0.7, "FB": 0.4, "DM": 0.4}.get(group, 0.15)),
        "distance_km": round(n90 * (5.2 if group == "GK" else 9.2 + 2.4 * (_f(a["Stamina"]) + _f(a["WorkRate"]) - 1.2)), 1),
        "high_intensity_sprints": cnt(0 if group == "GK" else 18 * _f(a["Pace"]) * _f(a["Acceleration"])),
        "fouls_made": cnt(0.4 + 0.08 * a["Aggression"]),
        "fouls_against": cnt(0.6 + 0.08 * a["Dribbling"]),
        "mistakes_leading_to_goal": cnt(0.02 * (1.6 - _f(a["Concentration"]))),
        "non_penalty_expected_goals": round(xg * 0.88, 2),
        "rated_appearances": apps,
    }
    clean = None
    if group == "GK":
        faced = cnt(3.8)
        save_pct = min(0.86, 0.5 + 0.012 * a["Reflexes"] + 0.008 * a["Handling"] + 0.004 * a["OneOnOnes"])
        saves = int(round(faced * save_pct))
        allowed = faced - saves
        expected_allowed = faced * 0.3
        extra.update(
            shots_on_target_faced=faced,
            saves_held=int(saves * 0.45),
            saves_parried=int(saves * 0.4),
            saves_tipped=saves - int(saves * 0.45) - int(saves * 0.4),
            goals_allowed=allowed,
            expected_goals_prevented=round(expected_allowed - allowed, 2),
        )
        clean = max(0, int(round(apps * (save_pct - 0.45))))
    rating = 6.55 + (p.ca - 100) / 260 + 0.02 * (goals + xa) / max(n90, 1) + rng.gauss(0, 0.12)
    return SeasonStats(
        competition_kind="league",
        club_name=club,
        starts=starts,
        sub_appearances=apps - starts,
        minutes=minutes,
        goals=goals,
        assists=max(0, int(round(rng.gauss(xa, max(0.5, xa**0.5))))),
        average_rating=round(min(8.6, max(5.9, rating)), 2),
        player_of_the_match=max(0, int(round(apps * max(0.0, rating - 6.9) * 0.15))),
        expected_goals=round(xg, 2),
        expected_assists=round(xa, 2),
        yellow_cards=cnt(0.06 + 0.012 * a["Aggression"]),
        red_cards=1 if rng.random() < 0.004 * a["Aggression"] * n90 / 30 else 0,
        clean_sheets=clean,
        extra=extra,
    )


def demo_bundles(players: int = 400, seasons: int = 3, seed: int = 27):
    """Carreira de demonstração completa, já normalizada, com estatísticas fictícias."""
    from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector  # noqa: PLC0415
    from fm27si.metrics import position_group  # noqa: PLC0415

    career = SyntheticCareer(players, seed=seed)
    conn = FMSuperScoutLiveConnector()
    out = []
    for i in range(seasons):
        if i:
            career.advance_season()
        rng = random.Random(seed * 1000 + i)
        dump = career.dump()
        bundle = conn.from_dict(dump)
        by_uid = {p.uid: p for p in career.players}

        # Minutos: os melhores de cada clube jogam mais.
        clubs: dict[str, list] = {}
        for np_ in bundle.players:
            clubs.setdefault(np_.club.name if np_.club else "", []).append(np_)
        minutes_of: dict[int, int] = {}
        for squad in clubs.values():
            for rank, np_ in enumerate(sorted(squad, key=lambda x: -(x.ca or 0))):
                young = (np_.age or 20) < 17
                if rank < 11 and not young:
                    minutes_of[np_.source_uid] = rng.randint(2100, 3300)
                elif rank < 20 and not young:
                    minutes_of[np_.source_uid] = rng.randint(500, 1900)
                elif rng.random() < 0.5:
                    minutes_of[np_.source_uid] = rng.randint(30, 600)

        new_players = []
        for np_ in bundle.players:
            src = by_uid[np_.source_uid]
            ratings = {k: rng.randint(1, 9) for k in ("GK", "SW", "DL", "DC", "DR", "DM", "ML", "MC", "MR", "AML", "AMC", "AMR", "ST", "WBL", "WBR")}
            for k in np_.accomplished_positions:
                ratings[k] = rng.randint(15, 17)
            for k in np_.natural_positions:
                ratings[k] = rng.randint(18, 20)
            if "GK" not in np_.natural_positions:
                ratings["GK"] = 1
            group = position_group(np_.natural_positions, np_.accomplished_positions) or "CM"
            mins = minutes_of.get(np_.source_uid, 0)
            stats = [_season_stats(src, group, mins, np_.club.name if np_.club else "", rng)] if mins else []
            status = {k: "estimate" for k in np_.field_status}  # nada disto é do jogo
            new_players.append(np_.model_copy(update={"positions": ratings, "season_stats": stats, "field_status": status}))
        src = bundle.source.model_copy(update={"connector": "synthetic", "tool": "Gerador de demonstração (dados fictícios)", "synthetic": True})
        out.append(bundle.model_copy(update={"source": src, "players": new_players, "unavailable_fields": _DEMO_UNAVAILABLE}))
    return out
