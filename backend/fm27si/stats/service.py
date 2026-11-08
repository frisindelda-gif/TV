"""Orquestração por importação: inventário de campos, disponibilidade, descoberta, aprovações."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from fm27si.orm import ImportRun, MetricDefinitionRow, MetricDiscoveryProposal, SaveMetricAvailability, SaveStatField
from fm27si.stats import repository
from fm27si.stats.availability import compute_availability, field_inventory
from fm27si.stats.discovery import infer, unmapped_fields
from fm27si.stats.mapping import CONNECTOR_PROFILE


def process_run(s: Session, run: ImportRun) -> dict[str, Any]:
    """Passos 3–6 da integração com o FM27 (secção 15): campos → mapeamento → disponibilidade → propostas."""
    rd, cat, _v = repository.run_stats(s, run, "club")
    rd_or_none = rd if rd.n else None
    inventory = field_inventory(rd_or_none)
    s.execute(delete(SaveStatField).where(SaveStatField.run_id == run.id))
    if inventory:
        s.execute(insert(SaveStatField), [{"run_id": run.id, **f} for f in inventory])
    avail = _store_availability(s, run, cat, rd_or_none)

    now = datetime.now()
    proposals = 0
    for f in unmapped_fields(inventory):
        p = s.scalar(select(MetricDiscoveryProposal).where(MetricDiscoveryProposal.data_source == f["data_source"],
                                                          MetricDiscoveryProposal.raw_key == f["raw_key"]))
        sample = {k: f[k] for k in ("players_with_value", "min_value", "max_value", "mean_value", "integer_share")}
        if p is None:
            s.add(MetricDiscoveryProposal(data_source=f["data_source"], raw_key=f["raw_key"], status="pending",
                                          first_run_id=run.id, last_run_id=run.id, proposal=infer(f["raw_key"], sample, cat),
                                          sample=sample, created_at=now))
            proposals += 1
        else:
            p.last_run_id, p.sample = run.id, sample
    s.flush()
    counts: dict[str, int] = {}
    for a in avail:
        counts[a["status"]] = counts.get(a["status"], 0) + 1
    return {"run_id": run.id, "players_with_stats": rd.n, "fields": len(inventory), "new_proposals": proposals,
            "availability": counts}


def _store_availability(s: Session, run: ImportRun, cat, rd) -> list[dict[str, Any]]:
    avail = compute_availability(cat, rd, run.connector)
    s.execute(delete(SaveMetricAvailability).where(SaveMetricAvailability.run_id == run.id))
    now = datetime.now()
    s.execute(insert(SaveMetricAvailability), [{"run_id": run.id, "computed_at": now, **a} for a in avail])
    return avail


def refresh_availability(s: Session, runs: list[ImportRun]) -> None:
    """Depois de o catálogo mudar (métrica aprovada): a disponibilidade de cada save é refeita."""
    repository.invalidate()
    for run in runs:
        rd, cat, _v = repository.run_stats(s, run, "club")
        _store_availability(s, run, cat, rd if rd.n else None)


def approve(s: Session, p: MetricDiscoveryProposal, overrides: dict[str, Any]) -> MetricDefinitionRow:
    cat, _v, _m = repository.load_catalog(s)
    prop = {**p.proposal, **{k: v for k, v in overrides.items() if v is not None}}
    key = overrides.get("key") or f"custom_{p.raw_key}"
    if key in cat.metrics:
        raise ValueError(f"já existe uma métrica com a chave {key}")
    field_key = p.raw_key if p.raw_key not in cat.fields else f"custom_{p.raw_key}"
    mtype = prop.get("type", "count")
    if mtype not in ("count", "value", "percentage"):
        mtype = "value"
    per90 = bool(prop.get("per90", True)) and mtype in ("count", "value")
    definition = {
        "id": key, "name": prop["name"], "alt_name": None, "description": prop.get("meaning", ""),
        "category": prop.get("category", "custom"), "type": mtype, "unit": prop.get("unit", "count"),
        "formulas": [{"field": field_key}], "per90": per90, "percentile": True,
        "direction": prop.get("direction", "higher"), "composite": True, "composed": False,
        "eligibility": {}, "data_source": f"Campo '{p.raw_key}' ({p.data_source}), aprovado manualmente",
    }
    row = MetricDefinitionRow(
        key=key, builtin=False, category=definition["category"], definition=definition,
        groups=list(prop.get("groups") or []), created_at=datetime.now(),
        custom_field={"key": field_key, "raw_key": p.raw_key, "data_source": p.data_source,
                      "name": prop["name"], "unit": definition["unit"], "description": definition["description"]},
    )
    # Validação completa antes de gravar (rejeita definições incoerentes).
    from fm27si.stats.catalog import Catalog  # noqa: PLC0415

    existing = s.scalars(select(MetricDefinitionRow).where(MetricDefinitionRow.builtin.is_(False))).all()
    Catalog(custom=[*[{**r.definition, "groups": r.groups} for r in existing], {**definition, "groups": row.groups}],
            custom_fields={**{r.custom_field["key"]: (r.custom_field["name"], r.custom_field["unit"], "")
                              for r in existing if r.custom_field},
                           field_key: (prop["name"], definition["unit"], definition["description"])})
    s.add(row)
    p.status, p.decided_at, p.created_metric_key = "approved", datetime.now(), key
    s.flush()
    connectors = [c for c, prof in CONNECTOR_PROFILE.items() if prof == p.data_source]
    runs = s.scalars(select(ImportRun).where(ImportRun.connector.in_(connectors))).all()
    refresh_availability(s, list(runs))
    return row


def reject(s: Session, p: MetricDiscoveryProposal) -> None:
    p.status, p.decided_at = "rejected", datetime.now()
