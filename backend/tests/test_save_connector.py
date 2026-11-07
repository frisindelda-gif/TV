"""Save Reader (fmsave).

Não temos (nem podemos publicar) um .fm real do FM27. Os testes constroem um objeto ``Save``
falso com as dataclasses REAIS do fmsave 0.10.0 (``fmsave.Player``, ``Attributes``, ...).
Se o fmsave renomear um campo que o adaptador usa, estes testes falham.

O teste com um save real corre só se ``FM27SI_REAL_SAVE`` apontar para um .fm.
"""

from __future__ import annotations

import dataclasses
import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

fmsave = pytest.importorskip("fmsave")

from fm27si.catalog import PLAYER_ATTRIBUTE_KEYS  # noqa: E402
from fm27si.connectors.base import ConnectorError, sha256_of  # noqa: E402
from fm27si.connectors.save_fmsave import FMSAVE_PIN, FmsaveSaveConnector  # noqa: E402
from fm27si.importer import import_bundle  # noqa: E402
from fm27si.integrity import integrity_report  # noqa: E402
from tests.helpers import build  # noqa: E402


def test_fmsave_version_is_pinned():
    assert fmsave.__version__ == FMSAVE_PIN


def _attributes(seed: int):
    names = [f.name for f in dataclasses.fields(fmsave.Attributes)]
    assert len(names) == 52
    return fmsave.Attributes(**{n: 1 + (i + seed) % 20 for i, n in enumerate(names)})


def _player(uid: int, unique_id: int | None, name: str, ca: int, pa: int | None, *, range_code=None, club_uid=7):
    from fmsave.models.common import TransferValueState

    return build(
        fmsave.Player,
        uid=uid,
        unique_id=unique_id,
        name=name,
        first_name=name.split()[0],
        last_name=name.split()[-1],
        birth_date=date(2008, 3, 14),
        age=18,
        nation_id=31,
        second_nation_ids=(44,),
        height_cm=181,
        ability=fmsave.Ability(current=ca, potential=pa, potential_range_code=range_code),
        reputation=fmsave.Reputation(bucket=1, home=1200, current=800, world=300),
        club_uid=club_uid,
        club_name="Clube Exemplo" if club_uid is not None else None,
        club_short_name="Exemplo" if club_uid is not None else None,
        club_reputation=4000,
        natural_positions=("stc",),
        accomplished_positions=("amc",),
        personality=fmsave.Personality(
            adaptability=10, ambition=15, loyalty=11, pressure=12, professionalism=17,
            sportsmanship=13, temperament=14, controversy=4,
        ),
        attributes=_attributes(uid),
        raw_attributes=_attributes(uid),
        left_foot=8,
        right_foot=20,
        positions=build(fmsave.Positions, stc=20, amc=16, gk=1),
        transfer_value=1_250_000,
        transfer_value_state=TransferValueState.OK,
        contract=build(fmsave.Contract, player_uid=uid, wage=3500, start=date(2025, 7, 1), end=date(2029, 6, 30)),
        on_loan=False,
    )


class FakeSave:
    def __init__(self, players, *, stats=(), stats_error=False, game="FM27", known=True):
        self._players = players
        self._stats = stats
        self._stats_error = stats_error
        self.info = build(
            fmsave.SaveInfo,
            game=game,
            build="27.0.0+2486695",
            known_build=known,
            game_date=date(2026, 9, 1),
            save_name="Carreira Exemplo",
            file_name="exemplo.fm",
        )

    def players(self):
        return list(self._players)

    def clubs(self):
        return [build(fmsave.Club, uid=7, unique_id=555, name="Clube Exemplo", short_name="Exemplo", reputation=4000, nation_id=31)]

    def managed_clubs(self):
        return [build(fmsave.ManagedClub, club_uid=7, club_name="Clube Exemplo", club_short_name="Exemplo", manager_name="Treinador Teste")]

    def player_season_stats(self):
        if self._stats_error:
            raise fmsave.UnsupportedGameError("secção com schema diferente")
        return list(self._stats)


def _opener(save):
    @contextmanager
    def _open(path):
        assert Path(path).suffix == ".fm"
        yield save

    return _open


@pytest.fixture
def fake_fm(tmp_path) -> Path:
    p = tmp_path / "exemplo.fm"
    p.write_bytes(b"not a real save, only opened through the fake opener")
    return p


