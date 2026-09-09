#!/usr/bin/env python3
"""Экспорт Word-справки «реальная картина» без запуска API."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from app.reports.karasai_reality_report import karasai_reality_docx  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "karasai" / "karasai_reality_report.docx"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(karasai_reality_docx("Система", "local"))
    print(f"Written {OUT}")


if __name__ == "__main__":
    main()
