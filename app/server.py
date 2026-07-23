"""Stage 5 — 검수 웹 UI (FastAPI).

좌: 스캔 페이지 이미지 / 우: 판독 초안(문제 목록) 편집.
한 페이지 초안을 여러 문제로 분할·추가·편집 후 확정 MD 저장.
그림은 이미지 위 드래그 영역(bbox) 을 크롭해 문제별로 저장.

실행:  python -m app.server   (기본 http://127.0.0.1:8010)
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from PIL import Image

from . import qmodel as M

app = FastAPI(title="OCR 검수 UI")
STATIC = Path(__file__).resolve().parent / "static"


# --------------------------------------------------------------- 페이지/개요
def _page_map() -> dict[str, Any]:
    p = M.INDEX / "page_map.json"
    if p.exists():
        return {f'{e["src"]}:{e["page"]}': e for e in json.loads(p.read_text("utf-8"))}
    return {}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/overview")
def overview() -> JSONResponse:
    pm = _page_map()
    out = []
    for src in ("1", "2"):
        for page in M.list_pages(src):
            key = f"{src}:{page}"
            meta = pm.get(key, {})
            draft = M.load_draft(src, page)
            out.append({
                "src": src, "page": page,
                "round": meta.get("round") or (draft or {}).get("round"),
                "round_label": meta.get("round_label") or (draft or {}).get("round_label"),
                "question_range": meta.get("question_range"),
                "has_draft": draft is not None,
                "n_questions": len(draft.get("questions", [])) if draft else 0,
            })
    # 확정 문제 카운트
    finalized = {}
    for md in M.QDIR.glob("*.md"):
        rr = md.name[:2]
        finalized.setdefault(rr, 0)
        finalized[rr] += 1
    return JSONResponse({"pages": out, "finalized": finalized})


@app.get("/scan/{src}/{page}")
def scan(src: str, page: int) -> FileResponse:
    p = M.RAW / src / f"page_{page:03d}.png"
    if not p.exists():
        raise HTTPException(404, "no scan")
    return FileResponse(p, media_type="image/png")


# --------------------------------------------------------------- 초안 CRUD
def _skeleton(src: str, page: int) -> dict[str, Any]:
    pm = _page_map().get(f"{src}:{page}", {})
    return {
        "src": src, "page": page,
        "round": pm.get("round"),
        "round_label": pm.get("round_label"),
        "ocr_text": "",
        "answer_key_line": "",
        "questions": [],
        "notes": "",
    }


@app.get("/api/draft/{src}/{page}")
def get_draft(src: str, page: int) -> JSONResponse:
    d = M.load_draft(src, page) or _skeleton(src, page)
    return JSONResponse(d)


@app.post("/api/draft/{src}/{page}")
async def post_draft(src: str, page: int, body: dict = None) -> JSONResponse:  # type: ignore
    M.save_draft(src, page, body or {})
    return JSONResponse({"ok": True})


# --------------------------------------------------------------- 그림 크롭
def _crop_and_save(src: str, page: int, bbox: list[int], dest: Path) -> None:
    img = Image.open(M.RAW / src / f"page_{page:03d}.png")
    x, y, w, h = [max(0, int(v)) for v in bbox]
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.crop((x, y, x + w, y + h)).save(dest)


@app.get("/api/crop")
def crop_preview(src: str, page: int, x: int, y: int, w: int, h: int) -> Response:
    img = Image.open(M.RAW / src / f"page_{page:03d}.png")
    buf = io.BytesIO()
    img.crop((x, y, x + w, y + h)).save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/img/{name}")
def img_file(name: str) -> FileResponse:
    p = M.QDIR / "images" / name
    if not p.exists():
        raise HTTPException(404, "no fig")
    return FileResponse(p, media_type="image/png")


# --------------------------------------------------------------- 확정 저장
@app.post("/api/finalize")
async def finalize(body: dict) -> JSONResponse:
    """body: {src, page, questions:[...]} -> MD 저장 + 그림 크롭."""
    src = body["src"]
    page = int(body["page"])
    saved = []
    for q in body.get("questions", []):
        q["reviewed"] = True
        q["needs_review"] = False
        path = M.finalize_question(q, src, page)
        saved.append(str(path.relative_to(M.OUT_ROOT)))
    return JSONResponse({"ok": True, "saved": saved})


@app.get("/api/question/{qid}")
def get_question(qid: str) -> JSONResponse:
    p = M.QDIR / f"{qid}.md"
    if not p.exists():
        raise HTTPException(404, "no question")
    return JSONResponse(M.read_question(p))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8010)
