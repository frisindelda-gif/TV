"""Persistência de um ``ImportBundle`` normalizado.

Um único caminho de escrita para os dois conectores. Inserções em lote (SQLAlchemy Core)
porque um save grande tem 60k–600k jogadores × 60 atributos.

Garantias:
- Idempotência: o mesmo ficheiro (sha256) na mesma carreira não cria uma segunda importação.
- Identidade: jogador = (carreira, Unique ID). Se o FM reutilizar um Unique ID de uma
  pessoa apagada (acontece com regens), a data de nascimento diferente gera nova identidade.
- Nada é corrigido: problemas de validação ficam em ``validation_issues``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime

import threading

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.orm import Session

from fm27si.catalog import ATTRIBUTES
from fm27si.connectors.base import season_label
from fm27si.orm import (
    Career,
    Club,
    ImportRun,
    Player,
    PlayerSnapshot,
    SeasonStatLine,
    SnapshotAttributes,
    SnapshotMetrics,
    ValidationIssue,
)
from fm27si.metrics import compute as compute_metrics
from fm27si.metrics import percentiles as compute_percentiles
from fm27si.metrics import position_group
from fm27si.schemas import ImportBundle, NormalizedPlayer
from fm27si.validation import quality_of, validate_player

BATCH = 2000
_IMPORT_LOCK = threading.Lock()


@dataclass
class ImportResult:
    run: ImportRun
    duplicate: bool = False
    created_players: int = 0
    updated_players: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


def career_key_for(bundle: ImportBundle) -> str:
    """Chave heurística. O utilizador pode (e deve) fixar ``career_key`` explicitamente."""
    s, c = bundle.source, bundle.career
    anchor = c.save_name or c.managed_club or "?"
    return f"{s.game or '?'}|{c.manager_name or '?'}|{anchor}"


def _chunks(seq: list, n: int = BATCH) -> Iterator[list]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _birth_token(p: NormalizedPlayer) -> str | None:
    if p.birth_date:
        return p.birth_date.isoformat()
    if p.birth_year:
        return str(p.birth_year)
    return None


def _same_birth(existing_date, existing_year, p: NormalizedPlayer) -> bool:
    if existing_date and p.birth_date:
        return existing_date == p.birth_date
    ey = existing_year or (existing_date.year if existing_date else None)
    py = p.birth_year or (p.birth_date.year if p.birth_date else None)
    return ey is None or py is None or ey == py


def import_bundle(session: Session, bundle: ImportBundle, *, career_key: str | None = None) -> ImportResult:
    with _IMPORT_LOCK:
        try:
            return _import_bundle(session, bundle, career_key=career_key)
        except Exception:
            session.rollback()
            raise


def _import_bundle(session: Session, bundle: ImportBundle, *, career_key: str | None) -> ImportResult:
    now = datetime.now()
    src = bundle.source
    key = career_key or career_key_for(bundle)
    warnings = list(bundle.warnings)

    career = session.scalar(select(Career).where(Career.key == key))
    if career is None:
        career = Career(
            key=key,
            label=bundle.career.save_name or f"{bundle.career.manager_name or '?'} — {bundle.career.managed_club or '?'}",
            game=src.game,
            manager_name=bundle.career.manager_name,
            save_name=bundle.career.save_name,
            created_at=now,
        )
        session.add(career)
        session.flush()

    if src.source_sha256:
        existing = session.scalar(
            select(ImportRun).where(ImportRun.career_id == career.id, ImportRun.source_sha256 == src.source_sha256)
        )
        if existing is not None:
            return ImportResult(run=existing, duplicate=True, warnings=["Fonte já importada (mesmo sha256)."])

    run = ImportRun(
        career_id=career.id,
        connector=src.connector,
        tool=src.tool,
        tool_version=src.tool_version,
        source_path=src.source_path,
        source_sha256=src.source_sha256,
        source_mtime=src.source_mtime,
        read_at=src.read_at,
        imported_at=now,
        game=src.game,
        game_version=src.game_version,
        game_version_supported=src.game_version_supported,
        game_date=src.game_date,
        game_date_status=src.game_date_status,
        season_label=season_label(src.game_date),
        managed_club=bundle.career.managed_club,
        currency=src.currency,
        synthetic=src.synthetic,
        source_player_count=len(bundle.players),
        unavailable_fields=list(bundle.unavailable_fields),
    )
    session.add(run)
    session.flush()

    # ---------------------------------------------------------------- clubes
    clubs_by_uid, clubs_by_name = _upsert_clubs(session, career.id, run.id, bundle)
    src_uid_to_club: dict[int, int] = {}
    for c in bundle.clubs:
        if c.source_uid is not None:
            cid = clubs_by_uid.get(c.unique_id) if c.unique_id is not None else None
            cid = cid or clubs_by_name.get(c.name or "")
            if cid:
                src_uid_to_club[c.source_uid] = cid

    # ------------------------------------------------------------- jogadores
    existing = {
        row.identity_key: row
        for row in session.execute(
            select(Player.id, Player.identity_key, Player.birth_date, Player.birth_year).where(Player.career_id == career.id)
        )
    }
    prev_run_id = session.scalar(
        select(ImportRun.id).where(ImportRun.career_id == career.id, ImportRun.id != run.id).order_by(ImportRun.id.desc())
    )

    seen_keys: set[str] = set()
    plan: list[tuple[NormalizedPlayer, str, int | None]] = []  # (player, identity, existing id)
    skipped = 0
    for p in bundle.players:
        ident = f"uid:{p.unique_id}" if p.unique_id is not None else f"src:{src.connector}:{p.source_uid}:{_birth_token(p)}"
        row = existing.get(ident)
        if row is not None and not _same_birth(row.birth_date, row.birth_year, p):
            warnings.append(f"Unique ID {p.unique_id} reutilizado com outra data de nascimento ({p.name}): nova identidade.")
            ident = f"{ident}:{_birth_token(p)}"
            row = existing.get(ident)
        if ident in seen_keys:
            warnings.append(f"Identidade duplicada na mesma fonte ({ident}, {p.name}): segundo registo ignorado.")
            skipped += 1
            continue
        seen_keys.add(ident)
        plan.append((p, ident, row.id if row is not None else None))

    if prev_run_id is not None and existing:
        overlap = sum(1 for _, _, pid in plan if pid is not None)
        if plan and overlap / len(plan) < 0.5:
            warnings.append(
                f"Só {overlap}/{len(plan)} jogadores já existiam nesta carreira: confirme que é a mesma carreira."
            )

    new_rows = [
        {
            "career_id": career.id,
            "identity_key": ident,
            "unique_id": p.unique_id,
            "name": p.name,
            "birth_date": p.birth_date,
            "birth_year": p.birth_year or (p.birth_date.year if p.birth_date else None),
            "gender": p.gender,
            "nationalities": p.nationalities,
            "first_seen_run_id": run.id,
            "last_seen_run_id": run.id,
        }
        for p, ident, pid in plan
        if pid is None
    ]
    new_ids = _assign_ids(session, Player, new_rows)
    _bulk(session, Player, new_rows)
    it_new = iter(new_ids)
    player_ids = [pid if pid is not None else next(it_new) for _, _, pid in plan]

    existing_ids = [pid for _, _, pid in plan if pid is not None]
    for chunk in _chunks(existing_ids, 900):
        session.execute(update(Player).where(Player.id.in_(chunk)).values(last_seen_run_id=run.id))

    prev = _previous_snapshots(session, run, existing_ids)
    first_run = prev_run_id is None

    # ------------------------------------------------------------- snapshots
    snap_rows = []
    all_issues = []
    groups: list[str | None] = []
    for (p, _ident, existing_pid), player_id in zip(plan, player_ids, strict=True):
        group = position_group(p.natural_positions, p.accomplished_positions)
        groups.append(group)
        before = prev.get(player_id)
        issues = validate_player(p)
        all_issues.append(issues)
        club_id = None
        if p.club is not None:
            if p.club.source_uid is not None:
                club_id = src_uid_to_club.get(p.club.source_uid)
            if club_id is None and p.club.name:
                club_id = clubs_by_name.get(p.club.name)
        c = p.contract
        snap_rows.append(
            {
                "player_id": player_id,
                "run_id": run.id,
                "source_uid": p.source_uid,
                "name": p.name,
                "age": p.age,
                "ca": p.ca,
                "pa": p.pa,
                "pa_range_code": p.pa_range_code,
                "height_cm": p.height_cm,
                "foot_left": p.foot_left,
                "foot_right": p.foot_right,
                "preferred_foot": p.preferred_foot,
                "reputation_home": p.reputation_home,
                "reputation_current": p.reputation_current,
                "reputation_world": p.reputation_world,
                "club_id": club_id,
                "club_name": p.club.name if p.club else None,
                "division": p.club.division if p.club else None,
                "market_value": p.market_value,
                "wage_weekly": c.wage_weekly if c else None,
                "contract_start": c.start if c else None,
                "contract_expires": c.expires if c else None,
                "contract": c.model_dump(mode="json") if c else None,
                "positions": p.positions,
                "natural_positions": p.natural_positions,
                "accomplished_positions": p.accomplished_positions,
                "roles": p.roles,
                "traits": p.traits,
                "field_status": p.field_status,
                "extra": _jsonable(p.extra),
                "quality": quality_of(issues),
                "position_group": group,
                "prev_snapshot_id": before[0] if before else None,
                "ca_delta": p.ca - before[1] if before and p.ca is not None and before[1] is not None else None,
                "pa_delta": p.pa - before[2] if before and p.pa is not None and before[2] is not None else None,
                # Na primeira importação da carreira todos seriam "novos": fica indefinido.
                "is_new": None if first_run else existing_pid is None,
            }
        )
    snap_ids = _assign_ids(session, PlayerSnapshot, snap_rows)
    _bulk(session, PlayerSnapshot, snap_rows)

    def attr_rows() -> Iterable[dict]:
        for (p, _, _), sid in zip(plan, snap_ids, strict=True):
            row = dict.fromkeys(ATTRIBUTES)  # NULL = não fornecido pela fonte
            row.update({k: v for k, v in p.attributes.items() if k in ATTRIBUTES and isinstance(v, int)})
            row["snapshot_id"] = sid
            yield row

    _bulk(session, SnapshotAttributes, attr_rows())

    def issue_rows() -> Iterable[dict]:
        for issues, sid in zip(all_issues, snap_ids, strict=True):
            for i in issues:
                yield {"snapshot_id": sid, "severity": i.severity, "field": i.field, "code": i.code,
                       "message": i.message, "value": _jsonable(i.value)}

    _bulk(session, ValidationIssue, issue_rows())

    def stat_rows() -> Iterable[dict]:
        for (p, _, _), sid in zip(plan, snap_ids, strict=True):
            for s in p.season_stats:
                d = s.model_dump()
                d["snapshot_id"] = sid
                yield d

    _bulk(session, SeasonStatLine, stat_rows())

    # --------------------------------------------- métricas (derivadas)
    metric_rows: list[tuple[int, str | None, float, dict]] = []
    for (p, _, _), sid, group in zip(plan, snap_ids, groups, strict=True):
        if p.season_stats:
            vals, minutes = compute_metrics(p.season_stats, group)
            if vals:
                metric_rows.append((sid, group, minutes, vals))
    pcts = compute_percentiles(metric_rows)
    _bulk(
        session,
        SnapshotMetrics,
        (
            {
                "snapshot_id": sid,
                "position_group": group,
                "minutes": minutes,
                "appearances": vals.get("appearances") or 0,
                "values": vals,
                "percentiles": pcts.get(sid, {}),
            }
            for sid, group, minutes, vals in metric_rows
        ),
    )

    # ------------------------------------- avaliação por posição/função (modelo ativo)
    from fm27si.evaluation.service import evaluate_run  # noqa: PLC0415

    try:
        with session.begin_nested():
            evaluate_run(session, run.id)
    except Exception as e:  # a avaliação nunca deve impedir a importação dos dados
        warnings.append(f"Avaliação por posição não calculada: {type(e).__name__}: {e}")

    # ------------------------- Statistical Scouting: campos, disponibilidade, descoberta
    from fm27si.stats.service import process_run  # noqa: PLC0415

    try:
        with session.begin_nested():
            process_run(session, run)
    except Exception as e:  # nunca impede a importação dos dados
        warnings.append(f"Análise estatística não calculada: {type(e).__name__}: {e}")

    run.player_count = len(plan)
    run.error_count = sum(1 for iss in all_issues if any(i.severity == "error" for i in iss))
    run.warning_count = sum(1 for iss in all_issues if quality_of(iss) == "warning")
    run.warnings = warnings[:500]
    session.commit()
    return ImportResult(
        run=run,
        created_players=len(new_rows),
        updated_players=len(existing_ids),
        skipped=skipped,
        warnings=warnings,
    )


def _previous_snapshots(session: Session, run: ImportRun, player_ids: list[int]) -> dict[int, tuple[int, int | None, int | None]]:
    """Snapshot anterior de cada jogador: o de data de jogo mais recente que não seja posterior a esta."""
    S, R = PlayerSnapshot, ImportRun
    out: dict[int, tuple[int, int | None, int | None]] = {}
    for chunk in _chunks(player_ids, 900):
        rn = func.row_number().over(partition_by=S.player_id, order_by=(R.game_date.desc(), S.id.desc())).label("rn")
        inner = select(S.id, S.player_id, S.ca, S.pa, rn).join(R, R.id == S.run_id).where(
            S.player_id.in_(chunk), S.run_id != run.id
        )
        if run.game_date is not None:
            inner = inner.where(or_(R.game_date.is_(None), R.game_date <= run.game_date))
        sq = inner.subquery()
        for sid, pid, ca, pa in session.execute(select(sq.c.id, sq.c.player_id, sq.c.ca, sq.c.pa).where(sq.c.rn == 1)):
            out[pid] = (sid, ca, pa)
    return out


def _upsert_clubs(session: Session, career_id: int, run_id: int, bundle: ImportBundle):
    by_uid: dict[int, int] = {}
    by_name: dict[str, int] = {}
    for c in session.scalars(select(Club).where(Club.career_id == career_id)):
        if c.unique_id is not None:
            by_uid[c.unique_id] = c.id
        by_name.setdefault(c.name, c.id)

    records = list(bundle.clubs)
    known_names = {c.name for c in records if c.name}
    # Clubes só referenciados por nome (Live Connector).
    for p in bundle.players:
        if p.club and p.club.name and p.club.name not in known_names:
            known_names.add(p.club.name)
            records.append(p.club)  # type: ignore[arg-type]

    for c in records:
        if not c.name:
            continue
        cid = by_uid.get(c.unique_id) if c.unique_id is not None else None
        if cid is None:
            cid = by_name.get(c.name)
        values = {
            "name": c.name,
            "short_name": c.short_name,
            "reputation": c.reputation,
            "division": getattr(c, "division", None),
            "nation_id": getattr(c, "nation_id", None),
            "last_seen_run_id": run_id,
        }
        values = {k: v for k, v in values.items() if v is not None}
        if cid is None:
            ident = f"uid:{c.unique_id}" if c.unique_id is not None else f"name:{c.name}"
            obj = Club(career_id=career_id, identity_key=ident, unique_id=c.unique_id, **values)
            session.add(obj)
            session.flush()
            cid = obj.id
        else:
            if c.unique_id is not None:
                values["unique_id"] = c.unique_id
            session.execute(update(Club).where(Club.id == cid).values(**values))
        if c.unique_id is not None:
            by_uid[c.unique_id] = cid
        by_name.setdefault(c.name, cid)
    return by_uid, by_name


def _assign_ids(session: Session, model, rows: list[dict]) -> list[int]:
    """Ids explícitos: evita INSERT ... RETURNING linha a linha (10x mais lento em SQLite).

    Seguro porque as importações são serializadas por ``_IMPORT_LOCK`` e a app é local e
    mono-utilizador; um escritor concorrente externo faria falhar a transação (UNIQUE),
    nunca misturar dados.
    """
    start = (session.scalar(select(func.max(model.id))) or 0) + 1
    ids = list(range(start, start + len(rows)))
    for r, i in zip(rows, ids, strict=True):
        r["id"] = i
    return ids


def _bulk(session: Session, model, rows: Iterable[dict]) -> None:
    """executemany via Core (sem a camada de unidade-de-trabalho do ORM)."""
    conn = session.connection()
    stmt = insert(model.__table__)
    buf: list[dict] = []
    for r in rows:
        buf.append(r)
        if len(buf) >= BATCH * 10:
            conn.execute(stmt, buf)
            buf = []
    if buf:
        conn.execute(stmt, buf)


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)
