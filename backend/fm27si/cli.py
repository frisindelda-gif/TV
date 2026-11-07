"""Linha de comandos: servir a API, importar fontes, gerar a carreira de teste."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fm27si")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sv = sub.add_parser("serve", help="Arranca a API local em 127.0.0.1")
    sv.add_argument("--port", type=int, default=8727)

    s = sub.add_parser("import-save", help="Importa um ficheiro .fm (Save Reader / fmsave)")
    s.add_argument("path", type=Path)
    s.add_argument("--career-key")

    lv = sub.add_parser("import-live", help="Importa o dump.json do scanner FMSuperScout (Live Connector)")
    lv.add_argument("path", type=Path, nargs="?")
    lv.add_argument("--career-key")
    lv.add_argument("--scan", type=Path, metavar="SCANNER_EXE", help="Corre o scanner antes de importar (Windows)")

    g = sub.add_parser("make-test-career", help="Gera dumps SINTÉTICOS para testes")
    g.add_argument("out", type=Path)
    g.add_argument("--players", type=int, default=300)
    g.add_argument("--seasons", type=int, default=2)

    i = sub.add_parser("integrity", help="Relatório de integridade de uma importação")
    i.add_argument("run_id", type=int)

    args = ap.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn  # noqa: PLC0415

        from fm27si.api import create_app  # noqa: PLC0415

        uvicorn.run(create_app(), host="127.0.0.1", port=args.port)
        return 0

    if args.cmd == "make-test-career":
        from fm27si.testdata import write_test_career  # noqa: PLC0415

        for p in write_test_career(args.out, players=args.players, seasons=args.seasons):
            print(p)
        return 0

    from fm27si.db import Database  # noqa: PLC0415

    db = Database()
    with db.sessionmaker() as session:
        if args.cmd == "integrity":
            from fm27si.integrity import integrity_report  # noqa: PLC0415

            print(json.dumps(integrity_report(session, args.run_id), indent=2, ensure_ascii=False, default=str))
            return 0

        from fm27si.connectors.base import ConnectorError  # noqa: PLC0415
        from fm27si.importer import import_bundle  # noqa: PLC0415

        try:
            if args.cmd == "import-save":
                from fm27si.connectors.save_fmsave import FmsaveSaveConnector  # noqa: PLC0415

                bundle = FmsaveSaveConnector().load(args.path)
            else:
                from fm27si.config import fmsuperscout_dump_path  # noqa: PLC0415
                from fm27si.connectors.live_fmsuperscout import FMSuperScoutLiveConnector, run_scanner  # noqa: PLC0415

                if args.scan:
                    run_scanner(args.scan)
                bundle = FMSuperScoutLiveConnector().load(args.path or fmsuperscout_dump_path())
        except ConnectorError as e:
            print(f"Erro: {e}", file=sys.stderr)
            return 2
        res = import_bundle(session, bundle, career_key=args.career_key)
        r = res.run
        print(json.dumps({
            "run_id": r.id, "career_id": r.career_id, "duplicate": res.duplicate,
            "players": r.player_count, "created": res.created_players, "updated": res.updated_players,
            "errors": r.error_count, "warnings": r.warning_count, "game_date": str(r.game_date),
            "season": r.season_label, "messages": res.warnings[:20],
        }, indent=2, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
