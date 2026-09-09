"""Копирует TXT НПА в passports/docs и генерирует assets/js/legal_data.js."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.legal.codes_registry import ACTS, doc_url  # noqa: E402
from app.legal.topics import TOPICS  # noqa: E402

SRC = BACKEND / "data" / "legal" / "documents"
DST = ROOT / "passports" / "docs" / "assets" / "legal"
OUT_JS = ROOT / "passports" / "docs" / "assets" / "js" / "legal_data.js"

TYPE_ORDER = {"кодекс": 0, "конституционный закон": 1, "закон": 2, "приказ": 3}


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    acts_out: list[dict] = []
    copied = 0

    for code in ACTS:
        doc_id = code["doc_id"]
        src_txt = SRC / f"{doc_id}.txt"
        dst_txt = DST / f"{doc_id}.txt"
        has_txt = False
        if src_txt.is_file():
            shutil.copy2(src_txt, dst_txt)
            copied += 1
            has_txt = True
        elif dst_txt.is_file():
            has_txt = True
        else:
            print(f"  [adilet only] нет TXT: {doc_id}")
        acts_out.append({
            "doc_id": doc_id,
            "title": code["title"],
            "number": code.get("number"),
            "act_type": code.get("act_type"),
            "adilet_url": doc_url(doc_id),
            "txt_url": f"assets/legal/{doc_id}.txt" if has_txt else None,
            "has_txt": has_txt,
            "bytes": dst_txt.stat().st_size if has_txt else 0,
            "superseded_by": code.get("superseded_by"),
        })

    acts_out.sort(key=lambda a: (TYPE_ORDER.get(a["act_type"], 9), a["title"]))

    bundles = []
    for key, bundle in TOPICS.items():
        bundles.append({
            "id": key,
            "title": bundle["title"],
            "acts": [
                {
                    "doc_id": a["doc_id"],
                    "title": a["title"],
                    "number": a["number"],
                    "adilet_url": a["adilet_url"],
                    "key_articles": a.get("key_articles", []),
                    "note": a.get("note", ""),
                }
                for a in bundle["acts"]
            ],
        })

    payload = {
        "updated": date.today().isoformat(),
        "adilet_base": "https://adilet.zan.kz",
        "count": len(acts_out),
        "bundles": bundles,
        "acts": acts_out,
    }

    js = (
        "/** Автогенерация: passports/scripts/build_legal.py — не править вручную */\n"
        f"window.LEGAL_CATALOG = {json.dumps(payload, ensure_ascii=False, indent=2)};\n"
    )
    OUT_JS.write_text(js, encoding="utf-8")
    print(f"Скопировано TXT: {copied} → {DST}")
    print(f"Каталог: {OUT_JS} ({len(acts_out)} актов)")
    return 0 if acts_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
