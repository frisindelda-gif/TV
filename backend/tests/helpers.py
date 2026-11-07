"""Construtor genérico de dataclasses do fmsave para testes (preenche campos omitidos)."""

from __future__ import annotations

import dataclasses
import typing


def _default_for(tp: object) -> object:
    text = str(tp)
    if "None" in text:
        return None
    origin = typing.get_origin(tp)
    if tp is int:
        return 0
    if tp is float:
        return 0.0
    if tp is str:
        return ""
    if tp is bool:
        return False
    if origin is tuple:
        return ()
    if "Mapping" in text or origin is dict:
        return {}
    return None


def build(cls, **overrides):
    hints = typing.get_type_hints(cls)
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = set(overrides) - names
    if unknown:  # um campo desapareceu/foi renomeado no fmsave
        raise TypeError(f"{cls.__name__} não tem os campos {sorted(unknown)}")
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name in overrides:
            kwargs[f.name] = overrides[f.name]
        elif f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:
            continue
        else:
            kwargs[f.name] = _default_for(hints[f.name])
    return cls(**kwargs)
