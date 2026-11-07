"""Relatório de integridade de uma importação (verificações SQL sobre o que ficou gravado)."""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from fm27si.catalog import PERSONALITY_KEYS, PLAYER_ATTRIBUTE_KEYS
from fm27si.orm import ImportRun, Player, PlayerSnapshot, SnapshotAttributes, ValidationIssue


def integrity_report(s: Session, run_id: int) -> dict:
    run = s.get(ImportRun, run_id)
    S, A = PlayerSnapshot, SnapshotAttributes
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: object = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    n_snap = s.scalar(select(func.count()).where(S.run_id == run_id)) or 0
    check("snapshots_match_run_count", n_snap == run.player_count, {"snapshots": n_snap, "run.player_count": run.player_count})
    check(
        "all_source_players_imported",
        run.player_count == run.source_player_count,
        {"imported": run.player_count, "in_source": run.source_player_count},
    )

    dup = s.scalar(
        select(func.count()).select_from(
            select(S.player_id).where(S.run_id == run_id).group_by(S.player_id).having(func.count() > 1).subquery()
        )
    )
    check("no_duplicate_player_in_run", dup == 0, dup)

    foreign = s.scalar(
        select(func.count()).select_from(S).join(Player, Player.id == S.player_id)
        .where(S.run_id == run_id, Player.career_id != run.career_id)
    )
    check("snapshots_belong_to_run_career", foreign == 0, foreign)

    dup_uid = s.scalar(
        select(func.count()).select_from(
            select(Player.unique_id).join(S, S.player_id == Player.id)
            .where(S.run_id == run_id, Player.unique_id.is_not(None))
            .group_by(Player.unique_id).having(func.count() > 1).subquery()
        )
    )
    check("unique_id_unique_in_run", dup_uid == 0, dup_uid)

    bad_ca = s.scalar(select(func.count()).where(S.run_id == run_id, S.ca.is_not(None), (S.ca < 1) | (S.ca > 200)))
    bad_pa = s.scalar(select(func.count()).where(S.run_id == run_id, S.pa.is_not(None), (S.pa < 1) | (S.pa > 200)))
    check("ca_in_range_1_200", bad_ca == 0, bad_ca)
    check("pa_in_range_1_200", bad_pa == 0, bad_pa)

    attr_base = select(func.count()).select_from(A).join(S, S.id == A.snapshot_id).where(S.run_id == run_id)
    n_attr_rows = s.scalar(attr_base) or 0
    check("one_attribute_row_per_snapshot", n_attr_rows == n_snap, {"attribute_rows": n_attr_rows, "snapshots": n_snap})

    cols = [getattr(A, k) for k in (*PLAYER_ATTRIBUTE_KEYS, *PERSONALITY_KEYS)]
    bad_attr = s.scalar(attr_base.where(or_(*[(c < 1) | (c > 25) for c in cols]))) or 0
    check("attributes_in_range", bad_attr == 0, bad_attr)

    full = s.scalar(attr_base.where(and_(*[getattr(A, k).is_not(None) for k in PLAYER_ATTRIBUTE_KEYS]))) or 0
    check(
        "attributes_complete_52",
        n_snap == 0 or full == n_snap,
        {"complete": full, "snapshots": n_snap, "share": round(full / n_snap, 4) if n_snap else None},
    )
    full_pers = s.scalar(attr_base.where(and_(*[getattr(A, k).is_not(None) for k in PERSONALITY_KEYS]))) or 0

    quality = dict(s.execute(select(S.quality, func.count()).where(S.run_id == run_id).group_by(S.quality)).all())
    issue_codes = dict(
        s.execute(
            select(ValidationIssue.field + ":" + ValidationIssue.code, func.count())
            .join(S, S.id == ValidationIssue.snapshot_id)
            .where(S.run_id == run_id)
            .group_by(ValidationIssue.field, ValidationIssue.code)
        ).all()
    )

    def share(cond) -> float | None:
        if not n_snap:
            return None
        return round((s.scalar(select(func.count()).where(S.run_id == run_id, cond)) or 0) / n_snap, 4)

    return {
        "run_id": run_id,
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "quality": quality,
        "issues_by_field_code": issue_codes,
        "coverage": {
            "ca": share(S.ca.is_not(None)),
            "pa": share(S.pa.is_not(None)),
            "pa_range_code": share(S.pa_range_code.is_not(None)),
            "market_value": share(S.market_value.is_not(None)),
            "wage_weekly": share(S.wage_weekly.is_not(None)),
            "contract_expires": share(S.contract_expires.is_not(None)),
            "club": share(S.club_name.is_not(None)),
            "personality_complete": round(full_pers / n_snap, 4) if n_snap else None,
        },
    }
