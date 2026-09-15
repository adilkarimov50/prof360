# Публикация дашбордов без персональных данных

Публичные HTML в `docs/` не должны содержать 12-значных ИИН и ФИО.

## Сборка

```bash
# Туран (нужен MongoDB scoring-db на localhost:27017)
backend/.venv/bin/python scripts/build_turan_dashboard.py

# ЦПС
backend/.venv/bin/python scripts/build_cps_spravka_dashboard.py

# Сверка ОВД (нужны Excel в «Карасайский район»)
cd passports && ../backend/.venv/bin/python scripts/crossmatch_registry.py
```

Оперативные версии с ИИН/ФИО: `passports/private/` (в git не попадает).

## История git krim-passport

Старые коммиты могли содержать ИИН в `registry_crossmatch.html` и `spravka_cps/spravka.html`.
Текущая версия на GitHub Pages — без них. Чтобы убрать данные из **истории** репозитория,
нужен переписанный history (например `git filter-repo`) и force-push — выполняйте осознанно
с бэкапом репозитория.
