"""Stage 1 — PDF -> 페이지 PNG 렌더 (pypdfium2, 크로스플랫폼·pip 전용).

_context/*.pdf 를 200 DPI PNG 로 렌더하여
data/raw_pages/<stem>/page_NNN.png 로 저장한다. (stem = PDF 파일명, 예: 1, 2)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "_context"
OUT = ROOT / "data" / "raw_pages"
DPI = 200


def render_pdf(pdf: Path, out_dir: Path) -> int:
    import pypdfium2 as pdfium

    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    n = len(doc)
    scale = DPI / 72.0
    for i in range(n):
        page = doc[i]
        pil = page.render(scale=scale).to_pil()
        pil.save(out_dir / f"page_{i + 1:03d}.png")
    doc.close()
    return n


def main() -> None:
    pdfs = sorted(CONTEXT.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"_context 에 PDF가 없습니다: {CONTEXT}")
    total = 0
    for pdf in pdfs:
        n = render_pdf(pdf, OUT / pdf.stem)
        print(f"{pdf.name}: {n} pages -> {OUT / pdf.stem}")
        total += n
    print(f"TOTAL: {total} pages")


if __name__ == "__main__":
    main()
