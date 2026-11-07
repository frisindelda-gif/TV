"""Endpoints do motor de avaliação: Position Lab, rankings e avaliação no perfil."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from fm27si.catalog import ATTRIBUTES
from fm27si.evaluation.defaults import original_spec
from fm27si.evaluation.engine import describe_metric, evaluate_player
from fm27si.evaluation.service import (
    active_model,
    ensure_original,
    evaluate_run,
    evaluation_state,
    mark_active,
    model_spec,
    player_detail,
    rankings,
)
from fm27si.evaluation.spec import POSITIONS, RANKING_GROUPS, EvaluationSpec
from fm27si.orm import EvaluationModel, ImportRun, Player, PlayerSnapshot, SnapshotAttributes

CATEGORY_LABEL = {
    "technical": "Técnicas", "mental": "Mentais", "physical": "Físicas", "tactical": "Táticas",
    "position_specific": "Específicas da posição",
}


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    base_id: int | None = Field(None, description="Modelo a duplicar; omisso = original")


class ModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    spec: dict | None = None


class RecalcIn(BaseModel):
    model_id: int | None = None
    run_id: int | None = None
    career_id: int | None = None


class PreviewIn(BaseModel):
    spec: dict
    player_id: int
    run_id: int | None = None


def _model_out(s: Session, m: EvaluationModel, *, full: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": m.id, "key": m.key, "name": m.name, "description": m.description, "builtin": m.builtin,
        "active": m.active, "base_key": m.base_key, "spec_hash": m.spec_hash,
        "created_at": m.created_at, "updated_at": m.updated_at,
        "modified_from_original": (not m.builtin) and m.spec_hash != original_spec().spec_hash(),
    }
    if full:
        spec = model_spec(m)
        out["spec"] = m.spec
        out["metrics"] = [{**describe_metric(spec, x.key), "category_label": CATEGORY_LABEL[x.category]} for x in spec.metrics]
    return out


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "modelo"
    return f"{base[:50]}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def register(app: FastAPI, get_session, latest_run) -> None:  # noqa: C901 - registo de rotas
    def model_or_404(s: Session, model_id: int | None) -> EvaluationModel:
        if model_id is None:
            return active_model(s)
        ensure_original(s)
        m = s.get(EvaluationModel, model_id)
        if m is None:
            raise HTTPException(404, "Modelo não encontrado")
        return m

    def editable(m: EvaluationModel) -> None:
        if m.builtin:
            raise HTTPException(409, "O modelo original não pode ser alterado. Duplique-o para editar.")

    # ---------------------------------------------------------------- catálogo
    @app.get("/api/evaluation/catalog")
    def catalog():
        return {
            "positions": [{"key": k, "pt": pt, "name": name} for k, (pt, name) in POSITIONS.items()],
            "ranking_groups": [{"key": k, "label": label, "positions": list(ps)} for k, (label, ps) in RANKING_GROUPS.items()],
            "categories": CATEGORY_LABEL,
            "attributes": [{"key": a.key, "label": a.label, "category": a.category} for a in ATTRIBUTES.values()],
            "scale": "Atributos 1–20 normalizados para 0–100: n(a) = (a − 1) / 19 × 100",
        }

    # ------------------------------------------------------------------ modelos
    @app.get("/api/evaluation/models")
    def list_models(s: Session = Depends(get_session)):
        ensure_original(s)
        s.commit()
        return [_model_out(s, m) for m in s.scalars(select(EvaluationModel).order_by(EvaluationModel.builtin.desc(), EvaluationModel.id))]

    @app.get("/api/evaluation/models/{model_id}")
    def get_model(model_id: int, s: Session = Depends(get_session)):
        m = model_or_404(s, model_id)
        s.commit()
        return _model_out(s, m, full=True)

    @app.post("/api/evaluation/models")
    def create_model(body: ModelCreate, s: Session = Depends(get_session)):
        original = ensure_original(s)
        base = s.get(EvaluationModel, body.base_id) if body.base_id else original
        if base is None:
            raise HTTPException(404, "Modelo base não encontrado")
        now = datetime.now()
        m = EvaluationModel(key=_slug(body.name), name=body.name, description=body.description, builtin=False,
                            active=False, base_key=base.key, spec=dict(base.spec), spec_hash=base.spec_hash,
                            created_at=now, updated_at=now)
        s.add(m)
        s.commit()
        return _model_out(s, m, full=True)

    @app.put("/api/evaluation/models/{model_id}")
    def update_model(model_id: int, body: ModelUpdate, s: Session = Depends(get_session)):
        m = model_or_404(s, model_id)
        editable(m)
        if body.spec is not None:
            try:
                spec = EvaluationSpec.model_validate(body.spec)
            except ValidationError as e:
                raise HTTPException(422, [{"loc": err["loc"], "msg": err["msg"]} for err in e.errors()]) from e
            m.spec, m.spec_hash = spec.model_dump(mode="json"), spec.spec_hash()
        if body.name is not None:
            m.name = body.name
        if body.description is not None:
            m.description = body.description
        m.updated_at = datetime.now()
        s.commit()
        return _model_out(s, m, full=True)

    @app.post("/api/evaluation/models/{model_id}/duplicate")
    def duplicate_model(model_id: int, s: Session = Depends(get_session)):
        base = model_or_404(s, model_id)
        desc = None if base.builtin else base.description  # a nota "duplique para editar" não se aplica à cópia
        return create_model(ModelCreate(name=f"{base.name} (cópia)", description=desc, base_id=base.id), s)

    @app.post("/api/evaluation/models/{model_id}/reset")
    def reset_model(model_id: int, s: Session = Depends(get_session)):
        """Restaura os pesos originais (mantém nome e descrição)."""
        m = model_or_404(s, model_id)
        editable(m)
        spec = original_spec()
        m.spec, m.spec_hash, m.updated_at = spec.model_dump(mode="json"), spec.spec_hash(), datetime.now()
        s.commit()
        return _model_out(s, m, full=True)

    @app.post("/api/evaluation/models/{model_id}/activate")
    def activate_model(model_id: int, s: Session = Depends(get_session)):
        m = model_or_404(s, model_id)
        mark_active(s, m)
        s.commit()
        return _model_out(s, m)

    @app.delete("/api/evaluation/models/{model_id}")
    def delete_model(model_id: int, s: Session = Depends(get_session)):
        m = model_or_404(s, model_id)
        editable(m)
        if m.active:
            raise HTTPException(409, "Ative outro modelo antes de apagar este.")
        s.delete(m)
        s.commit()
        return {"deleted": model_id}

    @app.post("/api/evaluation/recalculate")
    def recalculate(body: RecalcIn, s: Session = Depends(get_session)):
        m = model_or_404(s, body.model_id)
        run = s.get(ImportRun, body.run_id) if body.run_id else latest_run(s, body.career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        out = evaluate_run(s, run.id, m)
        s.commit()
        return out

    @app.get("/api/evaluation/state")
    def state(career_id: int | None = None, model_id: int | None = None, s: Session = Depends(get_session)):
        m = model_or_404(s, model_id)
        run = latest_run(s, career_id)
        s.commit()
        return {"run_id": run.id, "model_id": m.id, "state": evaluation_state(s, run.id, m)}

    @app.post("/api/evaluation/preview")
    def preview(body: PreviewIn, s: Session = Depends(get_session)):
        """Avalia um jogador com pesos ainda não guardados (Position Lab)."""
        try:
            spec = EvaluationSpec.model_validate(body.spec)
        except ValidationError as e:
            raise HTTPException(422, [{"loc": err["loc"], "msg": err["msg"]} for err in e.errors()]) from e
        snap = _snapshot(s, body.player_id, body.run_id)
        arow = s.get(SnapshotAttributes, snap.id)
        attrs = {k: getattr(arow, k) for k in ATTRIBUTES} if arow else {}
        out = evaluate_player(spec, attrs, (snap.field_status or {}).get("attributes"))
        return {"player_id": body.player_id, "name": snap.name, **out}

    # ---------------------------------------------------------------- rankings
    @app.get("/api/rankings")
    def get_rankings(
        s: Session = Depends(get_session),
        group: str = "ST",
        career_id: int | None = None,
        run_id: int | None = None,
        model_id: int | None = None,
        sort: str = "score",
        order: Literal["asc", "desc"] = "desc",
        eligible_only: bool = True,
        min_age: int | None = None,
        max_age: int | None = None,
        club: str | None = None,
        nationality: str | None = None,
        min_confidence: Literal["medium", "high"] | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        m = model_or_404(s, model_id)
        run = s.get(ImportRun, run_id) if run_id else latest_run(s, career_id)
        if run is None:
            raise HTTPException(404, "Importação não encontrada")
        try:
            out = rankings(s, run, m, group, sort=sort, order=order, eligible_only=eligible_only, min_age=min_age,
                           max_age=max_age, club=club, nationality=nationality, confidence_min=min_confidence,
                           limit=limit, offset=offset)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        s.commit()
        return {"run_id": run.id, "model": {"id": m.id, "name": m.name, "spec_hash": m.spec_hash}, **out}

    # ------------------------------------------------------------------ perfil
    @app.get("/api/players/{player_id}/evaluation")
    def player_evaluation(player_id: int, run_id: int | None = None, position: str | None = None,
                          model_id: int | None = None, s: Session = Depends(get_session)):
        m = model_or_404(s, model_id)
        snap = _snapshot(s, player_id, run_id)
        out = player_detail(s, snap, m, position)
        s.commit()
        return out


def _snapshot(s: Session, player_id: int, run_id: int | None) -> PlayerSnapshot:
    if s.get(Player, player_id) is None:
        raise HTTPException(404, "Jogador não encontrado")
    q = select(PlayerSnapshot).where(PlayerSnapshot.player_id == player_id)
    q = q.where(PlayerSnapshot.run_id == run_id) if run_id else q.order_by(PlayerSnapshot.run_id.desc())
    snap = s.scalar(q.limit(1))
    if snap is None:
        raise HTTPException(404, "Sem dados para esta importação")
    return snap

