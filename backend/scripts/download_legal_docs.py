#!/usr/bin/env python3
"""Скачать все НПА из реестра с adilet в backend/data/legal/documents/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.legal.codes_registry import ACTS  # noqa: E402
from app.legal.document_cache import ensure_cached  # noqa: E402


def main() -> int:
    force = "--force" in sys.argv

    ids = [c["doc_id"] for c in ACTS]
    results = []
    for i, doc_id in enumerate(ids, 1):
        print(f"[{i}/{len(ids)}] {doc_id}...", flush=True)
        try:
            r = ensure_cached(doc_id, force=force)
            print(f"  -> {r.get('status')}", flush=True)
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            print(f"  -> ОШИБКА: {exc}", flush=True)
            results.append({"doc_id": doc_id, "status": "error", "error": str(exc)})
        if i < len(ids):
            import time
            time.sleep(2.0)
    ok = sum(1 for r in results if r.get("status") in ("cached", "downloaded"))
    print(f"Готово: {ok}/{len(results)}")
    for r in results:
        if r.get("status") == "error":
            print(f"  [ОШИБКА] {r['doc_id']}: {r.get('error')}")
    return 1 if ok < len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
