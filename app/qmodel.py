"""문제 데이터 모델 & 직렬화.

- 판독 초안(draft) JSON: 페이지 단위, data/ocr_draft/{src}_pNNN.json
- 확정 문제(question) MD: data/questions/{RR}/{RR}-{NN}.md  (YAML frontmatter + 본문)

exambook/src/exambook/questions_io.py 의 방식을 이 프로젝트 스키마에 맞게 경량 이식.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_pages"
DRAFT = ROOT / "data" / "ocr_draft"
INDEX = ROOT / "data" / "index"

# 책 단위 출력: 작업폴더 루트(프로젝트의 상위)에 ocr-output-<날짜>/ 를 만들고
# 그 안에 파이프라인 단계별 폴더(01=OCR MD, 02=집필, 03=요약 ...)를 쌓는다.
# 이 폴더가 다른 앱들의 입력으로 사용된다.
BOOK_DATE = ROOT.name.split("-")[0]                 # "260723-ocr" -> "260723"
OUT_ROOT = ROOT.parent / f"ocr-output-{BOOK_DATE}"  # D:/00work/ocr-output-260723
STAGE_OCR = "01"                                    # 01 = OCR 결과(문제 MD) 단계
QDIR = OUT_ROOT / STAGE_OCR
ANALYSIS = QDIR                                     # 난이도 통계도 같은 단계 폴더에

# SQLD 2과목 체계. 회차당 보통 1~10 = 1과목, 11~50 = 2과목.
SUBJECT_MAP = {
    1: ("데이터 모델링의 이해", 1),
    2: ("SQL 기본 및 활용", 2),
}
DIFFICULTIES = ("하", "중", "상")

FRONTMATTER_ORDER = [
    "id", "round", "round_label", "subject", "subject_no", "question_no",
    "answer", "answer_index", "difficulty", "source_pdf", "source_pages",
    "has_figure", "has_sql", "has_table", "ocr_by", "verified", "reviewed",
    "needs_review",
]

CIRCLED = {"①": 0, "②": 1, "③": 2, "④": 3, "⑤": 4}
CIRCLED_INV = {0: "①", 1: "②", 2: "③", 3: "④", 4: "⑤"}


def subject_for(question_no: int, subject_no: int | None = None) -> tuple[str, int]:
    """과목명/번호 결정. subject_no 가 주어지면 우선, 아니면 문항번호로 추정."""
    if subject_no in SUBJECT_MAP:
        return SUBJECT_MAP[subject_no]
    inferred = 1 if question_no <= 10 else 2
    return SUBJECT_MAP[inferred]


def answer_to_index(answer: str | None) -> int | None:
    if not answer:
        return None
    a = answer.strip()
    if a in CIRCLED:
        return CIRCLED[a]
    if a.isdigit() and 1 <= int(a) <= 5:
        return int(a) - 1
    return None


def index_to_circled(idx: int | None) -> str:
    if idx is None:
        return ""
    return CIRCLED_INV.get(idx, "")


# ---------------------------------------------------------------- MD 직렬화

def _img(f: dict[str, Any]) -> str:
    src = f.get("path") or f.get("file") or ""
    note = f.get("note") or "figure"
    return f"![{note}]({src})" if src else ""


def _is_explanation_fig(f: dict[str, Any]) -> bool:
    return (f.get("placement") or "지문") in ("해설", "explanation")


def _render_block(b: dict[str, Any]) -> str:
    """지문 블록 하나를 MD 로 렌더. type: sql | table | text | figure."""
    t = b.get("type")
    if t == "sql":
        return "```sql\n" + (b.get("text") or "").strip() + "\n```"
    if t == "table":
        title = (b.get("title") or "").strip()
        md = (b.get("md") or "").strip()
        return f"**{title}**\n\n{md}" if title else md
    if t == "text":
        return (b.get("text") or "").strip()
    if t == "figure":
        return _img(b)
    return ""


# ---------------------------------------------------------------- 자산/토큰
# 자산(assets): {"t-1": {type:table,title,md}, "b-1": {type:sql,text}, "p-1": {type:figure,bbox/path,note}}
# 본문/선지/해설 어디서든 {{t-1}} 토큰으로 그 위치에 펼친다.
_TOKEN_RE = re.compile(r"\{\{([A-Za-z]+-\d+)\}\}")


def _asset_md(a: dict[str, Any]) -> str:
    t = a.get("type")
    if t == "table":
        title = (a.get("title") or "").strip()
        md = (a.get("md") or "").strip()
        return f"**{title}**\n\n{md}" if title else md
    if t in ("sql", "box"):
        return "```sql\n" + (a.get("text") or "").strip() + "\n```"
    if t == "figure":
        return _img(a)
    if t == "text":
        return "```text\n" + (a.get("text") or "").strip() + "\n```"
    return ""


def expand_tokens(text: str, assets: dict[str, Any]) -> str:
    if not text:
        return text or ""
    return _TOKEN_RE.sub(lambda m: _asset_md(assets[m.group(1)]) if m.group(1) in assets
                         else m.group(0), text)


def _has(q: dict[str, Any], kind: str) -> bool:
    """has_table/sql/figure 판정 (자산 우선, 없으면 레거시 필드)."""
    assets = q.get("assets") or {}
    if assets:
        types = [a.get("type") for a in assets.values()]
        return (("sql" in types or "box" in types) if kind == "sql" else kind in types)
    return bool(q.get({"figure": "figures", "sql": "sql", "table": "tables"}[kind]))


def _body_tokens(q: dict[str, Any], assets: dict[str, Any]) -> str:
    parts = ["## 문제\n" + expand_tokens((q.get("stem") or "").strip(), assets)]
    jm = expand_tokens((q.get("jimun") or "").strip(), assets)
    if jm.strip():
        parts.append("## 지문\n" + jm)
    lines = []
    for i, c in enumerate(q.get("choices") or []):
        ex = expand_tokens((c or "").strip(), assets)
        mark = CIRCLED_INV.get(i, f"{i + 1}.")
        blocky = "\n" in ex or ex.lstrip()[:2] in ("**", "| ", "``", "![") or ex.lstrip().startswith("|")
        lines.append(f"{mark}\n\n{ex}" if blocky else f"{mark} {ex}")
    parts.append("## 보기\n" + "\n\n".join(lines))
    expl = expand_tokens((q.get("explanation") or "").strip(), assets)
    if expl.strip():
        parts.append("## 해설\n" + expl)
    return "\n\n".join(parts) + "\n"


def _body(q: dict[str, Any]) -> str:
    """본문 순서: 문제 → 지문(SQL/표/그림) → 보기 → 해설.

    assets 가 있으면 토큰 모드(자산을 토큰 위치에 펼침). 없으면 레거시(고정 슬롯).
    """
    assets = q.get("assets") or {}
    if assets:
        return _body_tokens(q, assets)

    parts: list[str] = []
    parts.append("## 문제\n" + (q.get("stem") or "").strip())

    figs = q.get("figures") or []
    stem_figs = [f for f in figs if not _is_explanation_fig(f)]
    expl_figs = [f for f in figs if _is_explanation_fig(f)]

    # 표/ SQL 위치: 기본 '지문', '해설' 지정 시 해설로 이동
    tables_in_expl = (q.get("tables_placement") or "지문") in ("해설", "explanation")
    sql_in_expl = (q.get("sql_placement") or "지문") in ("해설", "explanation")

    # 지문(자료): SQL → 표 → 발문용 그림
    jimun: list[str] = []
    if q.get("sql") and not sql_in_expl:
        jimun.append("```sql\n" + q["sql"].strip() + "\n```")
    if q.get("tables") and not tables_in_expl:
        jimun.append(q["tables"].strip())
    for f in stem_figs:
        img = _img(f)
        if img:
            jimun.append(img)
    if jimun:
        parts.append("## 지문\n" + "\n\n".join(jimun))

    lines = [f"{CIRCLED_INV.get(i, str(i + 1) + '.')} {(c or '').strip()}"
             for i, c in enumerate(q.get("choices") or [])]
    parts.append("## 보기\n" + "\n".join(lines))

    # 해설: 해설 텍스트 → (해설 위치의) SQL/표 → 해설 그림
    expl: list[str] = []
    if q.get("explanation"):
        expl.append(q["explanation"].strip())
    if q.get("sql") and sql_in_expl:
        expl.append("```sql\n" + q["sql"].strip() + "\n```")
    if q.get("tables") and tables_in_expl:
        expl.append(q["tables"].strip())
    for f in expl_figs:
        img = _img(f)
        if img:
            expl.append(img)
    if expl:
        parts.append("## 해설\n" + "\n\n".join(expl))
    return "\n\n".join(parts) + "\n"


def question_path(round_no: int, question_no: int) -> Path:
    rr = f"{round_no:02d}"
    return QDIR / f"{rr}-{question_no:02d}.md"


def write_question(q: dict[str, Any]) -> Path:
    """dict -> MD 파일. 필수: round, question_no."""
    rn = int(q["round"])
    qn = int(q["question_no"])
    subject, subject_no = subject_for(qn, q.get("subject_no"))
    if q.get("subject"):
        subject = q["subject"]
    ans = q.get("answer") or index_to_circled(q.get("answer_index"))
    ans_idx = q.get("answer_index")
    if ans_idx is None:
        ans_idx = answer_to_index(ans)

    fm = {
        "id": f"{rn:02d}-{qn:02d}",
        "round": rn,
        "round_label": q.get("round_label", f"최신 기출문제 {rn:02d}회"),
        "subject": subject,
        "subject_no": q.get("subject_no", subject_no),
        "question_no": qn,
        "answer": ans or "",
        "answer_index": ans_idx,
        "difficulty": q.get("difficulty"),
        "source_pdf": q.get("source_pdf", ""),
        "source_pages": q.get("source_pages", []),
        "has_figure": _has(q, "figure"),
        "has_sql": _has(q, "sql"),
        "has_table": _has(q, "table"),
        "ocr_by": q.get("ocr_by", "claude"),
        "verified": bool(q.get("verified", False)),
        "reviewed": bool(q.get("reviewed", False)),
        "needs_review": bool(q.get("needs_review", True)),
    }
    ordered = {k: fm[k] for k in FRONTMATTER_ORDER if k in fm}
    front = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False).strip()
    text = f"---\n{front}\n---\n\n{_body(q)}"

    path = question_path(rn, qn)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def crop_figure(src: str, page: int, bbox: list[int], dest: Path) -> None:
    """페이지 PNG에서 bbox 영역을 크롭해 dest 로 저장."""
    from PIL import Image
    img = Image.open(RAW / src / f"page_{page:03d}.png")
    x, y, w, h = [max(0, int(v)) for v in bbox]
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.crop((x, y, x + w, y + h)).save(dest)


def finalize_question(q: dict[str, Any], src: str, page: int) -> Path:
    """그림 bbox 크롭 → 이미지 저장 후, 문제 MD 기록. server/CLI 공용."""
    rn = int(q["round"])
    qn = int(q["question_no"])
    qid = f"{rn:02d}-{qn:02d}"

    # 자산(figure) 크롭
    for aid, a in (q.get("assets") or {}).items():
        if a.get("type") == "figure" and a.get("bbox"):
            rel = f"images/{qid}_{aid}.png"
            crop_figure(src, page, a["bbox"], QDIR / rel)
            a["path"] = rel

    # 레거시 figures 크롭
    figs_out = []
    for i, f in enumerate(q.get("figures", []) or [], 1):
        if f.get("bbox"):
            rel = f"images/{qid}_{i}.png"
            crop_figure(src, page, f["bbox"], QDIR / rel)
            figs_out.append({"path": rel, "note": f.get("note", "figure"),
                             "bbox": f["bbox"], "placement": f.get("placement", "지문")})
        elif f.get("path"):
            figs_out.append(f)
    q["figures"] = figs_out
    q.setdefault("source_pdf", f"{src}.pdf")
    q.setdefault("source_pages", [page])
    return write_question(q)


_SEC = re.compile(r"^##\s+(문제|지문|보기|SQL|표|그림|해설)\s*$", re.M)


def read_question(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    fm: dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        _, front, body = raw.split("---", 2)
        fm = yaml.safe_load(front) or {}

    sections: dict[str, str] = {}
    matches = list(_SEC.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()

    q: dict[str, Any] = dict(fm)
    q["stem"] = sections.get("문제", "")
    choices: list[str] = []
    for line in sections.get("보기", "").splitlines():
        mm = re.match(r"^\s*(?:\d+[.)]|[①②③④⑤])\s*(.*)$", line)
        if mm:
            choices.append(mm.group(1).strip())
    q["choices"] = choices
    jimun = sections.get("지문", "")
    q["jimun"] = jimun
    # SQL: 신형은 지문 안 fenced 블록, 구형은 ## SQL 섹션
    sql_sec = sections.get("SQL", "")
    m_sql = re.search(r"```sql\s*(.*?)```", jimun, re.S)
    if m_sql:
        q["sql"] = m_sql.group(1).strip()
    elif sql_sec:
        q["sql"] = re.sub(r"^```sql\s*|\s*```$", "", sql_sec).strip()
    else:
        q["sql"] = ""
    q["tables"] = sections.get("표", "")
    q["explanation"] = sections.get("해설", "")
    return q


# ---------------------------------------------------------------- 초안 JSON

def draft_path(src: str, page: int) -> Path:
    return DRAFT / f"{src}_p{page:03d}.json"


def load_draft(src: str, page: int) -> dict[str, Any] | None:
    p = draft_path(src, page)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def save_draft(src: str, page: int, data: dict[str, Any]) -> Path:
    p = draft_path(src, page)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def list_pages(src: str) -> list[int]:
    d = RAW / src
    if not d.exists():
        return []
    pages = []
    for f in d.glob("page_*.png"):
        m = re.match(r"page_(\d+)\.png", f.name)
        if m:
            pages.append(int(m.group(1)))
    return sorted(pages)
