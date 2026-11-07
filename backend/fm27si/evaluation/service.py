"""Integração do motor com a base de dados: modelos, avaliação em lote, médias, rankings.

O motor (``engine.py``) não conhece a BD; este módulo não faz contas de avaliação.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from fm27si.catalog import ATTRIBUTES
from fm27si.evaluation.defaults import ORIGINAL_KEY, ORIGINAL_NAME, original_spec
from fm27si.evaluation.engine import ATTR_KEYS, compile_spec, confidence, evaluate_batch, evaluate_player
from fm27si.evaluation.spec import POSITIONS, RANKING_GROUPS, EvaluationSpec
from fm27si.orm import (
    EvaluationBaseline,
    EvaluationModel,
    ImportRun,
    Player,
    PlayerEvaluation,
    PlayerSnapshot,
    SnapshotAttributes,
)

FAMILIAR_RATING = 15  # classificação 1–20 a partir da qual o FM considera "competente"


# ------------------------------------------------------------------- modelos

def ensure_original(s: Session) -> EvaluationModel:
    """Garante o modelo original (só de leitura) e que existe um modelo ativo."""
    spec = original_spec()
    now = datetime.now()
    m = s.scalar(select(EvaluationModel).where(EvaluationModel.key == ORIGINAL_KEY))
    if m is None:
        m = EvaluationModel(key=ORIGINAL_KEY, name=ORIGINAL_NAME, builtin=True, active=False,
                            description="Pesos de partida definidos pela aplicação. Duplique para editar.",
                            spec=spec.model_dump(mode="json"), spec_hash=spec.spec_hash(), created_at=now, updated_at=now)
        s.add(m)
        s.flush()
    elif m.spec_hash != spec.spec_hash():  # nova versão da app trouxe pesos originais diferentes
        m.spec, m.spec_hash, m.updated_at = spec.model_dump(mode="json"), spec.spec_hash(), now
    if s.scalar(select(func.count()).where(EvaluationModel.active.is_(True))) == 0:
        m.active = True
    s.flush()
    return m


def active_model(s: Session) -> EvaluationModel:
    ensure_original(s)
    return s.scalar(select(EvaluationModel).where(EvaluationModel.active.is_(True)))


def model_spec(m: EvaluationModel) -> EvaluationSpec:
    return EvaluationSpec.model_validate(m.spec)


# ------------------------------------------------------------ elegibilidade

def eligible_positions(natural: list | None, accomplished: list | None, ratings: dict | None) -> list[str]:
    out = set(natural or []) | set(accomplished or [])
    for k, v in (ratings or {}).items():
        if isinstance(v, (int, float)) and v >= FAMILIAR_RATING:
            out.add(k)
    return [p for p in POSITIONS if p in out]


# --------------------------------------------------------- avaliação em lote

def evaluate_run(s: Session, run_id: int, model: EvaluationModel | None = None) -> dict[str, Any]:
    """Avalia todos os jogadores de uma importação e recalcula as médias por posição."""
    started = datetime.now()
    model = model or active_model(s)
    spec = model_spec(model)
    c = compile_spec(spec)
    S, A = PlayerSnapshot, SnapshotAttributes
    rows = s.execute(
        select(S.id, S.natural_positions, S.accomplished_positions, S.positions, S.field_status,
               *[getattr(A, k) for k in ATTR_KEYS])
        .join(A, A.snapshot_id == S.id)
        .where(S.run_id == run_id)
        .order_by(S.id)
    ).all()
    s.execute(delete(PlayerEvaluation).where(PlayerEvaluation.run_id == run_id, PlayerEvaluation.model_id == model.id))
    s.execute(delete(EvaluationBaseline).where(EvaluationBaseline.run_id == run_id, EvaluationBaseline.model_id == model.id))
    if not rows:
        return {"run_id": run_id, "model_id": model.id, "players": 0, "seconds": 0.0}

    raw = np.array([[np.nan if v is None or v < 1 else v for v in r[5:]] for r in rows], dtype=float)
    res = evaluate_batch(c, raw)
    pkeys, rkeys = c.position_keys, c.role_keys
    pidx = {k: i for i, k in enumerate(pkeys)}
    role_positions = {r.key: set(r.positions) for r in spec.roles}
    now = datetime.now()

    def r1(x: float) -> float | None:
        return None if np.isnan(x) else round(float(x), 1)

    out_rows = []
    eligible_by_row: list[list[str]] = []
    for i, r in enumerate(rows):
        elig = eligible_positions(r[1], r[2], r[3])
        eligible_by_row.append(elig)
        pscores = {k: r1(res.position_scores[i, j]) for j, k in enumerate(pkeys)}
        rscores = {k: r1(res.role_scores[i, j]) for j, k in enumerate(rkeys)}
        groups = {}
        for g, (_label, members) in RANKING_GROUPS.items():
            vals = [pscores[p] for p in members if p in elig and pscores[p] is not None]
            groups[g] = max(vals) if vals else None
        cand = [(pscores[p], p) for p in (elig or pkeys) if pscores[p] is not None]
        best_score, best_pos = max(cand) if cand else (None, None)
        # Melhor função: só entre as funções de posições em que é competente (se houver).
        rcand = [(v, k) for k, v in rscores.items() if v is not None and (not elig or role_positions[k] & set(elig))]
        best_r_score, best_role = max(rcand) if rcand else (None, None)
        status = (r[4] or {}).get("attributes")
        best_cov = float(res.position_coverage[i, pidx[best_pos]]) if best_pos else 0.0
        out_rows.append({
            "snapshot_id": r[0], "run_id": run_id, "model_id": model.id, "spec_hash": c.spec_hash,
            "position_scores": pscores, "role_scores": rscores, "group_scores": groups, "eligible_positions": elig,
            "best_position": best_pos, "best_position_score": best_score,
            "best_role": best_role, "best_role_score": best_r_score,
            "min_coverage": round(float(res.position_coverage[i].min()), 3),
            "confidence": confidence(best_cov, status) if best_pos else "low",
            "computed_at": now,
        })
    conn = s.connection()
    for k in range(0, len(out_rows), 5000):
        conn.execute(insert(PlayerEvaluation.__table__), out_rows[k:k + 5000])

    # Médias por posição: só jogadores competentes nessa posição.
    base_rows = []
    attr_n = raw
    for pos in pkeys:
        mask = np.array([pos in e for e in eligible_by_row])
        n = int(mask.sum())
        if n == 0:
            mm, am, sm = {}, {}, None
        else:
            with np.errstate(invalid="ignore"), _quiet():
                mvals = np.nanmean(res.metric_scores[mask], axis=0)
                avals = np.nanmean(attr_n[mask], axis=0)
                sm = r1(np.nanmean(res.position_scores[mask, pidx[pos]]))
            mm = {k: r1(v) for k, v in zip(c.metric_keys, mvals, strict=True)}
            am = {k: (None if np.isnan(v) else round(float(v), 2)) for k, v in zip(ATTR_KEYS, avals, strict=True)}
        base_rows.append({"run_id": run_id, "model_id": model.id, "spec_hash": c.spec_hash, "position": pos,
                          "players": n, "score_mean": sm, "metric_means": mm, "attribute_means": am})
    conn.execute(insert(EvaluationBaseline.__table__), base_rows)
    return {"run_id": run_id, "model_id": model.id, "spec_hash": c.spec_hash, "players": len(out_rows),
            "seconds": round((datetime.now() - started).total_seconds(), 2)}


class _quiet:
    def __enter__(self):
        import warnings  # noqa: PLC0415

        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)


def evaluation_state(s: Session, run_id: int, model: EvaluationModel) -> str:
    """'fresh' (avaliado com os pesos atuais), 'stale' (pesos mudaram) ou 'missing'."""
    hashes = set(s.scalars(select(PlayerEvaluation.spec_hash).where(
        PlayerEvaluation.run_id == run_id, PlayerEvaluation.model_id == model.id).distinct()))
    if not hashes:
        return "missing"
    return "fresh" if hashes == {model.spec_hash} else "stale"


# ------------------------------------------------------------------ rankings

def rankings(
    s: Session,
    run: ImportRun,
    model: EvaluationModel,
    group: str,
    *,
    sort: str = "score",
    order: str = "desc",
    eligible_only: bool = True,
    min_age: int | None = None,
    max_age: int | None = None,
    club: str | None = None,
    nationality: str | None = None,
    confidence_min: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if group not in RANKING_GROUPS:
        raise ValueError(f"grupo desconhecido: {group}")
    E, S = PlayerEvaluation, PlayerSnapshot
    label, members = RANKING_GROUPS[group]
    group_score = func.json_extract(E.group_scores, f"$.{group}")
    if eligible_only:
        score = group_score
    else:  # melhor das posições do grupo, sem exigir competência
        parts = [func.coalesce(func.json_extract(E.position_scores, f"$.{p}"), -1) for p in members]
        score = func.max(*parts) if len(parts) > 1 else parts[0]
    q = (
        select(S, E, Player.nationalities, score.label("score"))
        .join(E, E.snapshot_id == S.id)
        .join(Player, Player.id == S.player_id)
        .where(S.run_id == run.id, E.model_id == model.id)
    )
    if eligible_only:
        q = q.where(group_score.is_not(None))
    if min_age is not None:
        q = q.where(S.age >= min_age)
    if max_age is not None:
        q = q.where(S.age <= max_age)
    if club:
        q = q.where(S.club_name.ilike(f"%{club}%"))
    if nationality:
        q = q.where(func.json(Player.nationalities).ilike(f"%{nationality}%"))
    if confidence_min == "medium":
        q = q.where(E.confidence.in_(["medium", "high"]))
    elif confidence_min == "high":
        q = q.where(E.confidence == "high")

    if sort == "score":
        col = score
    elif sort.startswith("role:"):
        col = func.json_extract(E.role_scores, f"$.{sort[5:]}")
    elif sort.startswith("position:"):
        col = func.json_extract(E.position_scores, f"$.{sort[9:]}")
    else:
        cols = {"ca": S.ca, "pa": S.pa, "age": S.age, "market_value": S.market_value, "name": S.name,
                "ca_delta": S.ca_delta, "best_role": E.best_role_score}
        if sort not in cols:
            raise ValueError(f"ordenação inválida: {sort}")
        col = cols[sort]
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    q = q.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last(), S.id)
    items = []
    for i, (snap, ev, nats, sc) in enumerate(s.execute(q.limit(limit).offset(offset))):
        pos_in_group = {p: ev.position_scores.get(p) for p in members}
        group_roles = {k: v for k, v in ev.role_scores.items() if v is not None}
        items.append({
            "rank": offset + i + 1,
            "player_id": snap.player_id,
            "name": snap.name,
            "age": snap.age,
            "club": snap.club_name,
            "nationalities": nats or [],
            "positions": list(snap.natural_positions or []) + list(snap.accomplished_positions or []),
            "natural_positions": list(snap.natural_positions or []),
            "ca": snap.ca,
            "pa": snap.pa,
            "ca_delta": snap.ca_delta,
            "market_value": snap.market_value,
            "score": None if sc is None or sc < 0 else sc,
            "group_positions": pos_in_group,
            "best_position": ev.best_position,
            "best_role": ev.best_role,
            "best_role_score": ev.best_role_score,
            "role_scores": group_roles,
            "confidence": ev.confidence,
            "incomplete": ev.min_coverage < 1,
        })
    return {"group": group, "label": label, "positions": list(members), "total": total, "items": items,
            "state": evaluation_state(s, run.id, model)}


# ---------------------------------------------------------------- perfil

def player_detail(s: Session, snap: PlayerSnapshot, model: EvaluationModel, focus: str | None = None) -> dict[str, Any]:
    """Avaliação completa de um snapshot: posições, funções, métricas, médias e comparação."""
    spec = model_spec(model)
    arow = s.get(SnapshotAttributes, snap.id)
    attrs = {k: getattr(arow, k) for k in ATTRIBUTES} if arow else {}
    status = (snap.field_status or {}).get("attributes")
    live = evaluate_player(spec, attrs, status)
    elig = eligible_positions(snap.natural_positions, snap.accomplished_positions, snap.positions)
    pos_scores = {p["key"]: p["score"] for p in live["positions"]}
    if focus not in POSITIONS:
        cand = [(pos_scores[p], p) for p in elig if pos_scores.get(p) is not None]
        focus = max(cand)[1] if cand else (live["positions"][0]["key"] if live["positions"] else None)

    baselines = {
        b.position: b
        for b in s.scalars(select(EvaluationBaseline).where(
            EvaluationBaseline.run_id == snap.run_id, EvaluationBaseline.model_id == model.id))
    }
    base = baselines.get(focus)
    metric_by_key = {m["key"]: m for m in live["metrics"]}
    pos_spec = spec.position(focus) if focus else None
    total_w = sum(w.weight for w in pos_spec.metrics) if pos_spec else 1

    comparison = []
    if pos_spec:
        for w in sorted(pos_spec.metrics, key=lambda x: -x.weight):
            m = metric_by_key[w.metric]
            avg = (base.metric_means or {}).get(w.metric) if base else None
            comparison.append({
                "metric": w.metric, "name": m["name"], "category": m["category"],
                "weight_share": round(w.weight / total_w, 3),
                "score": m["score"], "position_mean": avg,
                "diff": None if m["score"] is None or avg is None else round(m["score"] - avg, 1),
                "coverage": m["coverage"],
            })
    rated = [x for x in comparison if x["diff"] is not None]
    strengths = sorted((x for x in rated if x["diff"] >= 5 and (x["score"] or 0) >= 50),
                       key=lambda x: -(x["diff"] * (0.5 + x["weight_share"] * 5)))[:4]
    weaknesses = sorted((x for x in rated if x["diff"] <= -5),
                        key=lambda x: x["diff"] * (0.5 + x["weight_share"] * 5))[:4]

    # Atributos acima/abaixo da média dos jogadores da posição (para o radar).
    attr_vs = []
    if base and base.attribute_means:
        imp: dict[str, float] = {}
        for w in pos_spec.metrics:
            mm = spec.metric(w.metric)
            mt = sum(a.weight for a in mm.attributes)
            for a in mm.attributes:
                imp[a.attribute] = imp.get(a.attribute, 0) + w.weight / total_w * a.weight / mt
        for k in sorted(imp, key=imp.get, reverse=True)[:8]:
            attr_vs.append({"attribute": k, "label": ATTRIBUTES[k].label, "value": attrs.get(k),
                            "position_mean": base.attribute_means.get(k)})

    stored = s.scalar(select(PlayerEvaluation).where(PlayerEvaluation.snapshot_id == snap.id,
                                                     PlayerEvaluation.model_id == model.id))
    ranking = None
    if stored and focus and stored.spec_hash == model.spec_hash and focus in elig:
        E = PlayerEvaluation
        col = func.json_extract(E.position_scores, f"$.{focus}")
        fam = func.instr(func.json(E.eligible_positions), f'"{focus}"') > 0
        my = pos_scores.get(focus)
        if my is not None:
            n = s.scalar(select(func.count()).where(E.run_id == snap.run_id, E.model_id == model.id, fam, col.is_not(None)))
            above = s.scalar(select(func.count()).where(E.run_id == snap.run_id, E.model_id == model.id, fam, col > my))
            neigh_q = (
                select(PlayerSnapshot.player_id, PlayerSnapshot.name, PlayerSnapshot.age, PlayerSnapshot.club_name,
                       PlayerSnapshot.ca, PlayerSnapshot.pa, col.label("score"))
                .join(E, E.snapshot_id == PlayerSnapshot.id)
                .where(E.run_id == snap.run_id, E.model_id == model.id, fam, col.is_not(None))
            )
            better = s.execute(neigh_q.where(col >= my, PlayerSnapshot.id != snap.id).order_by(col.asc()).limit(3)).all()
            worse = s.execute(neigh_q.where(col <= my, PlayerSnapshot.id != snap.id).order_by(col.desc()).limit(3)).all()
            top = s.execute(neigh_q.order_by(col.desc()).limit(5)).all()

            def pl(r):
                return {"player_id": r.player_id, "name": r.name, "age": r.age, "club": r.club_name,
                        "ca": r.ca, "pa": r.pa, "score": r.score}

            ranking = {
                "position": focus, "rank": above + 1, "of": n,
                "percentile": round(100 * (n - above - 1) / max(n - 1, 1), 1) if n > 1 else None,
                "above": [pl(r) for r in reversed(better)], "below": [pl(r) for r in worse], "top": [pl(r) for r in top],
            }

    return {
        "model": {"id": model.id, "name": model.name, "spec_hash": model.spec_hash, "builtin": model.builtin},
        "data_status": status,
        "eligible_positions": elig,
        "focus": focus,
        "positions": [{**p, "pt": POSITIONS[p["key"]][0], "eligible": p["key"] in elig,
                       "familiarity": (snap.positions or {}).get(p["key"]),
                       "position_mean": baselines[p["key"]].score_mean if p["key"] in baselines else None}
                      for p in live["positions"]],
        "roles": [{**r, "positions": spec.role(r["key"]).positions,
                   "availability": spec.role(r["key"]).availability,
                   "eligible": any(x in elig for x in spec.role(r["key"]).positions)} for r in live["roles"]],
        "metrics": live["metrics"],
        "comparison": comparison,
        "position_mean_score": base.score_mean if base else None,
        "position_players": base.players if base else 0,
        "attributes_vs_position": attr_vs,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "ranking": ranking,
        "stored_state": None if stored is None else ("fresh" if stored.spec_hash == model.spec_hash else "stale"),
    }


def mark_active(s: Session, model: EvaluationModel) -> None:
    s.execute(update(EvaluationModel).values(active=False))
    model.active = True
