"""Stage 7 — 확정 MD 스냅샷 인덱스 + 난이도 통계 내보내기.

- data/questions/**/*.md 를 모두 읽어 data/questions/_index.json 생성
- 회차/과목/난이도 분포를 data/analysis/difficulty_stats.json 로 롤업
  (이 통계만 Task 2/3 로 넘어가는 것을 원칙으로 함 — verbatim 본문은 넘기지 않음)

실행:  python scripts/export_index.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import qmodel as M  # noqa: E402


def main() -> None:
    items = []
    for md in sorted(M.QDIR.glob("*.md")):
        q = M.read_question(md)
        items.append({
            "id": q.get("id"),
            "round": q.get("round"),
            "subject": q.get("subject"),
            "subject_no": q.get("subject_no"),
            "question_no": q.get("question_no"),
            "answer": q.get("answer"),
            "answer_index": q.get("answer_index"),
            "difficulty": q.get("difficulty"),
            "has_figure": q.get("has_figure"),
            "has_sql": q.get("has_sql"),
            "has_table": q.get("has_table"),
            "reviewed": q.get("reviewed"),
            "n_choices": len(q.get("choices", [])),
            "path": str(md.relative_to(M.OUT_ROOT)).replace("\\", "/"),
        })

    M.QDIR.mkdir(parents=True, exist_ok=True)
    (M.QDIR / "_index.json").write_text(
        json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # 난이도/과목 통계 (verbatim 없음 — 통계만)
    by_round: dict = defaultdict(lambda: {"count": 0, "difficulty": Counter(),
                                          "subject": Counter(), "with_figure": 0,
                                          "with_sql": 0})
    overall = {"difficulty": Counter(), "subject": Counter()}
    for it in items:
        r = it["round"]
        b = by_round[r]
        b["count"] += 1
        b["difficulty"][it.get("difficulty") or "미정"] += 1
        b["subject"][it.get("subject") or "미정"] += 1
        b["with_figure"] += 1 if it.get("has_figure") else 0
        b["with_sql"] += 1 if it.get("has_sql") else 0
        overall["difficulty"][it.get("difficulty") or "미정"] += 1
        overall["subject"][it.get("subject") or "미정"] += 1

    stats = {
        "total": len(items),
        "overall": {"difficulty": dict(overall["difficulty"]),
                    "subject": dict(overall["subject"])},
        "by_round": {str(k): {"count": v["count"],
                              "difficulty": dict(v["difficulty"]),
                              "subject": dict(v["subject"]),
                              "with_figure": v["with_figure"],
                              "with_sql": v["with_sql"]}
                     for k, v in sorted(by_round.items(), key=lambda x: (x[0] is None, x[0]))},
    }
    M.ANALYSIS.mkdir(parents=True, exist_ok=True)
    (M.ANALYSIS / "difficulty_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"index: {len(items)} questions -> {(M.QDIR / '_index.json').relative_to(M.OUT_ROOT.parent)}")
    print(f"stats -> {(M.ANALYSIS / 'difficulty_stats.json').relative_to(M.OUT_ROOT.parent)}")
    print(json.dumps(stats["by_round"], ensure_ascii=False))


if __name__ == "__main__":
    main()
