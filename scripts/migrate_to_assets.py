"""레거시 초안(sql/tables/figures + placement) -> 자산(assets)+토큰({{t-1}}) 변환.

- tables 필드의 여러 '**제목**' 표를 각각 t-1, t-2 ... 로 분리
- sql -> b-1, figure -> p-1 ...
- SQL로 보이는 선지(SELECT/INSERT/... 로 시작)는 코드박스 자산(b-N)으로 변환해 선지에 토큰 삽입
- 지문/해설 위치는 placement 를 반영해 stem/explanation 에 토큰 배치

사용: python scripts/migrate_to_assets.py [초안글롭]   (기본 data/ocr_draft/1_p*.json)
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SQL_CHOICE = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|GROUP\s+BY)\b", re.I)
_TITLE = re.compile(r"^\*\*(.+?)\*\*\s*$")


def split_tables(md: str) -> list[tuple[str, str]]:
    md = (md or "").strip()
    if not md:
        return []
    parts: list[tuple[str, str]] = []
    title, buf, started = None, [], False

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            parts.append((title or "", body))

    for ln in md.split("\n"):
        m = _TITLE.match(ln.strip())
        if m:
            if started:
                flush()
            title, buf, started = m.group(1), [], True
        else:
            buf.append(ln)
            started = True
    flush()
    return parts or [("", md)]


def migrate_q(q: dict) -> bool:
    if q.get("assets"):
        return False
    assets: dict = {}
    nt = nb = npic = 0
    stem_tok: list[str] = []
    expl_tok: list[str] = []

    if q.get("sql"):
        nb += 1
        aid = f"b-{nb}"
        assets[aid] = {"type": "sql", "text": q["sql"]}
        (expl_tok if q.get("sql_placement") in ("해설", "explanation") else stem_tok).append(aid)

    if q.get("tables"):
        for title, md in split_tables(q["tables"]):
            nt += 1
            aid = f"t-{nt}"
            assets[aid] = {"type": "table", "title": title, "md": md}
            (expl_tok if q.get("tables_placement") in ("해설", "explanation") else stem_tok).append(aid)

    for f in q.get("figures") or []:
        npic += 1
        aid = f"p-{npic}"
        a = {"type": "figure", "note": f.get("note", "figure")}
        if f.get("bbox"):
            a["bbox"] = f["bbox"]
        if f.get("path"):
            a["path"] = f["path"]
        assets[aid] = a
        (expl_tok if f.get("placement") in ("해설", "explanation") else stem_tok).append(aid)

    # SQL 선지 -> 코드박스 자산
    new_choices = []
    for c in q.get("choices") or []:
        if c and SQL_CHOICE.match(c):
            nb += 1
            aid = f"b-{nb}"
            assets[aid] = {"type": "sql", "text": c}
            new_choices.append("{{" + aid + "}}")
        else:
            new_choices.append(c)
    q["choices"] = new_choices

    stem = (q.get("stem") or "").rstrip()
    if stem_tok:
        stem += ("\n\n" if stem else "") + "\n\n".join("{{%s}}" % t for t in stem_tok)
    q["stem"] = stem
    expl = (q.get("explanation") or "").rstrip()
    if expl_tok:
        expl += ("\n\n" if expl else "") + "\n\n".join("{{%s}}" % t for t in expl_tok)
    q["explanation"] = expl

    if assets:
        q["assets"] = assets
    for k in ("sql", "tables", "figures", "sql_placement", "tables_placement"):
        q.pop(k, None)
    return bool(assets)


def main() -> None:
    pat = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "ocr_draft" / "1_p*.json")
    files = sorted(glob.glob(pat))
    total_q = total_migrated = 0
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        changed = 0
        for q in d.get("questions", []):
            total_q += 1
            if migrate_q(q):
                changed += 1
                total_migrated += 1
        Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{Path(f).name}: {changed} questions -> assets")
    print(f"총 {total_q}문항 중 {total_migrated}문항에 자산 정의")


if __name__ == "__main__":
    main()
