"""Configuração local. Sem serviços cloud: tudo vive numa pasta de dados do utilizador."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("FM27SI_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "FM27ScoutingIntelligence"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "fm27si"


def database_url() -> str:
    url = os.environ.get("FM27SI_DATABASE_URL")
    if url:
        return url
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(d / 'fm27si.sqlite3').as_posix()}"


def fmsuperscout_dump_path() -> Path:
    """Onde o scanner do FMSuperScout escreve dump.json (Windows: %LOCALAPPDATA%\\FMSuperScout)."""
    override = os.environ.get("FM27SI_FMSS_DUMP")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / "FMSuperScout" / "dump.json"
