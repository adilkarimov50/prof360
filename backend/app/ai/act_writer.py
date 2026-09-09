"""ИИ-генерация прокурорских актов реагирования (Приказ ГП РК №32).

Генерирует грамотный развёрнутый юридический текст акта на основе фактов лица/дела,
рекомендованных мер и релевантных норм. ПДн токенизируются перед отправкой во внешний
LLM и восстанавливаются локально. При недоступности ИИ — детерминированный шаблон.
"""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.guard import detokenize, tokenize_pii
from app.analytics.scoring import compute_person_factors
from app.legal.search import hybrid_search
from app.models.person import AdminCase, Person
from app.prosecutor.measures import APPEAL_TERM_DAYS, recommend_measures

SYSTEM_PROMPT = (
    "Ты — старший помощник прокурора, готовящий проекты актов прокурорского реагирования "
    "службы по защите общественных интересов прокуратуры Алматинской области. Пиши строго "
    "официально-деловым юридическим языком, грамотно и развёрнуто. Используй ТОЛЬКО переданные "
    "факты, цифры и нормы — ничего не выдумывай (не придумывай номера, даты, суммы). НЕ признавай "
    "лицо виновным и не подменяй решения суда/следователя. Сохраняй плейсхолдеры вида [ЛИЦО_1], "
    "[ИИН_1], [ЕРДР_1] без изменений. Опирайся на нормы: ст.54, ст.73, ст.461 КоАП РК, ст.107-109 УК РК, "
    "Закон РК «О профилактике правонарушений» №245-VIII (ст.18, 58, 72), Приказ ГП РК №32 от 17.01.2023, "
    "Конституционный закон РК «О прокуратуре»."
)

# Метаданные актов: заголовок, адресат, резолютивный глагол, структура.
ACTS: dict[str, dict] = {
    "representation": {
        "title": "ПРЕДСТАВЛЕНИЕ об устранении нарушений законности",
        "addressee": "Начальнику Департамента полиции Алматинской области",
        "verb": "ТРЕБУЮ",
        "structure": (
            "Структура: 1) вводная (кем и что изучено); 2) установочная (выявленные нарушения "
            "законности профилактической работы с конкретными фактами и цифрами); 3) мотивировочная "
            "(нормы права, которые нарушены/подлежат применению, причины и условия нарушений); "
            "4) резолютивная «ТРЕБУЮ» (рассмотреть представление с участием прокурора; устранить "
            "нарушения; поставить лицо на профилактический учёт и провести индивидуальную "
            "профилактическую работу; рассмотреть вопрос об ответственности виновных должностных лиц; "
            "о результатах сообщить прокурору в установленный срок)."
        ),
    },
    "protest": {
        "title": "ПРОТЕСТ на постановление по делу об административном правонарушении",
        "addressee": "Начальнику органа (должностному лицу), вынесшему постановление",
        "verb": "ПРОШУ",
        "structure": (
            "Структура: 1) вводная (какое постановление изучено — номер, дата, лицо, квалификация); "
            "2) установочная (принятое решение/мера); 3) мотивировочная (основания незаконности/"
            "необоснованности: необоснованное прекращение или занижение квалификации семейно-бытового "
            "состава, несоразмерно мягкая мера; ссылки на нормы); 4) резолютивная «ПРОШУ» (отменить "
            "незаконное постановление, направить на новое рассмотрение/принять законное решение; "
            "рассмотреть вопрос о приостановлении исполнения до рассмотрения протеста)."
        ),
    },
    "appeal": {
        "title": "АПЕЛЛЯЦИОННОЕ ХОДАТАЙСТВО",
        "addressee": "В суд апелляционной инстанции",
        "verb": "ПРОШУ",
        "structure": (
            "Структура: 1) вводная (на какой судебный акт — номер, дата, лицо, квалификация, срок "
            "обжалования по КоАП — 10 суток и дата истечения); 2) мотивировочная (доводы: неполнота "
            "исследования обстоятельств, неправильная квалификация, несоразмерность меры; нормы); "
            "3) резолютивная «ПРОШУ» (судебный акт изменить/отменить, вынести законное и обоснованное "
            "решение)."
        ),
    },
    "requirement": {
        "title": "ТРЕБОВАНИЕ (УКАЗАНИЕ) прокурора",
        "addressee": "Начальнику территориального органа внутренних дел",
        "verb": "ТРЕБУЮ",
        "structure": (
            "Структура: 1) вводная (в порядке надзора за законностью профилактической работы); "
            "2) установочная (что установлено по лицу); 3) мотивировочная (нормы Закона №245-VIII, "
            "Приказа №32); 4) резолютивная «ТРЕБУЮ» (решить вопрос о постановке на профилактический "
            "учёт; обеспечить индивидуальную профилактическую работу и контроль; усилить "
            "взаимодействие с органами социальной защиты, образования, здравоохранения; письменно "
            "уведомить прокурора о принятых мерах). Указать на ответственность за невыполнение "
            "законных требований прокурора."
        ),
    },
}

