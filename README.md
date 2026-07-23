# OCR 검수 툴

스캔 PDF 문제집을 **문제별 구조화 MD**(문제·선택지·정답·표·SQL·그림)로 정리하는 도구.
판독은 Claude가 수행하고, 사람은 웹 UI에서 원본과 대조·수정한다.

> ⚠️ **저작권**: 원본 PDF와 추출 내용은 원저작물입니다. **비공개(private) 저장소**로만 쓰고,
> 소스 PDF·렌더 이미지는 커밋하지 마세요(`.gitignore`에 이미 제외됨).

## 설치 (최초 1회)

- Windows: `setup.bat` 더블클릭
- macOS/Linux: `./setup.sh`

가상환경(.venv) 생성 + 의존성 설치(fastapi, uvicorn, pyyaml, pillow, pypdfium2).
파이썬 3.10+ 필요.

## 실행 (검수 UI)

- Windows: `run.bat`
- macOS/Linux: `./run.sh`

→ 브라우저에서 http://127.0.0.1:8010 자동 열림. 대시보드에서 페이지 클릭 →
**좌: OCR 원문 / 우: 문제 카드**. 원본(출력물/서브모니터)과 대조하며 수정 →
문제별 **💾 저장**(자동 대조완료 체크). 저장 즉시 아래 출력 폴더로 기록된다.

## 파이프라인 (CLI)

```
python -m app.cli render     # _context/*.pdf -> data/raw_pages/<stem>/page_NNN.png
python -m app.cli serve      # 검수 웹 UI
python -m app.cli finalize   # 모든 초안 -> 문제 MD 일괄 확정
python -m app.cli export     # _index.json / difficulty_stats.json
python -m app.cli status     # 진행 현황
```

**판독(OCR)** 자체는 Claude Code 세션에서 수행: 프로젝트를 Claude Code로 열고
"N회 판독해줘" → `data/raw_pages`를 읽어 `data/ocr_draft/*.json`(초안) 생성.
이후 `serve`로 검수하거나 `finalize`로 일괄 확정.

## 새 책 OCR 절차

1. 새 프로젝트 폴더로 복사 (예: `260801-ocr`) — 출력이 자동으로 `ocr-output-260801/`로 분리됨
2. `_context/`에 스캔 PDF 넣기 (예: `1.pdf`, `2.pdf`)
3. `setup` → `python -m app.cli render`
4. Claude Code로 판독 → `serve`로 검수 → 💾 저장

## 출력 구조 (다른 앱의 입력)

작업폴더 루트(프로젝트 상위)에 책 단위 폴더가 생성된다:

```
../ocr-output-<날짜>/
  README.md                 # 폴더/파일 규칙
  01/                        # OCR 문제 MD 단계
    01-01.md ~ 07-50.md       # {회차}-{문항}.md
    images/ 01-14_1.png       # {회차}-{문항}_{순번}.png
    _index.json  difficulty_stats.json
  02/ 03/ ...                 # 이후 집필·요약·영상 파이프라인
```

MD 본문 순서: `## 문제` → `## 지문`(SQL/표/그림) → `## 보기` → `## 해설`.
표 셀 줄바꿈은 `<br>`.
