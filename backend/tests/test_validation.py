"""Validação de CA, PA e atributos."""

import pytest

from fm27si.catalog import ATTRIBUTES, PERSONALITY_KEYS, PLAYER_ATTRIBUTE_KEYS
from fm27si.schemas import NormalizedPlayer
from fm27si.validation import quality_of, validate_player


def _player(**kw) -> NormalizedPlayer:
    attrs = {k: 10 + (i % 7) for i, k in enumerate(ATTRIBUTES)}
    base = dict(source_uid=1, unique_id=1, name="Teste", ca=120, pa=150, attributes=attrs)
    base.update(kw)
    return NormalizedPlayer(**base)


def codes(p):
    return {(i.field, i.code) for i in validate_player(p)}


def test_catalog_has_52_player_attributes_and_8_personality():
    assert len(PLAYER_ATTRIBUTE_KEYS) == 52
    assert len(PERSONALITY_KEYS) == 8
    cats = {a.category for a in ATTRIBUTES.values()}
    assert cats == {"technical", "mental", "physical", "goalkeeping", "hidden", "personality"}


def test_valid_player_is_ok():
    p = _player()
    assert validate_player(p) == []
    assert quality_of(validate_player(p)) == "ok"


@pytest.mark.parametrize("ca", [0, -1, 201, 999])
def test_ca_out_of_range_is_error(ca):
    assert ("ca", "out_of_range") in codes(_player(ca=ca))
    assert quality_of(validate_player(_player(ca=ca))) == "error"


@pytest.mark.parametrize("pa", [0, 201])
def test_pa_out_of_range_is_error(pa):
    assert ("pa", "out_of_range") in codes(_player(pa=pa))


def test_pa_range_code_accepted_when_pa_missing():
    assert codes(_player(pa=None, pa_range_code=-95)) == set()
    assert ("pa_range_code", "invalid") in codes(_player(pa=None, pa_range_code=-500))


def test_missing_ca_pa_are_warnings_not_invented():
    p = _player(ca=None, pa=None)
    c = codes(p)
    assert ("ca", "missing") in c and ("pa", "missing") in c
    assert p.ca is None and p.pa is None  # validação não altera
    assert quality_of(validate_player(p)) == "warning"


def test_ca_above_pa_is_warning():
    assert ("ca", "ca_above_pa") in codes(_player(ca=160, pa=150))


@pytest.mark.parametrize("v,code", [(0, "out_of_range"), (26, "out_of_range"), (22, "edited_scale")])
def test_attribute_ranges(v, code):
    p = _player()
    p.attributes["pace"] = v
    assert ("attributes.pace", code) in codes(p)


def test_unknown_attribute_key_is_error():
    p = _player()
    p.attributes["velocidade_magica"] = 10
    assert ("attributes.velocidade_magica", "unknown_key") in codes(p)


def test_incomplete_attributes_warning():
    p = _player()
    del p.attributes["pace"]
    del p.attributes["ambition"]
    c = codes(p)
    assert ("attributes", "incomplete") in c
    assert ("attributes", "personality_incomplete") in c


def test_constant_attribute_block_flags_bad_read():
    p = _player(attributes={k: 1 for k in PLAYER_ATTRIBUTE_KEYS})
    assert ("attributes", "constant_block") in codes(p)


def test_position_validation():
    assert ("positions.XX", "unknown_key") in codes(_player(positions={"XX": 10}))
    assert ("positions.ST", "out_of_range") in codes(_player(positions={"ST": 21}))
    assert codes(_player(positions={"ST": 20, "GK": 1})) == set()