_QUERY = {
    "representation": "нарушения законности профилактическая работа профилактический учёт представление бездействие",
    "protest": "незаконное постановление административное правонарушение прекращение протест семейно-бытовое",
    "appeal": "обжалование судебного акта апелляционное ходатайство срок обжалования КоАП",
    "requirement": "постановка на профилактический учёт индивидуальная профилактика требование прокурора",
}


def _person_facts(person: Person) -> str:
    score, factors, signals = compute_person_factors(person)
    lines = [
        f"Лицо: {person.fio}; район: {person.district or '—'}; дата рождения: {person.birth_date or '—'}.",
        f"Уровень риска: {person.risk_level} ({score} баллов).",
        f"Административных дел всего: {len(person.admin_cases)}.",
    ]
    cases = sorted(person.admin_cases, key=lambda x: x.case_date or date.min)
    for c in cases[:12]:
        lines.append(
            f"- {c.case_date or '—'}: {c.qualification or '—'}; решение: {c.decision or '—'}; "
            f"мера: {c.measure or 'не указана'}; материал № {c.material_no or '—'}."
        )
    if person.preventive_records:
        lines.append("Профилактический учёт:")
        for p in person.preventive_records:
            lines.append(
                f"- {p.category or p.form or '—'}: с {p.date_post or '—'} по {p.date_removed or 'наст. время'}."
            )
    if person.suspects:
        lines.append("Сведения ЕРДР (признан подозреваемым):")
        for s in person.suspects:
            lines.append(f"- ЕРДР № {s.erdr_no or '—'} ({s.erdr_year or '—'} г.): {s.qualification or '—'}, {s.gravity or '—'}.")
    if signals:
        lines.append("Автоматические сигналы системы:")
        for s in signals:
            lines.append(f"- [{s['level']}] {s['message']}")
    return "\n".join(lines)


def _measures_facts(person: Person) -> str:
    lines = ["Рекомендованные акты реагирования (Приказ ГП РК №32):"]
    for m in recommend_measures(person):
        mark = "применимо" if m["applicable"] else "не требуется"
        lines.append(f"- [{mark}] {m['title']}: {m['reason']} (основание: {', '.join(m['legal_basis'])}).")
    return "\n".join(lines)


def _case_facts(person: Person, case: AdminCase | None, kind: str) -> str:
    if not case:
        return ""
    lines = [
        f"Оспариваемый материал: № {case.material_no or '—'} от {case.case_date or '—'}; "
        f"квалификация: {case.qualification or '—'}; решение: {case.decision or '—'}; "
        f"мера: {case.measure or 'не указана'}; орган: {case.organ or '—'}."
    ]
    if kind == "appeal" and case.case_date:
        deadline = case.case_date + timedelta(days=APPEAL_TERM_DAYS)
        lines.append(f"Срок обжалования (КоАП — {APPEAL_TERM_DAYS} суток) истекает: {deadline}.")
    return "\n".join(lines)


def _norms_facts(db: Session, kind: str) -> str:
    results = hybrid_search(db, _QUERY.get(kind, ""), limit=5)
    if not results:
        return ""
    lines = ["Релевантные нормы права:"]
    for r in results:
        norm = r["norm"]
        act = norm.act.title if norm.act else ""
        lines.append(f"- {act}, {norm.article or ''}: {norm.text_ru or ''}")
    return "\n".join(lines)


