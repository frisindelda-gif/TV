"""Utilitários partilhados pelos conectores."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from fm27si.schemas import ImportBundle


class Connector(Protocol):
    kind: str

    def load(self, path: Path) -> ImportBundle: ...


class ConnectorError(RuntimeError):
    """Fonte ilegível, versão não suportada ou ferramenta externa em falta."""


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:  # só leitura
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def mtime_of(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(tzinfo=None)


def season_label(game_date: date | None) -> str | None:
    """Época ao estilo europeu (Jul–Jun). Valor DERIVADO: ligas de ano civil diferem."""
    if game_date is None:
        return None
    start = game_date.year if game_date.month >= 7 else game_date.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def parse_iso_date(s: object) -> date | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None
