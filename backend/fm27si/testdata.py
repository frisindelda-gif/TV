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
