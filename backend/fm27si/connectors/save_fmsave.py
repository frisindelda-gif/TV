"""Save Reader: importação de ficheiros ``.fm`` através da biblioteca ``fmsave`` (MIT).

Decisão (ver docs/DECISOES.md, D-03): o fmsave é Python puro, só-leitura, sem rede, e expõe
uma API pública (``fmsave.open`` → ``Save.players()``, ``clubs()``, ``contracts()``,
``player_season_stats()``, ...). Integramo-lo como dependência fixada (``fmsave==0.10.0``) em
vez de copiar código.

Proteções:
- O ficheiro do save nunca é aberto para escrita. Por omissão copiamos o ``.fm`` para uma
  pasta temporária e lemos a cópia (o FM pode estar a gravar o original).
- No FM27, o fmsave não marca nenhum campo de jogador como verificado contra o ecrã do jogo
  (só campos de staff). Todos os campos de jogador vindos deste conector ficam
  ``unconfirmed`` até termos verificação própria.
"""

from __future__ import annotations

import shutil
import tempfile
import warnings as _warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from fm27si.catalog import ATTRIBUTES, POSITION_KEYS
from fm27si.connectors.base import ConnectorError, mtime_of, season_label, sha256_of
from fm27si.schemas import (
    CareerInfo,
    ClubRecord,
    ClubRef,
    Contract,
    ImportBundle,
    NormalizedPlayer,
    SeasonStats,
    SourceInfo,
)

KIND = "save_file"
FMSAVE_PIN = "0.10.0"

_ATTR_FIELDS = {a.key: a.fmsave_field for a in ATTRIBUTES.values() if a.category != "personality"}
_PERS_FIELDS = {a.key: a.fmsave_field for a in ATTRIBUTES.values() if a.category == "personality"}
# fmsave.Positions usa "stc" para ponta-de-lança; o resto coincide em minúsculas.
_POS_FIELDS = {k: ("stc" if k == "ST" else k.lower()) for k in POSITION_KEYS}

UNAVAILABLE = [
    "nationalities (nomes; o save só guarda ids — nomes vêm da BD instalada do jogo)",
    "club.division (nome da competição requer mapa externo database_id→nome)",
    "gender",
    "roles",
    "contract.transfer_listed / not_for_sale (não expostos pelo fmsave 0.10)",
    "asking price",
]

_STAT_EXTRA = (
    "shots", "shots_on_target", "passes_attempted", "passes_completed", "key_passes",
    "progressive_passes", "dribbles", "tackles_attempted", "tackles_completed", "interceptions",
    "possession_won", "possession_lost", "distance_km", "non_penalty_expected_goals",
    "expected_goals_prevented", "goals_allowed", "headers_won", "clearances", "blocks",
    "saves_held", "saves_parried", "saves_tipped", "fouls_made", "fouls_against",
    "mistakes_leading_to_goal", "rated_appearances", "aerial_challenges_attempted",
    "shots_on_target_faced", "clear_cut_chances_created", "crosses_attempted", "crosses_completed",
    "high_intensity_sprints", "pressures_attempted", "pressures_completed", "open_play_key_passes",
)


# Campos de identificação/colunas já guardadas à parte (não vão para ``extra``).
_STAT_NOT_EXTRA = {
    "player_uid", "player_name", "kind", "team_id", "club_uid", "club_name", "club_short_name", "team_slot",
    "starts", "substitute_appearances", "minutes", "goals", "assists", "average_rating", "player_of_the_match",
    "expected_goals", "expected_assists", "yellow_cards", "red_cards", "clean_sheets",
}


def _all_numeric_stats(s: Any) -> dict[str, float | int | None]:
    """TODOS os campos numéricos da linha de estatísticas (a descoberta automática precisa deles)."""
    import dataclasses  # noqa: PLC0415

    if dataclasses.is_dataclass(s):
        names = [f.name for f in dataclasses.fields(s)]
    else:  # objetos de teste simples
        names = [n for n in vars(s) if not n.startswith("_")]
    out: dict[str, float | int | None] = {}
    for n in names:
        if n in _STAT_NOT_EXTRA:
            continue
        v = getattr(s, n, None)
        if v is None or (isinstance(v, (int, float)) and not isinstance(v, bool)):
            out[n] = v
    return out


