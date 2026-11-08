"""Ligação do catálogo/motor à base de dados (GlobalMetricCatalogService persistente).

- As definições built-in vivem no código (versionadas e testadas) e são sincronizadas para
  ``metric_definitions`` / ``position_metric_mappings``.
- As personalizadas (aprovadas a partir de propostas de descoberta) vivem só na BD.
- O catálogo efetivo = built-in + personalizadas; a sua "versão" entra nas chaves de cache.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fm27si.orm import (
    CompositeScoreDefinition,
    ImportRun,
    MetricDefinitionRow,
    PositionMetricMappingRow,
)
from fm27si.stats import catalog_data as data
from fm27si.stats.catalog import Catalog
from fm27si.stats.data import RUN_CACHE, RunStats, load_run_stats
from fm27si.stats.mapping import FieldMapping
from fm27si.stats.percentiles import PCT_CACHE, PercentileResult, Universe

_BUILTIN_HASH = hashlib.sha256(
    json.dumps([data.METRICS, data.POSITION_MAP, data.COMPOSITES], sort_keys=True, default=str).encode()
).hexdigest()[:16]
_lock = threading.Lock()
_catalog_cache: dict[str, tuple[Catalog, dict[str, dict[str, FieldMapping]]]] = {}


def sync_builtin(s: Session) -> None:
    """Escreve o catálogo built-in na BD se a versão do código mudou. Não toca nas personalizadas."""
    marker = s.scalar(select(MetricDefinitionRow).where(MetricDefinitionRow.key == "__builtin_version__"))
    if marker is not None and marker.definition.get("hash") == _BUILTIN_HASH:
        _ensure_composites(s)
        return
    now = datetime.now()
    s.execute(delete(MetricDefinitionRow).where(MetricDefinitionRow.builtin.is_(True)))
    s.execute(delete(PositionMetricMappingRow))
    for m in data.METRICS:
        s.add(MetricDefinitionRow(key=m["id"], builtin=True, category=m["category"], definition=m, groups=[],
                                  created_at=now))
    for g, sections in data.POSITION_MAP.items():
        for title, items in sections:
            for i, it in enumerate(items):
                mid, _, view = it.partition("@")
                s.add(PositionMetricMappingRow(group_key=g, section=title, position=i, metric_key=mid,
                                               view=view or "total"))
    s.add(MetricDefinitionRow(key="__builtin_version__", builtin=True, category="_meta",
                              definition={"hash": _BUILTIN_HASH}, groups=[], created_at=now))
    _ensure_composites(s)
    s.flush()


def _ensure_composites(s: Session) -> None:
    now = datetime.now()
    for c in data.COMPOSITES:
        row = s.scalar(select(CompositeScoreDefinition).where(CompositeScoreDefinition.key == c["key"]))
        comps = [{"metric": k, "weight": 1.0, "invert": False} for k in c["components"]]
        if row is None:
            s.add(CompositeScoreDefinition(key=c["key"], name=c["name"], builtin=True, group_key=c["group"],
                                           components=comps, min_coverage=0.6, created_at=now, updated_at=now,
                                           description="Modelo inicial do documento Statistical Scouting (§5). Duplique para editar."))
        elif row.builtin and row.components != comps:
            row.components, row.updated_at = comps, now


def catalog_version(s: Session) -> str:
    n, last = s.execute(select(func.count(MetricDefinitionRow.id), func.max(MetricDefinitionRow.id))
                        .where(MetricDefinitionRow.builtin.is_(False))).one()
    return f"{_BUILTIN_HASH}:{n}:{last}"


def _db_id(s: Session) -> str:
    """Identidade da base de dados (as caches nunca misturam bases diferentes)."""
    bind = s.get_bind()
    return f"{id(bind)}:{bind.url}"


def load_catalog(s: Session) -> tuple[Catalog, str, dict[str, dict[str, FieldMapping]]]:
    """Catálogo efetivo + versão + mapeamentos personalizados (por fonte de dados)."""
    sync_builtin(s)
    version = f"{_db_id(s)}|{catalog_version(s)}"
    with _lock:
        hit = _catalog_cache.get(version)
    if hit:
        return hit[0], version, hit[1]
    custom_rows = s.scalars(select(MetricDefinitionRow).where(MetricDefinitionRow.builtin.is_(False))).all()
    custom_defs, custom_fields = [], {}
    mappings: dict[str, dict[str, FieldMapping]] = {}
    for r in custom_rows:
        custom_defs.append({**r.definition, "groups": r.groups})
        if r.custom_field:
            f = r.custom_field
            custom_fields[f["key"]] = (f["name"], f["unit"], f.get("description", ""))
            mappings.setdefault(f["data_source"], {})[f["raw_key"]] = FieldMapping(f["raw_key"], f["key"], "custom",
                                                                                   "Métrica personalizada aprovada.")
    cat = Catalog(custom=custom_defs, custom_fields=custom_fields)
    with _lock:
        _catalog_cache[version] = (cat, mappings)
    return cat, version, mappings


def run_stats(s: Session, run: ImportRun, scope: str = "club") -> tuple[RunStats, Catalog, str]:
    if scope not in ("club", "league"):
        raise ValueError(f"âmbito desconhecido: {scope}")
    cat, version, mappings = load_catalog(s)
    from fm27si.stats.mapping import CONNECTOR_PROFILE  # noqa: PLC0415

    custom = mappings.get(CONNECTOR_PROFILE.get(run.connector) or "", {})
    key = (version, run.id, run.imported_at, scope)
    rd = RUN_CACHE.get(key, lambda: load_run_stats(s, run, cat, scope, custom))
    return rd, cat, version


def percentiles(rd: RunStats, cat: Catalog, version: str, key: str, u: Universe) -> PercentileResult:
    return PCT_CACHE.get(rd, cat, key, u, version)


def invalidate() -> None:
    """Depois de aprovar métricas: catálogo, dados e percentis recalculam-se na próxima consulta."""
    with _lock:
        _catalog_cache.clear()
    RUN_CACHE.clear()
    PCT_CACHE.clear()
