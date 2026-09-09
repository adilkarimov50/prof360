"""Безопасность ИИ: защита от prompt-injection и фильтрация персональных данных."""
import re

INJECTION_PATTERNS = [
    r"ignore (all |the )?(previous|above) instructions",
    r"игнорируй (все |предыдущие )?(инструкции|указания)",
    r"forget (your|all) (rules|instructions)",
    r"ты больше не",
    r"system prompt",
    r"reveal (your )?(system )?prompt",
    r"раскрой системный промпт",
]

IIN_RE = re.compile(r"\b\d{12}\b")
PHONE_RE = re.compile(r"\+?7?\s*\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}")


def detect_injection(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in INJECTION_PATTERNS)


def sanitize_context(text: str) -> str:
    """Удаляет потенциальные инструкции из загруженного контента (документов/фабул)."""
    cleaned = text
    for p in INJECTION_PATTERNS:
        cleaned = re.sub(p, "[removed]", cleaned, flags=re.IGNORECASE)
    return cleaned


def redact_pii(text: str, allow: bool) -> str:
    """Маскирует ИИН и телефоны в ответе, если у пользователя нет права на ПДн."""
    if allow:
        return text
    text = IIN_RE.sub(lambda m: "*" * 8 + m.group()[-4:], text)
    text = PHONE_RE.sub("[телефон скрыт]", text)
    return text


# --- Токенизация ПДн для безопасной отправки во внешний ИИ (Gemini) ---
# ФИО: фамилия + инициалы или полное ФИО (кириллица). Покрывает форматы эталона.
FIO_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,2}\b"
    r"|\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?\b"
)
ERDR_RE = re.compile(r"\b\d{15,}\b")


def tokenize_pii(text: str) -> tuple[str, dict[str, str]]:
    """Заменяет ПДн (ФИО, ИИН, ЕРДР, телефоны) на обезличенные плейсхолдеры.

    Возвращает (обезличенный_текст, карта_замен). Карта хранится ЛОКАЛЬНО и
    используется для обратной подстановки после ответа модели. Во внешний ИИ
    уходит только обезличенный текст.
    """
    mapping: dict[str, str] = {}
    counters = {"ЛИЦО": 0, "ИИН": 0, "ЕРДР": 0, "ТЕЛ": 0}

    def repl(prefix: str):
        def _r(m: re.Match) -> str:
            val = m.group()
            for ph, orig in mapping.items():
                if orig == val:
                    return ph
            counters[prefix] += 1
            ph = f"[{prefix}_{counters[prefix]}]"
            mapping[ph] = val
            return ph
        return _r

    out = ERDR_RE.sub(repl("ЕРДР"), text)
    out = IIN_RE.sub(repl("ИИН"), out)
    out = PHONE_RE.sub(repl("ТЕЛ"), out)
    out = FIO_RE.sub(repl("ЛИЦО"), out)
    return out, mapping


def detokenize(text: str, mapping: dict[str, str]) -> str:
    """Восстанавливает реальные значения ПДн в ответе модели по карте замен."""
    for ph, orig in mapping.items():
        text = text.replace(ph, orig)
    return text