def _import_fmsave():
    try:
        import fmsave  # noqa: PLC0415
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise ConnectorError("fmsave não instalado. Instale com: pip install 'fm27si[save]'") from e
    if fmsave.__version__ != FMSAVE_PIN:
        _warnings.warn(f"fmsave {fmsave.__version__} != versão validada {FMSAVE_PIN}", stacklevel=2)
    return fmsave


def _label(coded: Any) -> str | None:
    if coded is None:
        return None
    label = getattr(coded, "label", None)
    name = getattr(label, "name", None)
    if name is None or name == "UNKNOWN":
        return f"UNKNOWN_{getattr(coded, 'raw', '?')}"
    return name


class FmsaveSaveConnector:
    kind = KIND

    def __init__(self, *, copy_first: bool = True, opener=None) -> None:
        self.copy_first = copy_first
        self._opener = opener  # injetável nos testes

    # ------------------------------------------------------------------ API
    def load(self, path: Path) -> ImportBundle:
        if not path.is_file():
            raise ConnectorError(f"Ficheiro não encontrado: {path}")
        if path.suffix.lower() != ".fm":
            raise ConnectorError("O Save Reader só aceita ficheiros .fm")
        sha = sha256_of(path)
        mtime = mtime_of(path)
        with tempfile.TemporaryDirectory(prefix="fm27si-") as tmp:
            target = path
            if self.copy_first:
                target = Path(tmp) / path.name
                shutil.copy2(path, target)  # lemos a cópia; o original fica intacto
            opener = self._opener or _import_fmsave().open
            try:
                with opener(target) as save:
                    bundle = self.from_save(save)
            except ConnectorError:
                raise
            except Exception as e:
                raise ConnectorError(f"fmsave não conseguiu ler o save: {type(e).__name__}: {e}") from e
        src = bundle.source.model_copy(
            update={"source_path": str(path), "source_sha256": sha, "source_mtime": mtime, "read_at": mtime}
        )
        return bundle.model_copy(update={"source": src})

    def from_save(self, save: Any) -> ImportBundle:
        warnings: list[str] = []
        info = save.info
        game = getattr(info, "game", None)
        known = getattr(info, "known_build", None)
        if game == "FM27" and not known:
            warnings.append(f"Build FM27 não registada no fmsave ({info.build}): leitura com layouts emprestados.")
        if game == "FM27":
            warnings.append("fmsave: no FM27 nenhum campo de jogador está verificado contra o jogo (todos 'unconfirmed').")

        try:
            import fmsave as _fm  # noqa: PLC0415

            tool_version = _fm.__version__
        except ImportError:  # pragma: no cover
            tool_version = None

        source = SourceInfo(
            connector=KIND,
            tool=f"fmsave {tool_version or '?'}",
            tool_version=tool_version,
            read_at=datetime.now(),
            game=game,
            game_version=getattr(info, "build", None),
            game_version_supported=known,
            game_date=getattr(info, "game_date", None),
            game_date_status="unconfirmed",
            currency="save_base_unit",
        )

        managed = self._safe(lambda: list(save.managed_clubs()), warnings, "managed_clubs") or []
        career = CareerInfo(
            save_name=getattr(info, "save_name", None) or getattr(info, "file_name", None),
            manager_name=next((m.manager_name for m in managed if m.manager_name), None),
            managed_club=managed[0].club_name if managed else None,
        )

        clubs = [
            ClubRecord(
                source_uid=c.uid,
                unique_id=c.unique_id,
                name=c.name,
                short_name=c.short_name,
                reputation=c.reputation,
                nation_id=c.nation_id,
                last_league_position=c.last_league_position,
            )
            for c in (self._safe(lambda: list(save.clubs()), warnings, "clubs") or [])
        ]

        stats_by_player: dict[int, list[SeasonStats]] = defaultdict(list)
        season = season_label(getattr(info, "game_date", None))  # derivado
        for s in self._safe(lambda: list(save.player_season_stats()), warnings, "player_season_stats") or []:
            stats_by_player[s.player_uid].append(self._stats(s, season))

        players_table = save.players()  # obrigatório: se falhar, a importação falha
        players = []
        for p in players_table:
            try:
                players.append(self._player(p, stats_by_player.get(p.uid, []), game))
            except Exception as e:
                warnings.append(f"Jogador uid={getattr(p, 'uid', '?')} ignorado: {e}")

        return ImportBundle(
            source=source,
            career=career,
            players=players,
            clubs=clubs,
            unavailable_fields=UNAVAILABLE,
            warnings=warnings,
        )

    # ------------------------------------------------------------ mapping
    @staticmethod
    def _safe(fn, warnings: list[str], reader: str):
        try:
            with _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always")
                out = fn()
            for w in caught:
                warnings.append(f"{reader}: {w.message}")
            return out
        except Exception as e:
            warnings.append(f"Leitor '{reader}' indisponível: {type(e).__name__}: {e}")
            return None

    @staticmethod
    def _stats(s: Any, season: str | None) -> SeasonStats:
        return SeasonStats(
            season=season,
            competition_kind=str(getattr(s.kind, "value", s.kind)),
            club_name=s.club_name,
            starts=s.starts,
            sub_appearances=s.substitute_appearances,
            minutes=s.minutes,
            goals=s.goals,
            assists=s.assists,
            average_rating=s.average_rating,
            player_of_the_match=s.player_of_the_match,
            expected_goals=s.expected_goals,
            expected_assists=s.expected_assists,
            yellow_cards=s.yellow_cards,
            red_cards=s.red_cards,
            clean_sheets=s.clean_sheets,
            extra=_all_numeric_stats(s),
        )

    @staticmethod
    def _player(p: Any, stats: list[SeasonStats], game: str | None) -> NormalizedPlayer:
        attrs = {key: int(getattr(p.attributes, f)) for key, f in _ATTR_FIELDS.items()}
        if p.personality is not None:
            attrs.update({key: int(getattr(p.personality, f)) for key, f in _PERS_FIELDS.items()})
        positions = {k: int(getattr(p.positions, f)) for k, f in _POS_FIELDS.items()}
        positions = {k: v for k, v in positions.items() if v > 0}

        c = p.contract
        contract = Contract(
            wage_weekly=c.wage if c else None,
            start=c.start if c else None,
            expires=c.end if c else None,
            squad_status=_label(c.squad_status) if c else None,
            on_loan=p.on_loan,
            loan_parent_club=p.loan_parent_club_name,
            loan_end=p.loan_end,
        )
        tv_state = getattr(p.transfer_value_state, "value", p.transfer_value_state)
        value = p.transfer_value if tv_state == "ok" else None

        # O fmsave declara "unconfirmed" para todos os campos de jogador no FM27.
        status_all = "unconfirmed"
        status = {f: status_all for f in (
            "ca", "pa", "attributes", "personality", "positions", "contract.wage_weekly",
            "contract.expires", "market_value", "reputation", "season_stats", "birth_date",
        )}
        status["age"] = "derived"

        nat = [p.nation_id] if p.nation_id is not None else []
        nat += list(p.second_nation_ids)
        pos_nat = [x.upper() if x != "stc" else "ST" for x in p.natural_positions]
        pos_acc = [x.upper() if x != "stc" else "ST" for x in p.accomplished_positions]
        return NormalizedPlayer(
            source_uid=p.uid,
            unique_id=p.unique_id,
            name=p.name or p.full_name or p.legal_name or "?",
            first_name=p.first_name,
            last_name=p.last_name,
            common_name=p.common_name,
            birth_date=p.birth_date,
            birth_year=p.birth_date.year if p.birth_date else None,
            age=p.age,
            nation_ids=nat,
            height_cm=p.height_cm or None,
            foot_left=p.left_foot,
            foot_right=p.right_foot,
            ca=p.ability.current,
            pa=p.ability.potential,
            pa_range_code=p.ability.potential_range_code,
            reputation_home=p.reputation.home,
            reputation_current=p.reputation.current,
            reputation_world=p.reputation.world,
            club=ClubRef(
                source_uid=p.club_uid,
                name=p.club_name,
                short_name=p.club_short_name,
                reputation=p.club_reputation,
            ) if p.club_uid is not None else None,
            contract=contract,
            market_value=value,
            positions=positions,
            natural_positions=pos_nat,
            accomplished_positions=pos_acc,
            attributes=attrs,
            traits=[_label(t) for t in p.traits],
            season_stats=stats,
            field_status=status,
            extra={"transfer_value_state": tv_state, "club_join_date": p.club_join_date.isoformat() if p.club_join_date else None},
        )
