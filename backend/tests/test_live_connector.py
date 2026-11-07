"""Live Connector (dump.json do FMSuperScout)."""

import json

import pytest

from fm27si.catalog import PLAYER_ATTRIBUTE_KEYS
from fm27si.connectors.base import ConnectorError, sha256_of
from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector, _FMSS_TO_KEY


def test_every_fmss_attribute_key_maps_to_catalog():
    # As 52 chaves do Fields.cs do FMSuperScout (47 + 5 escondidos) cobrem o catálogo inteiro.
    assert sorted(_FMSS_TO_KEY.values()) == sorted(PLAYER_ATTRIBUTE_KEYS)


def test_maps_full_player(small_dump_path):
    b = FMSuperScoutLiveConnector().load(small_dump_path)
    assert b.source.connector == "live_memory"
    assert b.source.game == "FM27" and b.source.synthetic is True
    assert str(b.source.game_date) == "2026-08-20"
    assert b.source.source_sha256 == sha256_of(small_dump_path)
    assert b.career.manager_name == "Treinador Ficticio"
    assert len(b.players) == 3

    rui = b.players[0]
    assert rui.unique_id == 91000001
    assert (rui.ca, rui.pa) == (112, 178)
    assert len([k for k in rui.attributes if k in PLAYER_ATTRIBUTE_KEYS]) == 52
    assert rui.attributes["pace"] == 17 and rui.attributes["important_matches"] == 12
    assert rui.attributes["professionalism"] == 18  # personalidade escondida
    assert rui.birth_date.isoformat() == "2009-02-01"  # dia 32 do ano
    assert rui.preferred_foot == "left"
    assert rui.natural_positions == ["AMR"] and rui.accomplished_positions == ["ST"]
    assert rui.contract.wage_weekly == 1500 and rui.contract.not_for_sale is True
    assert rui.contract.on_loan is None  # ownerClub ausente = sem empréstimo
    assert rui.field_status["ca"] == "verified" and rui.field_status["birth_date"] == "derived"
    assert rui.positions == {}  # o dump não tem as classificações 1..20 por posição


def test_loan_and_missing_value_stay_none(small_dump_path):
    gk = FMSuperScoutLiveConnector().load(small_dump_path).players[1]
    assert gk.contract.on_loan is True and gk.contract.loan_parent_club == "SC Vale Ficticio"
    assert gk.market_value is None  # nunca estimado
    assert "positions (classificação 1..20 por posição; só listas natural/acomplished)" in \
        FMSuperScoutLiveConnector().load(small_dump_path).unavailable_fields


def test_rejects_non_dump(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"hello": 1}))
    with pytest.raises(ConnectorError):
        FMSuperScoutLiveConnector().load(p)
    with pytest.raises(ConnectorError):
        FMSuperScoutLiveConnector().load(tmp_path / "nao_existe.json")


def test_rejects_unsupported_game(small_dump):
    small_dump["meta"]["game"] = "FM24"
    with pytest.raises(ConnectorError):
        FMSuperScoutLiveConnector().from_dict(small_dump)


def test_warns_when_game_version_unverified(small_dump):
    small_dump["meta"]["versionOk"] = False
    small_dump["meta"]["gameVersion"] = "27.1"
    b = FMSuperScoutLiveConnector().from_dict(small_dump)
    assert any("não verificada" in w for w in b.warnings)
    assert b.source.game_version_supported is False


def test_corrupt_record_skipped_not_fatal(small_dump):
    small_dump["players"].append({"name": "sem id"})
    b = FMSuperScoutLiveConnector().from_dict(small_dump)
    assert len(b.players) == 3
    assert any("ignorado" in w for w in b.warnings)


def test_connector_never_modifies_source(small_dump_path):
    before = (sha256_of(small_dump_path), small_dump_path.stat().st_mtime_ns)
    FMSuperScoutLiveConnector().load(small_dump_path)
    assert (sha256_of(small_dump_path), small_dump_path.stat().st_mtime_ns) == before
