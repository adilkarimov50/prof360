"""Сборка данных сайта: data/*.json -> site/assets/js/data.js.

Данные встраиваются в JS-файл, а не загружаются через fetch, чтобы паспорт
открывался как с GitHub Pages, так и напрямую с диска (протокол file://).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TARGET = ROOT / "docs" / "assets" / "js" / "data.js"
KARASAI_ANALYSIS = DATA / "karasai" / "analysis.json"
KARASAI_JS = ROOT / "docs" / "assets" / "js" / "karasai_analysis.js"
KARASAI_REPORT_RU = DATA / "karasai" / "report_ru.json"
KARASAI_REPORT_JS = ROOT / "docs" / "assets" / "js" / "karasai_report_ru.js"

# Порядок населённых пунктов в интерфейсе.
ORDER = [
    "alatau", "konaev", "kaskelen", "talgar",
    "otegen_batyr", "irgeli", "uzynagash", "chundzha", "issyk",
]

SKIP_JSON = {"geo", "districts"}


def load_passports() -> list[dict]:
    files = {path.stem: path for path in DATA.glob("*.json") if not path.stem.startswith("_")}
    for skip in SKIP_JSON:
        files.pop(skip, None)
    ordered = [name for name in ORDER if name in files]
    ordered += sorted(name for name in files if name not in ORDER)
    return [json.loads(files[name].read_text(encoding="utf-8")) for name in ordered]


def _embed_json(src: Path, target: Path, var_name: str) -> None:
    if not src.exists():
        return
    body = src.read_text(encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"/* Сформировано scripts/build.py — не редактировать вручную. */\n"
        f"window.{var_name} = {body};\n",
        encoding="utf-8",
    )
    print(f"{target.relative_to(ROOT)} — {var_name}")


def _build_karasai_js() -> None:
    """Экспорт analysis.json → karasai_analysis.js для дашборда."""
    if not KARASAI_ANALYSIS.exists():
        # Генерация через backend, если analysis.json ещё нет
        import subprocess
        import sys

        backend = ROOT.parent / "backend"
        venv_py = backend / ".venv" / "bin" / "python3"
        py = str(venv_py) if venv_py.exists() else sys.executable
        env = {**__import__("os").environ, "PYTHONPATH": str(backend)}
        subprocess.run(
            [
                py,
                "-c",
                "from app.analytics.karasai_crosscheck import build_analysis; "
                "import json; from pathlib import Path; "
                f"p=Path('{KARASAI_ANALYSIS}'); p.parent.mkdir(parents=True, exist_ok=True); "
                "p.write_text(json.dumps(build_analysis(), ensure_ascii=False, indent=2)+'\\n', encoding='utf-8')",
            ],
            cwd=str(backend),
            env=env,
            check=False,
        )
    if KARASAI_ANALYSIS.exists():
        body = KARASAI_ANALYSIS.read_text(encoding="utf-8")
        KARASAI_JS.parent.mkdir(parents=True, exist_ok=True)
        KARASAI_JS.write_text(
            "/* Сформировано scripts/build.py — не редактировать вручную. */\n"
            f"window.KARASAI_ANALYSIS = {body};\n",
            encoding="utf-8",
        )
        print(f"{KARASAI_JS.relative_to(ROOT)} — дашборд Карасай")
    else:
        print("karasai analysis.json не найден — пропуск дашборда")

    _embed_json(KARASAI_REPORT_RU, KARASAI_REPORT_JS, "KARASAI_REPORT_RU")


def main() -> None:
    districts_path = DATA / "districts.json"
    districts = json.loads(districts_path.read_text(encoding="utf-8")) if districts_path.exists() else {}
    payload = {
        "passports": load_passports(),
        "geo": json.loads((DATA / "geo.json").read_text(encoding="utf-8")),
        "districts": districts,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        "/* Сформировано scripts/build.py — не редактировать вручную. */\n"
        f"window.KRIM_DATA = {body};\n",
        encoding="utf-8",
    )
    names = ", ".join(p["name"] for p in payload["passports"])
    print(f"{TARGET.relative_to(ROOT)} — паспортов: {len(payload['passports'])} ({names})")
    _build_karasai_js()


if __name__ == "__main__":
    main()
