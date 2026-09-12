# Профилактика 360 — монорепозиторий

Информационно-аналитическая система прокуратуры Алматинской области и цифровые криминологические паспорта населённых пунктов.

## Структура

```
backend/          FastAPI, PostgreSQL + pgvector, аналитика, отчёты
frontend/         React 18 + Mantine — рабочий кабинет прокурора
passports/        Статический сайт паспортов (GitHub Pages)
  data/           JSON паспортов и профилей 9 НП
  docs/           HTML/CSS/JS издания
  scripts/        build.py, digitize, fetch_locality_stats.py
.github/          CI и деплой Pages
```

**Репозиторий:** https://github.com/adilkarimov50/prof360  
**Публичный сайт паспортов:** https://adilkarimov50.github.io/krim-passport/  
**Служебный режим сайта:** добавьте `?staff=1` к URL (сохраняется в браузере).

## Быстрый старт (разработка)

```bash
cp .env.example .env   # GEMINI_API_KEY, JWT_SECRET и др.
docker compose up -d --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs
- Health: http://localhost:8000/health/ready
- Паспорта (локально): откройте `passports/docs/index.html` или `python -m http.server` в `passports/docs`

**Логины по умолчанию:** `admin` / `Prof360!admin`, `prokuror` / `Prof360!prok` — при первом входе система потребует смену пароля.

## Сборка данных паспортов

```bash
cd passports
python scripts/fetch_locality_stats.py   # обновить профили из manual_stats.csv
python scripts/build.py                # data/*.json → docs/assets/js/data.js
python scripts/build_legal.py          # backend TXT → docs/assets/legal/ + legal_data.js
```

**Нормативная библиотека на GitHub Pages:** вкладка «Прокурору» → «Работа с законами»
(`prokuror_zakon.html`) — 23 НПА, чтение TXT и ссылки на adilet.zan.kz.

## Production

```bash
cp .env.example .env
# ENVIRONMENT=production, сильные JWT_SECRET, FIELD_ENCRYPTION_KEY, IIN_HASH_PEPPER
docker compose -f docker-compose.prod.yml up -d --build
```

1. Сгенерируйте секреты (`openssl rand -hex 32` для JWT и pepper)
2. Смените пароли демо-учёток
3. Включите 2FA для администраторов
4. TLS перед nginx на VPS

Деплой сайта паспортов: push в `main` → GitHub Actions `deploy-pages.yml` публикует `passports/docs/`.

## API населённых пунктов

- `GET /api/localities` — список 9 НП с `locality_profile`
- `GET /api/localities/{id}` — профиль и статус паспорта (`full` / `profile_only`)

## Тесты

```bash
cd backend && pytest tests/ -q
cd frontend && npm test && npm run build
```

## Населённые пункты (9)

| id | Название | Статус данных |
|---|---|---|
| alatau | г. Алатау | обзорный профиль |
| konaev | г. Конаев | обзорный профиль |
| kaskelen | г. Каскелен | полный паспорт |
| talgar | г. Талгар | обзорный профиль |
| otegen_batyr | с. Отеген батыр | полный паспорт |
| irgeli | с. Иргели | полный паспорт |
| uzynagash | с. Узынагаш | обзорный профиль |
| chundzha | с. Чунджа | полный паспорт |
| issyk | г. Иссык | обзорный профиль |
