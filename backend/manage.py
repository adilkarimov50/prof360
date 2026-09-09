"""CLI для инициализации БД, сидов, загрузки данных и пересчёта риска.

Примеры:
    python manage.py seed-legal    # загрузить ключевые НПА
    python manage.py ingest        # загрузить Excel из data_dir
    python manage.py recompute     # пересчитать риск-скоринг
    python manage.py reembed       # пересчитать эмбеддинги норм (после смены модели)
    python manage.py ingest-codes  # скачать и структурировать кодексы РК с adilet
    python manage.py tag-norms     # авто-теги для норм без subject/keywords
    python manage.py link-norms    # связать admin_cases.article_base с LegalNorm
    python manage.py data-quality  # отчёт качества данных
    python manage.py legal-index   # ivfflat индекс по эмбеддингам
    python manage.py all           # init + seed-legal + ingest
"""
import json
import sys

from app.analytics.scoring import recompute_all
from app.bootstrap import ensure_default_admin
from app.core.db import SessionLocal, init_db
from app.core.config import settings
from app.etl.loaders import discover_and_load_all
from app.legal.entitlements_seed import seed_entitlements
from app.legal.seed import reembed_legal, seed_legal


def cmd_init():
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        print("БД инициализирована, администратор создан.")
    finally:
        db.close()


def cmd_seed_legal():
    db = SessionLocal()
    try:
        n = seed_legal(db)
        print(f"Загружено норм НПА: {n}")
    finally:
        db.close()


def cmd_download_legal_docs():
    from app.legal.document_cache import download_all

    results = download_all(None, force="--force" in sys.argv)
    ok = sum(1 for r in results if r.get("status") in ("cached", "downloaded"))
    err = [r for r in results if r.get("status") == "error"]
    print(f"Кэш НПА: {ok}/{len(results)}")
    for r in results:
        if r.get("status") == "error":
            print(f"  [ОШИБКА] {r['doc_id']}: {r.get('error')}")
    if err:
        sys.exit(1)


def cmd_import_registry_mkb():
    from app.legal.person_icd import import_registry_mkb

    db = SessionLocal()
    try:
        print(import_registry_mkb(db))
    finally:
        db.close()


def cmd_seed_entitlements():
    db = SessionLocal()
    try:
        stats = seed_entitlements(db)
        print(f"Справочники: {stats}")
    finally:
        db.close()


def cmd_ingest(force: bool = False):
    from app.models.person import Person

    force = force or "--force" in sys.argv
    db = SessionLocal()
    try:
        existing = db.query(Person).count()
        if existing and not force:
            # Идемпотентность: при наличии данных повторный ETL пропускаем,
            # чтобы перезапуск контейнера не дублировал admin_cases.
            print(f"ETL пропущен: в БД уже есть лица ({existing}). "
                  f"Для принудительной загрузки: python manage.py ingest --force")
            return
        summary = discover_and_load_all(db, settings.data_dir)
        for s in summary:
            print(f"  {s['file']}: принято {s['accepted']}, отклонено {s['rejected']}")
        n = recompute_all(db)
        print(f"Риск-скоринг пересчитан для {n} лиц.")
    finally:
        db.close()


def cmd_recompute():
    db = SessionLocal()
    try:
        print(f"Пересчитано: {recompute_all(db)} лиц.")
    finally:
        db.close()


def cmd_reembed():
    from app.legal.embeddings import using_local_model

    db = SessionLocal()
    try:
        n = reembed_legal(db)
        mode = "локальная модель" if using_local_model() else "офлайн-хеш (модель недоступна!)"
        print(f"Переэмбеддинг норм: {n}. Движок: {mode}.")
    finally:
        db.close()


def cmd_ingest_codes():
    from app.legal.code_ingest import ingest_all

    doc_ids = sys.argv[2:] or None
    db = SessionLocal()
    try:
        results = ingest_all(db, doc_ids)
        total = 0
        for r in results:
            if r.get("error"):
                print(f"  [ОШИБКА] {r['code']} ({r['doc_id']}): {r['error']}")
            else:
                total += r["added"]
                print(f"  {r['code']}: статей {r['parsed']}, добавлено {r['added']}")
        print(f"Итого добавлено норм: {total}")
    finally:
        db.close()
    cmd_legal_index()


def cmd_tag_norms():
    from app.legal.code_ingest import tag_existing_norms

    db = SessionLocal()
    try:
        n = tag_existing_norms(db)
        print(f"Обновлено норм (авто-теги): {n}")
    finally:
        db.close()


def cmd_link_norms():
    from app.legal.links import link_cases_to_norms

    db = SessionLocal()
    try:
        result = link_cases_to_norms(db)
        print(f"Связано дел с нормами: {result}")
    finally:
        db.close()


def cmd_data_quality():
    from app.etl.quality import data_quality_report, district_completeness

    db = SessionLocal()
    try:
        report = data_quality_report(db)
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        print("\nРайоны с пропусками дат:")
        for row in district_completeness(db):
            print(f"  {row['district']}: {row['missing_date_pct']}% ({row['missing_date']}/{row['cases']})")
    finally:
        db.close()


def cmd_legal_index():
    from sqlalchemy import text

    from app.core.db import SessionLocal as SL

    db = SL()
    try:
        db.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_legal_norms_embedding "
            "ON legal_norms USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        ))
        db.execute(text("ANALYZE legal_norms"))
        db.commit()
        print("Векторный индекс ivfflat по legal_norms.embedding готов.")
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Не удалось создать индекс: {exc}")
    finally:
        db.close()


COMMANDS = {
    "init": cmd_init,
    "seed-legal": cmd_seed_legal,
    "seed-entitlements": cmd_seed_entitlements,
    "import-registry-mkb": cmd_import_registry_mkb,
    "download-legal-docs": cmd_download_legal_docs,
    "ingest": cmd_ingest,
    "recompute": cmd_recompute,
    "reembed": cmd_reembed,
    "ingest-codes": cmd_ingest_codes,
    "tag-norms": cmd_tag_norms,
    "link-norms": cmd_link_norms,
    "data-quality": cmd_data_quality,
    "legal-index": cmd_legal_index,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS and sys.argv[1] != "all":
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "all":
        cmd_init()
        cmd_seed_legal()
        cmd_seed_entitlements()
        cmd_ingest()
    else:
        COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
