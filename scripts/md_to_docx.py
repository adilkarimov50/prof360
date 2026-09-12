#!/usr/bin/env python3
"""Конвертация справок из Markdown в DOCX для отправки адресатам.

Поддерживает подмножество Markdown, используемое в справках репозитория:
заголовки, абзацы, маркированные и нумерованные списки, таблицы, цитаты,
горизонтальные линии, а из встроенного форматирования — полужирный, курсив,
моноширинный текст и ссылки (вставляются как кликабельные гиперссылки).

    python md_to_docx.py <файл.md> [<файл.md> ...]
    python md_to_docx.py            # все .md из ИИ_порноконтент_блокировка/
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "ИИ_порноконтент_блокировка"

BASE_FONT = "Times New Roman"
BASE_SIZE = Pt(12)
LINK_COLOR = RGBColor(0x1A, 0x4F, 0xA0)

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
ORDERED_RE = re.compile(r"^(\d+)[.)]\s+(.*)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")
RULE_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")
SEPARATOR_ROW_RE = re.compile(r"^\|[\s:|-]+\|$")
# Порядок важен: ** разбирается раньше *, иначе полужирный распадётся на курсив.
INLINE_RE = re.compile(
    r"\[(?P<text>[^\]]+)\]\((?P<url>[^)]+)\)"
    r"|\*\*(?P<bold>[^*]+)\*\*"
    r"|`(?P<code>[^`]+)`"
    r"|\*(?P<italic>[^*]+)\*"
)


def add_hyperlink(paragraph, text: str, url: str) -> None:
    """Гиперссылка: python-docx не умеет их сам, нужен внешний relationship."""
    from docx.oxml import OxmlElement

    rel_id = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    for tag, attrs in (("w:color", {"w:val": "1A4FA0"}), ("w:u", {"w:val": "single"})):
        node = OxmlElement(tag)
        for key, value in attrs.items():
            node.set(qn(key), value)
        props.append(node)
    run.append(props)
    node = OxmlElement("w:t")
    node.text = text
    run.append(node)
    link.append(run)
    paragraph._p.append(link)


def write_inline(paragraph, text: str, bold: bool = False) -> None:
    """Разбор встроенного форматирования в готовый абзац."""
    position = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > position:
            paragraph.add_run(text[position : match.start()]).bold = bold
        if match.group("url"):
            add_hyperlink(paragraph, match.group("text"), match.group("url"))
        elif match.group("bold"):
            paragraph.add_run(match.group("bold")).bold = True
        elif match.group("code"):
            run = paragraph.add_run(match.group("code"))
            run.font.name = "Consolas"
            run.font.size = Pt(10.5)
        else:
            run = paragraph.add_run(match.group("italic"))
            run.italic = True
            run.bold = bold
        position = match.end()
    if position < len(text):
        paragraph.add_run(text[position:]).bold = bold


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_blocks(lines: list[str]) -> list[tuple[str, object]]:
    """Строки Markdown -> последовательность блоков (вид, содержимое)."""
    blocks: list[tuple[str, object]] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue

        if RULE_RE.match(line):
            blocks.append(("rule", None))
            index += 1
            continue

        if line.startswith("|"):
            table = [split_row(line)]
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                row = lines[index].rstrip()
                if not SEPARATOR_ROW_RE.match(row.strip()):
                    table.append(split_row(row))
                index += 1
            blocks.append(("table", table))
            continue

        if match := HEADING_RE.match(line):
            blocks.append((f"h{len(match.group(1))}", match.group(2)))
            index += 1
            continue

        if match := BULLET_RE.match(line):
            blocks.append(("bullet", match.group(1)))
            index += 1
            continue

        if match := ORDERED_RE.match(line):
            blocks.append(("ordered", match.group(2)))
            index += 1
            continue

        if match := QUOTE_RE.match(line):
            blocks.append(("quote", match.group(1)))
            index += 1
            continue

        blocks.append(("para", line))
        index += 1
    return blocks


def build_document(blocks: list[tuple[str, object]]) -> Document:
    document = Document()

    normal = document.styles["Normal"]
    normal.font.name = BASE_FONT
    normal.font.size = BASE_SIZE
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BASE_FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for section in document.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(1.5)

    for kind, payload in blocks:
        if kind == "rule":
            document.add_paragraph()
        elif kind == "table":
            rows: list[list[str]] = payload  # type: ignore[assignment]
            width = max(len(row) for row in rows)
            table = document.add_table(rows=0, cols=width)
            table.style = "Table Grid"
            for position, row in enumerate(rows):
                cells = table.add_row().cells
                for column in range(width):
                    paragraph = cells[column].paragraphs[0]
                    paragraph.paragraph_format.space_after = Pt(2)
                    text = row[column] if column < len(row) else ""
                    write_inline(paragraph, text, bold=(position == 0))
                    for run in paragraph.runs:
                        run.font.size = Pt(10.5)
        elif kind.startswith("h"):
            level = int(kind[1])
            paragraph = document.add_heading(level=min(level, 4))
            if level == 1:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            write_inline(paragraph, str(payload))
            for run in paragraph.runs:
                run.font.name = BASE_FONT
                run.font.color.rgb = RGBColor(0, 0, 0)
        elif kind in ("bullet", "ordered"):
            style = "List Bullet" if kind == "bullet" else "List Number"
            paragraph = document.add_paragraph(style=style)
            write_inline(paragraph, str(payload))
        elif kind == "quote":
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(1)
            write_inline(paragraph, str(payload))
            for run in paragraph.runs:
                run.italic = True
        else:
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            write_inline(paragraph, str(payload))

    return document


def convert(source: Path) -> Path:
    blocks = read_blocks(source.read_text(encoding="utf-8").splitlines())
    target = source.with_suffix(".docx")
    build_document(blocks).save(target)
    return target


def main() -> None:
    sources = [Path(arg) for arg in sys.argv[1:]] or sorted(DEFAULT_DIR.glob("*.md"))
    if not sources:
        sys.exit("не найдено ни одного .md")
    for source in sources:
        target = convert(source)
        print(f"{source.name} -> {target.name} ({target.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
