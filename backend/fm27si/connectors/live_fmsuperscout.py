"""Live Connector: leitura da memória do FM27 através do scanner do FMSuperScout.

Decisão (ver docs/DECISOES.md, D-02): não reimplementamos a leitura de memória. O scanner
open source do FMSuperScout (MIT, C#/.NET 8) abre ``fm.exe`` só com ``PROCESS_VM_READ |
PROCESS_QUERY_INFORMATION`` e escreve ``%LOCALAPPDATA%\\FMSuperScout\\dump.json``. Este
conector:

1. (opcional) executa ``FMSuperScout.Scanner.exe scan`` a pedido do utilizador;
2. lê o ``dump.json`` em modo só-leitura;
3. traduz para o contrato normalizado.

Nunca escrevemos na memória do jogo nem no dump. O formato do dump não é uma API pública
estável do FMSuperScout: está fixado aqui contra a versão 1.7.x e é validado na leitura.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from fm27si.catalog import ATTRIBUTES
from fm27si.connectors.base import ConnectorError, mtime_of, parse_iso_date, sha256_of
from fm27si.schemas import (
    CareerInfo,
    ClubRef,
    Contract,
    ImportBundle,
    NormalizedPlayer,
    SourceInfo,
)

KIND = "live_memory"

_FMSS_TO_KEY = {a.fmss_key: a.key for a in ATTRIBUTES.values() if a.category != "personality"}
_PERSONALITY_KEYS = [a.key for a in ATTRIBUTES.values() if a.category == "personality"]
_FOOT = {"Beide": "both", "Rechts": "right", "Links": "left"}

# Campos que o dump do FMSuperScout 1.7.x não contém (confirmado em core/Dumper.cs).
UNAVAILABLE = [
    "positions (classificação 1..20 por posição; só listas natural/acomplished)",
    "foot_left / foot_right (só o pé preferido)",
    "reputation_home / reputation_current (jogadores)",
    "season_stats (estatísticas individuais)",
    "contract.start / squad_status",
    "club.unique_id (clubes só por nome)",
    "traits",
    "roles",
    "first_name / last_name separados",
]

# Leitura validada em: FMSuperScout 1.7.x, layout FM27 27.0 / FM26 26.3.
SUPPORTED_GAMES = {"FM27", "FM26"}


def run_scanner(scanner_exe: Path, timeout_s: int = 180) -> None:
    """Pede uma nova leitura ao scanner (só Windows). O scanner apenas LÊ a memória."""
    if sys.platform != "win32":
        raise ConnectorError("O scanner do FMSuperScout só corre em Windows.")
    if not scanner_exe.is_file():
        raise ConnectorError(f"Scanner não encontrado: {scanner_exe}")
    proc = subprocess.run(
        [str(scanner_exe), "scan"], capture_output=True, text=True, timeout=timeout_s, check=False
    )
    if proc.returncode != 0:
        raise ConnectorError(f"Scanner terminou com código {proc.returncode}: {proc.stdout[-500:]}{proc.stderr[-500:]}")


def scanner_path_from_env() -> Path | None:
    p = os.environ.get("FM27SI_FMSS_SCANNER")
    return Path(p) if p else None


def _birth_date(year: object, doy: object) -> date | None:
    if not isinstance(year, int) or not isinstance(doy, int) or year < 1900 or not 1 <= doy <= 366:
        return None
    d = date(year, 1, 1) + timedelta(days=doy - 1)
    return d if d.year == year else None


class FMSuperScoutLiveConnector:
    kind = KIND

    def load(self, path: Path) -> ImportBundle:
        if not path.is_file():
            raise ConnectorError(f"dump.json não encontrado em {path}. Corra o scanner com o FM27 aberto.")
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ConnectorError(f"dump.json ilegível: {e}") from e
        return self.from_dict(data, path=path)

    def from_dict(self, data: dict, *, path: Path | None = None) -> ImportBundle:
        if not isinstance(data, dict) or "meta" not in data or "players" not in data:
            raise ConnectorError("Formato inesperado: faltam 'meta'/'players' (não é um dump do FMSuperScout?)")
        meta = data["meta"]
        warnings: list[str] = []
        game = meta.get("game")
        if game not in SUPPORTED_GAMES:
            raise ConnectorError(f"Jogo não suportado no dump: {game!r}")
        if meta.get("versionOk") is False:
            warnings.append(
                f"FMSuperScout indica versão do jogo não verificada ({meta.get('gameVersion')} vs "
                f"{meta.get('supportedVersion')}): os offsets podem estar errados."
            )
        if meta.get("synthetic"):
            warnings.append("Dump SINTÉTICO (dados de teste fabricados, não vêm do jogo).")

        game_date = parse_iso_date(meta.get("gameDate"))
        gd_status = "unconfirmed" if meta.get("gameDateSource") == "memory" else "derived"
        try:
            read_at = datetime.fromisoformat(meta["generated"]) if meta.get("generated") else None
        except ValueError:
            read_at = None
        source = SourceInfo(
            connector=KIND,
            tool=str(meta.get("source") or "FMSuperScout"),
            tool_version=meta.get("pluginVersion"),
            source_path=str(path) if path else None,
            source_sha256=sha256_of(path) if path else None,
            source_mtime=mtime_of(path) if path else None,
            read_at=read_at or (mtime_of(path) if path else datetime.now()),
            game=game,
            game_version=meta.get("gameVersion"),
            game_version_supported=meta.get("versionOk"),
            game_date=game_date,
            game_date_status=gd_status,
            currency=meta.get("currency"),
            synthetic=bool(meta.get("synthetic")),
        )
        career = CareerInfo(manager_name=meta.get("manager"), managed_club=meta.get("myClub"))

        players: list[NormalizedPlayer] = []
        for i, raw in enumerate(data["players"]):
            try:
                players.append(self._player(raw))
            except Exception as e:  # registo individual corrompido não pára a importação
                warnings.append(f"Jogador #{i} ignorado: {e}")
        return ImportBundle(
            source=source,
            career=career,
            players=players,
            clubs=[],
            unavailable_fields=UNAVAILABLE,
            warnings=warnings,
        )

    @staticmethod
    def _player(r: dict) -> NormalizedPlayer:
        uid = int(r["id"])
        attrs: dict[str, int] = {}
        unknown_attr: dict[str, object] = {}
        for k, v in (r.get("attrs") or {}).items():
            key = _FMSS_TO_KEY.get(k)
            if key is None:
                unknown_attr[k] = v
            else:
                attrs[key] = int(v)
        for k in _PERSONALITY_KEYS:
            v = r.get(k)
            if isinstance(v, int) and v > 0:
                attrs[k] = v

        birth = _birth_date(r.get("birthYear"), r.get("birthDoy"))
        owner = r.get("ownerClub")
        contract = Contract(
            wage_weekly=r.get("wage"),
            expires=parse_iso_date(r.get("expires")),
            transfer_listed=r.get("listed"),
            loan_listed=r.get("loanListed"),
            not_for_sale=r.get("notForSale"),
            set_for_release=r.get("setForRelease"),
            on_loan=bool(owner) if owner is not None else None,
            loan_parent_club=owner,
        )
        status = {
            # FMSuperScout afirma ter verificado estes contra o FM27 a correr (Fields.cs, 02-11-2026).
            "ca": "verified", "pa": "verified", "attributes": "verified", "personality": "verified",
            "contract.wage_weekly": "verified", "contract.expires": "verified", "market_value": "verified",
            "contract.loan_listed": "unconfirmed",  # o próprio Dumper.cs diz "nog niet geverifieerd"
            "birth_date": "derived", "preferred_foot": "derived", "age": "derived",
            "natural_positions": "derived", "accomplished_positions": "derived",
        }
        extra = {k: r[k] for k in ("teamType", "ownerTeamType", "transferTo", "transferDate", "natId", "birthDoy") if k in r}
        if unknown_attr:
            extra["unmapped_attrs"] = unknown_attr
        pos_all = list(r.get("posArr") or [])
        pos_nat = list(r.get("posNat") or pos_all)
        return NormalizedPlayer(
            source_uid=uid,
            unique_id=uid,  # FMSuperScout lê o Unique ID do objeto (OBJ_DUNI)
            name=r.get("name") or "?",
            birth_date=birth,
            birth_year=r.get("birthYear"),
            age=r.get("age"),
            gender="female" if r.get("gender") == 1 else "male",
            nationalities=list(r.get("nat") or []),
            nation_ids=[r["natId"]] if isinstance(r.get("natId"), int) else [],
            height_cm=r.get("height") or None,
            preferred_foot=_FOOT.get(r.get("foot"), r.get("foot")),
            ca=r.get("ca"),
            pa=r.get("pa"),
            reputation_world=r.get("worldRep"),
            club=ClubRef(name=r.get("club"), reputation=r.get("clubRep"), division=r.get("div")) if r.get("club") else None,
            contract=contract,
            market_value=r.get("value"),
            natural_positions=pos_nat,
            accomplished_positions=[p for p in pos_all if p not in pos_nat],
            attributes=attrs,
            field_status=status,
            extra=extra,
        )
