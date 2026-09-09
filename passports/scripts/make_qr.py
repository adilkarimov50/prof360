"""QR-код на цифровое издание паспорта — в SVG для сайта и в PNG для документов."""

from __future__ import annotations

import argparse
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://adilkarimov50.github.io/krim-passport/"


def build(url: str) -> qrcode.QRCode:
    # Уровень коррекции Q оставляет код читаемым при печати и копировании документа.
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, box_size=10, border=2)
    code.add_data(url)
    code.make(fit=True)
    return code


def write_svg(code: qrcode.QRCode, target: Path) -> None:
    matrix = code.get_matrix()
    size = len(matrix)
    rects = "".join(
        f'<rect x="{x}" y="{y}" width="1" height="1"/>'
        for y, row in enumerate(matrix)
        for x, filled in enumerate(row)
        if filled
    )
    target.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR-код">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<g fill="#0d1b33">{rects}</g></svg>\n',
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="адрес цифрового издания")
    args = parser.parse_args()

    code = build(args.url)

    svg = ROOT / "docs" / "assets" / "img" / "qr.svg"
    svg.parent.mkdir(parents=True, exist_ok=True)
    write_svg(code, svg)

    png = ROOT / "build" / "qr.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    code.make_image(fill_color="#0d1b33", back_color="white").save(png)

    print(f"{args.url}\n  {svg.relative_to(ROOT)}\n  {png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