def _stats_row(uid):
    from fmsave.models.season_stats import SeasonStatsKind

    return build(fmsave.PlayerSeasonStats, player_uid=uid, kind=SeasonStatsKind.LEAGUE, club_name="Clube Exemplo",
                 starts=10, minutes=900, goals=7, assists=3, average_rating=7.21, expected_goals=5.4)


def test_maps_players_from_fmsave_types(fake_fm):
    save = FakeSave([_player(1, 1001, "Ana Exemplo", 120, 175), _player(2, None, "Bea Teste", 90, None, range_code=-95)],
                    stats=[_stats_row(1)])
    b = FmsaveSaveConnector(opener=_opener(save)).load(fake_fm)

    assert b.source.connector == "save_file" and b.source.game == "FM27"
    assert b.source.source_sha256 == sha256_of(fake_fm)
    assert b.career.save_name == "Carreira Exemplo" and b.career.manager_name == "Treinador Teste"
    assert any("nenhum campo de jogador está verificado" in w for w in b.warnings)

    ana, bea = b.players
    assert (ana.ca, ana.pa, ana.unique_id) == (120, 175, 1001)
    assert set(PLAYER_ATTRIBUTE_KEYS) <= set(ana.attributes)
    assert ana.attributes["professionalism"] == 17
    assert ana.positions["ST"] == 20 and ana.positions["AMC"] == 16
    assert ana.natural_positions == ["ST"] and ana.accomplished_positions == ["AMC"]
    assert ana.contract.wage_weekly == 3500 and ana.contract.expires == date(2029, 6, 30)
    assert ana.market_value == 1_250_000
    assert ana.field_status["ca"] == "unconfirmed"
    assert ana.season_stats[0].goals == 7 and ana.season_stats[0].competition_kind == "league"
    assert ana.season_stats[0].season == "2026/27"

    assert bea.pa is None and bea.pa_range_code == -95  # PA não inventado
    assert bea.unique_id is None
    assert len(b.clubs) == 1 and b.clubs[0].unique_id == 555


def test_failing_optional_reader_is_a_warning(fake_fm):
    save = FakeSave([_player(1, 1001, "Ana Exemplo", 120, 175)], stats_error=True)
    b = FmsaveSaveConnector(opener=_opener(save)).load(fake_fm)
    assert len(b.players) == 1
    assert any("player_season_stats" in w for w in b.warnings)


def test_rejects_non_fm_and_missing(tmp_path):
    with pytest.raises(ConnectorError):
        FmsaveSaveConnector().load(tmp_path / "nao_existe.fm")
    p = tmp_path / "x.txt"
    p.write_text("x")
    with pytest.raises(ConnectorError):
        FmsaveSaveConnector().load(p)


def test_real_fmsave_rejects_garbage_file(tmp_path):
    p = tmp_path / "lixo.fm"
    p.write_bytes(b"\x00" * 64)
    with pytest.raises(ConnectorError):
        FmsaveSaveConnector().load(p)


def test_save_file_untouched_and_copy_read(fake_fm):
    before = (sha256_of(fake_fm), fake_fm.stat().st_mtime_ns)
    seen = []

    @contextmanager
    def opener(path):
        seen.append(Path(path))
        yield FakeSave([_player(1, 1001, "Ana Exemplo", 120, 175)])

    FmsaveSaveConnector(opener=opener).load(fake_fm)
    assert seen[0] != fake_fm  # leu a cópia temporária, não o original
    assert (sha256_of(fake_fm), fake_fm.stat().st_mtime_ns) == before


def test_save_import_end_to_end(fake_fm, session):
    save = FakeSave([_player(1, 1001, "Ana Exemplo", 120, 175), _player(2, None, "Bea Teste", 90, None, range_code=-95)],
                    stats=[_stats_row(1)])
    b = FmsaveSaveConnector(opener=_opener(save)).load(fake_fm)
    res = import_bundle(session, b)
    rep = integrity_report(session, res.run.id)
    assert rep["ok"], rep
    assert res.run.player_count == 2


@pytest.mark.skipif(not os.environ.get("FM27SI_REAL_SAVE"), reason="defina FM27SI_REAL_SAVE=caminho.fm")
def test_real_save(session):  # pragma: no cover - depende de ficheiro do utilizador
    b = FmsaveSaveConnector().load(Path(os.environ["FM27SI_REAL_SAVE"]))
    res = import_bundle(session, b)
    rep = integrity_report(session, res.run.id)
    print(res.run.player_count, rep)
    assert res.run.player_count > 0
