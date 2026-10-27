"""Build the source-code listing for the software-copyright (软著) filing.

Reads the in-scope source files from a git ref (not the working tree), so the
listing always matches a committed baseline, and writes:

* ``源程序.pdf``      — the first and last 30 pages of the full listing
                        (all pages when the listing has 60 or fewer), 50
                        source lines per page, software name and version in
                        the header, page number top right;
* ``源程序-清单.txt`` — totals and which files each submitted page covers;
* ``源程序-文本.txt`` — the submitted lines as plain text, for review.

Usage::

    python scripts/ruanzhu/build_source_listing.py --ref main
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

SOFTWARE = "大模型应用多源证据分层安全评测平台 V1.0"
LINES_PER_PAGE = 50
HEAD_PAGES = 30
TAIL_PAGES = 30

SCOPE = ("backend/app", "frontend/src")
EXTENSIONS = (".py", ".ts", ".tsx", ".css")
EXCLUDED = re.compile(r"(^backend/app/tests/|^frontend/src/test/|\.test\.tsx?$)")

# The listing opens with the backend entry and the multi-source evidence chain
# (evidence model, collectors, arbiter, verdict rules) ...
HEAD_FILES = [
    "backend/app/main.py",
    "backend/app/services/evidence.py",
    "backend/app/services/collectors/base.py",
    "backend/app/services/collectors/rule_hit.py",
    "backend/app/services/collectors/judge.py",
    "backend/app/services/collectors/control.py",
    "backend/app/services/collectors/probe.py",
    "backend/app/services/collectors/behavior.py",
    "backend/app/services/collectors/signature.py",
    "backend/app/services/verdict_arbiter.py",
    "backend/app/services/verdict_engine.py",
    "backend/app/services/control_variants.py",
]
# ... and closes with response evaluation and the attack-results UI.
TAIL_FILES = [
    "frontend/src/utils/responseEvaluation.ts",
    "frontend/src/components/ResponseEvaluationPanel.tsx",
    "frontend/src/utils/resultLabels.ts",
    "frontend/src/utils/resultRows.ts",
    "frontend/src/components/results/NotEvaluablePills.tsx",
    "frontend/src/components/results/VariantTabs.tsx",
    "frontend/src/components/results/ResultsFilters.tsx",
    "frontend/src/components/results/ResultRowItem.tsx",
    "frontend/src/components/results/ResultDetail.tsx",
    "frontend/src/pages/ScanResults.tsx",
]

FONTS_DIR = Path("C:/Windows/Fonts")
CODE_FONT = ("Code", FONTS_DIR / "consola.ttf", 0)
FALLBACK_FONTS = [
    ("CJK", FONTS_DIR / "msyh.ttc", 0),
    ("Hangul", FONTS_DIR / "malgun.ttf", 0),
    ("Symbol", FONTS_DIR / "seguisym.ttf", 0),
]
FONT_SIZE = 8.4
HEADER_SIZE = 9
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 48, 40, 64, 40
ROW_HEIGHT = 14.0


@dataclass
class SourceLine:
    path: str
    text: str


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def in_scope_files(ref: str | None) -> list[str]:
    if ref is None:
        listed = git("ls-files", "--", *SCOPE).splitlines()
    else:
        listed = git("ls-tree", "-r", "--name-only", ref, "--", *SCOPE).splitlines()
    files = [p for p in listed if p.endswith(EXTENSIONS) and not EXCLUDED.search(p)]
    missing = [p for p in HEAD_FILES + TAIL_FILES if p not in files]
    if missing:
        raise SystemExit(f"Ordered files not found at {ref}: {missing}")
    middle = sorted(p for p in files if p not in HEAD_FILES and p not in TAIL_FILES)
    backend = [p for p in middle if p.startswith("backend/")]
    frontend = [p for p in middle if p.startswith("frontend/")]
    return HEAD_FILES + backend + frontend + TAIL_FILES


def file_marker(path: str) -> str:
    if path.endswith(".py"):
        return f"# ---- {path} ----"
    if path.endswith(".css"):
        return f"/* ---- {path} ---- */"
    return f"// ---- {path} ----"


def source_lines(ref: str | None, files: list[str]) -> list[SourceLine]:
    lines: list[SourceLine] = []
    for path in files:
        text = Path(path).read_text(encoding="utf-8") if ref is None else git("show", f"{ref}:{path}")
        body = [raw.expandtabs(4).rstrip() for raw in text.splitlines() if raw.strip()]
        if not body:
            continue
        lines.append(SourceLine(path, file_marker(path)))
        lines.extend(SourceLine(path, text) for text in body)
    return lines


class Fonts:
    def __init__(self) -> None:
        self.order: list[tuple[str, set[int]]] = []
        for name, file, index in [CODE_FONT, *FALLBACK_FONTS]:
            if not file.exists():
                continue
            font = TTFont(name, str(file), subfontIndex=index)
            pdfmetrics.registerFont(font)
            self.order.append((name, set(font.face.charToGlyph)))

    def font_for(self, char: str) -> str:
        code = ord(char)
        for name, covered in self.order:
            if code in covered:
                return name
        return self.order[0][0]

    def drawable(self, char: str) -> bool:
        return any(ord(char) in covered for _, covered in self.order)

    def runs(self, text: str) -> list[tuple[str, str]]:
        runs: list[tuple[str, str]] = []
        for char in text:
            name = self.font_for(char)
            if runs and runs[-1][0] == name:
                runs[-1] = (name, runs[-1][1] + char)
            else:
                runs.append((name, char))
        return runs

    def width(self, text: str, size: float) -> float:
        return sum(pdfmetrics.stringWidth(chunk, name, size) for name, chunk in self.runs(text))


def wrap(fonts: Fonts, text: str, width: float) -> list[tuple[float, str]]:
    """Split one source line into (indent, row) pairs that fit the page width.

    The code itself is never changed; continuation rows hang under the
    line's own indentation plus four columns.
    """
    hang = min(fonts.width(" " * (len(text) - len(text.lstrip()) + 4), FONT_SIZE), width * 0.4)
    rows: list[tuple[float, str]] = []
    current, indent = "", 0.0
    for char in text:
        if current and fonts.width(current + char, FONT_SIZE) > width - indent:
            rows.append((indent, current))
            current, indent = char, hang
        else:
            current += char
    rows.append((indent, current))
    return rows


def render(pages: list[list[SourceLine]], out_pdf: Path, fonts: Fonts) -> None:
    page_width, page_height = A4
    text_width = page_width - MARGIN_LEFT - MARGIN_RIGHT
    usable_height = page_height - MARGIN_TOP - MARGIN_BOTTOM
    pdf = canvas.Canvas(str(out_pdf), pagesize=A4)
    pdf.setTitle(f"{SOFTWARE} 源程序")
    for number, page in enumerate(pages, start=1):
        header_y = page_height - 40
        pdf.setFont("CJK", HEADER_SIZE)
        pdf.drawCentredString(page_width / 2, header_y, SOFTWARE)
        pdf.drawRightString(page_width - MARGIN_RIGHT, header_y, f"第 {number} 页")
        pdf.setLineWidth(0.5)
        pdf.line(MARGIN_LEFT, header_y - 6, page_width - MARGIN_RIGHT, header_y - 6)

        rows = [row for line in page for row in wrap(fonts, line.text, text_width)]
        row_height = min(ROW_HEIGHT, usable_height / max(len(rows), 1))
        y = page_height - MARGIN_TOP - row_height * 0.8
        for indent, row in rows:
            x = MARGIN_LEFT + indent
            for name, chunk in fonts.runs(row):
                pdf.setFont(name, FONT_SIZE)
                pdf.drawString(x, y, chunk)
                x += pdfmetrics.stringWidth(chunk, name, FONT_SIZE)
            y -= row_height
        pdf.showPage()
    pdf.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="main", help="git ref to read the sources from")
    parser.add_argument("--worktree", action="store_true", help="read the working tree instead of --ref (for previews)")
    parser.add_argument("--out", default=str(Path(__file__).parent / "out"), help="output folder")
    args = parser.parse_args()

    ref = None if args.worktree else args.ref
    files = in_scope_files(ref)
    lines = source_lines(ref, files)
    total_pages = math.ceil(len(lines) / LINES_PER_PAGE)
    head_lines = HEAD_PAGES * LINES_PER_PAGE
    tail_lines = TAIL_PAGES * LINES_PER_PAGE
    # The first and last 1500 lines, so every submitted page is full and the
    # last one still ends where the program ends.
    if len(lines) <= head_lines + tail_lines:
        spans = [(0, len(lines))]
    else:
        spans = [(0, head_lines), (len(lines) - tail_lines, len(lines))]
    picked = [
        (start + 1, lines[start:start + LINES_PER_PAGE])
        for begin, end in spans
        for start in range(begin, end, LINES_PER_PAGE)
    ]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fonts = Fonts()
    render([page for _, page in picked], out / "源程序.pdf", fonts)

    source = "工作区（未提交）" if ref is None else f"{ref}（{git('rev-parse', '--short', ref).strip()}）"
    code_lines = len(lines) - len({line.path for line in lines})
    manifest = [
        f"{SOFTWARE} 源程序",
        f"来源：{source}，范围：{' + '.join(SCOPE)}，不含测试",
        f"文件 {len({line.path for line in lines})} 个，有效代码 {code_lines} 行（不含空行），"
        f"全文 {len(lines)} 行约 {total_pages} 页，提交 {len(picked)} 页",
        "",
    ]
    for submitted, (first_line, page) in enumerate(picked, start=1):
        covered = list(dict.fromkeys(line.path for line in page))
        span = f"全文第 {first_line}-{first_line + len(page) - 1} 行"
        manifest.append(f"第 {submitted:>2} 页（{span}）: {', '.join(covered)}")
    (out / "源程序-清单.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    (out / "源程序-文本.txt").write_text(
        "\n".join(line.text for _, page in picked for line in page) + "\n", encoding="utf-8"
    )
    print("\n".join(manifest[:3]))
    for number, (_, page) in enumerate(picked, start=1):
        for line in page:
            missing = sorted({char for char in line.text if not char.isspace() and not fonts.drawable(char)})
            if missing:
                codes = " ".join(f"U+{ord(char):04X}" for char in missing)
                print(f"警告：第 {number} 页 {line.path} 有字体无法显示的字符 {codes}")
    print(f"写入 {out}")


if __name__ == "__main__":
    main()
