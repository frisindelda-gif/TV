"""Integridade dos dados ao longo de uma carreira de teste (sintética, 3 épocas)."""

from __future__ import annotations

import json

from sqlalchemy import func, select

from fm27si.connectors.base import sha256_of
from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector
from fm27si.importer import import_bundle
from fm27si.integrity import integrity_report
from fm27si.orm import ImportRun, Player, PlayerSnapshot, SnapshotAttributes, ValidationIssue

conn = FMSuperScoutLiveConnector()


def _import_all(session, paths):
    return [import_bundle(session, conn.load(p)) for p in paths]


def test_import_counts_match_source(session, career_dumps):
    for path, res in zip(career_dumps, _import_all(session, career_dumps), strict=True):
        n_src = len(json.loads(path.read_text(encoding="utf-8"))["players"])
        assert res.run.player_count == n_src
        rep = integrity_report(session, res.run.id)
        assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
        assert rep["coverage"]["ca"] == 1.0 and rep["coverage"]["pa"] == 1.0
        assert rep["coverage"]["personality_complete"] == 1.0
        assert rep["quality"] == {"ok": n_src}


def test_reimport_same_file_is_idempotent(session, career_dumps):
    first = import_bundle(session, conn.load(career_dumps[0]))
    again = import_bundle(session, conn.load(career_dumps[0]))
    assert again.duplicate and again.run.id == first.run.id
    assert session.scalar(select(func.count(ImportRun.id))) == 1
    assert session.scalar(select(func.count(PlayerSnapshot.id))) == first.run.player_count


def test_history_regens_and_retirements(session, career_dumps):
    r1, r2, r3 = _import_all(session, career_dumps)
    assert r1.run.career_id == r2.run.career_id == r3.run.career_id  # mesma carreira
    assert r2.created_players > 0 and r2.updated_players > 0  # regens novos + existentes

    ids1 = {p["id"] for p in json.loads(career_dumps[0].read_text(encoding="utf-8"))["players"]}
    ids3 = {p["id"] for p in json.loads(career_dumps[2].read_text(encoding="utf-8"))["players"]}
    assert ids1 - ids3, "a carreira de teste deve ter retirados"
    total = session.scalar(select(func.count(Player.id)))
    assert total == len(ids1 | {p["id"] for p in json.loads(career_dumps[1].read_text(encoding="utf-8"))["players"]} | ids3)

    # Um jogador presente nas 3 épocas tem 3 snapshots, por ordem, ligados a runs diferentes.
    uid = next(iter(ids1 & ids3))
    pl = session.scalar(select(Player).where(Player.unique_id == uid))
    snaps = pl.snapshots
    assert [s.run_id for s in snaps] == [r1.run.id, r2.run.id, r3.run.id]
    src_ca = [next(p["ca"] for p in json.loads(f.read_text(encoding="utf-8"))["players"] if p["id"] == uid) for f in career_dumps]
    assert [s.ca for s in snaps] == src_ca  # valores preservados exatamente
    assert pl.first_seen_run_id == r1.run.id and pl.last_seen_run_id == r3.run.id


def test_values_preserved_exactly(session, small_dump_path, small_dump):
    res = import_bundle(session, conn.load(small_dump_path))
    src = small_dump["players"][0]
    snap = session.scalar(select(PlayerSnapshot).where(PlayerSnapshot.run_id == res.run.id, PlayerSnapshot.source_uid == src["id"]))
    attrs = session.get(SnapshotAttributes, snap.id)
    assert attrs.pace == src["attrs"]["Pace"] and attrs.dirtiness == src["attrs"]["Dirtiness"]
    assert attrs.ambition == src["ambition"]
    assert (snap.ca, snap.pa, snap.wage_weekly, snap.market_value) == (src["ca"], src["pa"], src["wage"], src["value"])
    run = session.get(ImportRun, res.run.id)
    assert run.synthetic and run.source_sha256 == sha256_of(small_dump_path)
    assert run.game_date.isoformat() == "2026-08-20" and run.season_label == "2026/27"


def test_bad_record_is_kept_but_flagged(session, small_dump_path):
    res = import_bundle(session, conn.load(small_dump_path))
    assert res.run.player_count == 3 and res.run.error_count == 1
    bad = session.scalar(select(PlayerSnapshot).where(PlayerSnapshot.source_uid == 91000003))
    assert bad.quality == "error"
    assert (bad.ca, bad.pa) == (0, 250)  # nada é "corrigido"
    codes = {(i.field, i.code) for i in session.scalars(select(ValidationIssue).where(ValidationIssue.snapshot_id == bad.id))}
    assert {("ca", "out_of_range"), ("pa", "out_of_range"), ("attributes", "incomplete"), ("attributes", "constant_block")} <= codes
    attrs = session.get(SnapshotAttributes, bad.id)
    assert attrs.pace is None  # em falta na fonte = NULL, não preenchido
    rep = integrity_report(session, res.run.id)
    assert not next(c for c in rep["checks"] if c["name"] == "ca_in_range_1_200")["ok"]
    assert not rep["ok"]


def test_duplicate_unique_id_in_source_is_skipped(session, small_dump):
    small_dump["players"].append(dict(small_dump["players"][0]))
    b = conn.from_dict(small_dump)
    res = import_bundle(session, b)
    assert res.skipped == 1 and res.run.player_count == 3
    assert any("duplicada" in w for w in res.warnings)
    assert not integrity_report(session, res.run.id)["checks"][1]["ok"]  # all_source_players_imported


def test_unique_id_reuse_with_other_birth_creates_new_identity(session, small_dump):
    import_bundle(session, conn.from_dict(small_dump), career_key="k")
    reused = json.loads(json.dumps(small_dump))
    reused["meta"]["gameDate"] = "2030-08-20"
    reused["players"][0].update(name="Regen Novo", birthYear=2014, birthDoy=10)
    res = import_bundle(session, conn.from_dict(reused), career_key="k")
    assert any("reutilizado" in w for w in res.warnings)
    assert session.scalar(select(func.count(Player.id)).where(Player.unique_id == 91000001)) == 2


def test_explicit_career_key_separates_careers(session, small_dump_path):
    a = import_bundle(session, conn.load(small_dump_path), career_key="carreira-A")
    b = import_bundle(session, conn.load(small_dump_path), career_key="carreira-B")
    assert a.run.career_id != b.run.career_id and not b.duplicate