def write_act(db: Session, kind: str, person: Person, case: AdminCase | None = None
              ) -> tuple[str, bool]:
    """Возвращает (текст_акта, использован_ли_LLM)."""
    meta = ACTS.get(kind)
    if not meta:
        return "", False

    facts = "\n\n".join(filter(None, [
        _person_facts(person),
        _case_facts(person, case, kind),
        _measures_facts(person),
        _norms_facts(db, kind),
    ]))

    external = llm.provider() == "gemini"
    sent_facts, pii_map = (tokenize_pii(facts) if external else (facts, {}))
    prompt = (
        f"Подготовь проект акта прокурорского реагирования: «{meta['title']}».\n"
        f"Адресат: {meta['addressee']}.\n"
        f"{meta['structure']}\n"
        f"Резолютивную часть начни словом «{meta['verb']}». Объём — развёрнутый, 4-8 содержательных "
        f"абзацев, без таблиц. Не повторяй адресата и заголовок в теле (они будут добавлены отдельно).\n\n"
        f"ФАКТЫ ПО ДЕЛУ:\n{sent_facts}\n"
    )
    answer = llm.generate(prompt, system=SYSTEM_PROMPT, temperature=0.35)
    if answer and external and pii_map:
        answer = detokenize(answer, pii_map)
    if answer:
        return answer.strip(), True
    return _fallback(kind, person, case, meta), False


def _fallback(kind: str, person: Person, case: AdminCase | None, meta: dict) -> str:
    """Детерминированный текст акта, если ИИ недоступен."""
    score, _, signals = compute_person_factors(person)
    measures = {m["type"]: m for m in recommend_measures(person)}
    head = (
        f"Прокуратурой Алматинской области в порядке надзора изучена профилактическая работа "
        f"в отношении {person.fio} (район: {person.district or '—'}). Установлено следующее."
    )
    sig = "\n".join(f"• {s['message']}" for s in signals) or "• существенных автоматических сигналов не зафиксировано."
    if kind == "representation":
        body = (
            f"{head}\n\n{measures.get('representation',{}).get('reason','')}\n{sig}\n\n"
            f"Количество административных правонарушений лица: {len(person.admin_cases)}; "
            f"уровень риска: {person.risk_level} ({score} баллов).\n\n"
            f"{meta['verb']}:\n"
            "1. Безотлагательно рассмотреть настоящее представление с участием прокурора.\n"
            "2. Принять меры к устранению нарушений законности и способствующих им условий.\n"
            "3. Решить вопрос о постановке лица на профилактический учёт и проведении индивидуальной "
            "профилактической работы.\n"
            "4. Рассмотреть вопрос об ответственности виновных должностных лиц.\n"
            "5. О результатах сообщить прокурору в установленный законом срок."
        )
    elif kind == "protest":
        cinfo = (f"материал № {case.material_no or '—'} от {case.case_date or '—'}, квалификация "
                 f"{case.qualification or '—'}, решение {case.decision or '—'}." if case
                 else "материалы административной практики.")
        body = (
            f"Изучено постановление: {cinfo}\n\n"
            "Постановление вынесено с нарушением требований законности (необоснованное прекращение/"
            "возврат материала либо занижение квалификации семейно-бытового состава и назначение "
            "несоразмерно мягкой меры).\n\n"
            f"{meta['verb']}:\nОтменить незаконное постановление и направить дело на новое рассмотрение "
            "либо принять законное решение; до рассмотрения протеста рассмотреть вопрос о "
            "приостановлении исполнения опротестованного акта."
        )
    elif kind == "appeal":
        deadline = (case.case_date + timedelta(days=APPEAL_TERM_DAYS)) if (case and case.case_date) else None
        cinfo = (f"судебный акт по материалу № {case.material_no or '—'} от {case.case_date or '—'} "
                 f"(квалификация {case.qualification or '—'}); срок обжалования истекает {deadline or '—'}."
                 if case else "судебный акт по материалам дела.")
        body = (
            f"Обжалуется {cinfo}\n\n"
            "Судебный акт подлежит пересмотру ввиду неполноты исследования обстоятельств, "
            "неправильной квалификации либо несоответствия назначенной меры характеру правонарушения.\n\n"
            f"{meta['verb']}:\nСудебный акт изменить/отменить и вынести законное и обоснованное решение."
        )
    else:  # requirement
        body = (
            f"{head}\n\n{measures.get('requirement',{}).get('reason','')}\n\n"
            f"{meta['verb']}:\n"
            "1. Решить вопрос о постановке лица на профилактический учёт при наличии оснований.\n"
            "2. Обеспечить индивидуальную профилактическую работу и контроль за поведением лица.\n"
            "3. Усилить взаимодействие с органами социальной защиты, образования и здравоохранения.\n"
            "4. О принятых мерах письменно уведомить прокурора.\n\n"
            "Невыполнение законных требований прокурора влечёт ответственность по законодательству РК."
        )
    return body
