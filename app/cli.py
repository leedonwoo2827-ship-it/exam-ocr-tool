"""OCR 검수 툴 CLI.

사용:
  python -m app.cli render     # _context/*.pdf -> data/raw_pages/<stem>/page_NNN.png
  python -m app.cli serve      # 검수 웹 UI (기본 http://127.0.0.1:8010)
  python -m app.cli finalize   # 모든 초안(data/ocr_draft/*.json) -> 문제 MD 일괄 확정
  python -m app.cli export     # _index.json / difficulty_stats.json 생성
  python -m app.cli status     # 진행 현황

판독(OCR) 자체는 Claude Code 세션에서 수행합니다:
  프로젝트를 Claude Code로 열고 "N회 판독해줘" 요청 → data/raw_pages 를 읽어
  data/ocr_draft/*.json(초안)을 생성. 이후 serve 로 검수하거나 finalize 로 일괄 확정.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app import qmodel as M  # noqa: E402


def cmd_render(_a: argparse.Namespace) -> None:
    import render
    render.main()


def cmd_serve(a: argparse.Namespace) -> None:
    import uvicorn
    print(f"검수 UI: http://{a.host}:{a.port}")
    uvicorn.run("app.server:app", host=a.host, port=a.port)


def cmd_export(_a: argparse.Namespace) -> None:
    import export_index
    export_index.main()


def cmd_finalize(_a: argparse.Namespace) -> None:
    n = 0
    for f in sorted(M.DRAFT.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        src = str(d.get("src"))
        page = int(d.get("page"))
        for q in d.get("questions", []):
            if not q.get("round") or not q.get("question_no"):
                continue
            M.finalize_question(q, src, page)
            n += 1
    print(f"finalized MD: {n}")
    import export_index
    export_index.main()


def cmd_status(_a: argparse.Namespace) -> None:
    mds = list(M.QDIR.glob("*.md"))
    drafts = list(M.DRAFT.glob("*.json"))
    pages = sum(len(M.list_pages(s)) for s in ("1", "2"))
    print(f"출력 폴더 : {M.QDIR}")
    print(f"렌더 페이지 : {pages}")
    print(f"초안 페이지 : {len(drafts)}")
    print(f"확정 MD    : {len(mds)}")


def main() -> None:
    p = argparse.ArgumentParser(prog="ocr-tool", description="OCR 검수 툴")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("render", help="PDF -> 페이지 PNG")
    s = sub.add_parser("serve", help="검수 웹 UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8010)
    sub.add_parser("finalize", help="초안 -> MD 일괄 확정")
    sub.add_parser("export", help="인덱스/통계 생성")
    sub.add_parser("status", help="진행 현황")
    a = p.parse_args()
    {"render": cmd_render, "serve": cmd_serve, "export": cmd_export,
     "finalize": cmd_finalize, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
