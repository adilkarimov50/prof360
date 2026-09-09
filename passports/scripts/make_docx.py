"""Добавление в исходный .docx паспорта блока со ссылкой на цифровое издание и QR-кодом.

Исходный документ не изменяется — результат сохраняется в каталог build/.

    python make_docx.py "Крим паспорт Каскелен.docx" --id kaskelen
    python make_docx.py "Крим паспорт Иргели.docx" --id irgeli

QR-код один для всех паспортов — на главную страницу выбора населённого пункта.
Параметр --id используется только для имени выходного файла.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from make_qr import DEFAULT_URL, build as build_qr

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
NAVY = RGBColor(0x0D, 0x1B, 0x33)
GREY = RGBColor(0x5D, 0x6B, 0x80)


def qr_png(url: str, target: Path) -> Path:
    code = build_qr(url)
    target.parent.mkdir(parents=True, exist_ok=True)
    code.make_image(fill_color="#0d1b33", back_color="white").save(target)
    return target


def find_anchor(doc: Document):
    """Последний абзац титульного блока — год паспорта."""
    for paragraph in doc.paragraphs[:12]:
        if paragraph.text.strip().lower().startswith("2026"):
            return paragraph
    return doc.paragraphs[0]


def insert_block(anchor, doc: Document, url: str, repo: str, image: Path) -> None:
    """Блок вставляется сразу после титульных строк, до раздела 1."""
    made = []

    def add(text: str = "", *, size=10.5, bold=False, color=GREY, space_before=0, space_after=4):
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(space_before)
        paragraph.paragraph_format.space_after = Pt(space_after)
        if text:
            run = paragraph.add_run(text)
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
        made.append(paragraph)
        return paragraph

    add("ЦИФРОВАЯ ВЕРСИЯ ПАСПОРТА", size=10, bold=True, color=NAVY, space_before=14, space_after=6)

    picture = add(space_after=6)
    picture.add_run().add_picture(str(image), width=Cm(3.6))

    add(url, size=10, bold=True, color=NAVY, space_after=6)
    add(
        "Наведите камеру телефона на QR-код, чтобы открыть цифровое издание. "
        "На главной странице выберите населённый пункт и откройте полный паспорт: "
        "структура преступности, карта точек концентрации, карточки приоритетных мероприятий "
        "с исполнителями, сроками и критериями оценки.",
        size=9,
        space_after=4,
    )
    add(f"Исходные данные и код: {repo}", size=9, space_after=14)

    # python-docx добавляет абзацы в конец, поэтому переносим их к якорю,
    # сохраняя исходный порядок.
    for paragraph in reversed(made):
        anchor._p.addnext(paragraph._p)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="исходный .docx паспорта")
    parser.add_argument("--id", required=True, help="идентификатор населённого пункта")
    parser.add_argument("--base-url", default=DEFAULT_URL, help="адрес цифрового издания")
    parser.add_argument("--repo", default="github.com/adilkarimov50/krim-passport")
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/"
    image = qr_png(url, BUILD / "qr.png")

    doc = Document(args.source)
    insert_block(find_anchor(doc), doc, url, args.repo, image)

    BUILD.mkdir(parents=True, exist_ok=True)
    target = BUILD / f"{args.source.stem} (цифровая версия).docx"
    doc.save(target)
    print(f"{target.relative_to(ROOT)}\n  QR ведёт на {url}")


if __name__ == "__main__":
    main()
