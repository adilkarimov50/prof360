"""Нормализация значений: ИИН, ФИО, статьи КоАП/УК, даты, признаки риска."""
import re
from datetime import date, datetime

# Статьи КоАП, относящиеся к алкоголю/общественному порядку
ALC_ARTICLES = ("ст.200", "ст.440", "ст.440-1", "ст.435", "ст.461", "ст.482", "ст.128", "ст.131")
# Семейно-бытовые составы
SB_ARTICLES = ("ст.73", "ст.73-1", "ст.73-2")
# Насильственные составы УК (для эскалации)
CRIM_SB_VIOLENCE = ("ст.106", "ст.107", "ст.108", "ст.108-1", "ст.109", "ст.109-1", "ст.110")
# Маркеры особых требований к поведению (ст.54 КоАП)
SPECIAL_REQ_MARKERS = ("ОСОБЫЕ ТРЕБОВАНИЯ", "ЗАЩИТНОЕ ПРЕДПИСАНИЕ")
INTOXICATION_STATES = ("опьянен", "алкоголь", "алкогольн", "наркотическ")

# Темы повестки МВК по профилактике правонарушений (поиск в qualification/article)
# Интернет-мошенничество
CYBER_FRAUD_ARTICLES = ("ст.190", "ст.202", "ст.205")
CYBER_FRAUD_KEYWORDS = ("мошенни", "кибер", "интернет", "онлайн", "фишинг", "алаяқ")
# Вымогательство
EXTORTION_ARTICLES = ("ст.194",)
EXTORTION_KEYWORDS = ("вымогател", "бопсалау", "шантаж")
# Электронные сигареты / вейп
VAPE_ARTICLES = ("ст.301-1",)
VAPE_KEYWORDS = ("вейп", "электрон темекі", "электронные сигарет")
# Несовершеннолетние (категории профучёта)
JUVENILE_CATEGORIES = ("НЕСОВЕРШЕННОЛЕТН", "КӘМЕЛЕТКЕ ТОЛМАҒАН", "ПДН", "ЮП", "ҮОБП")


def norm(value) -> str:
    if value is None:
        return ""
    s = str(value).replace("_x000D_", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm_iin(value) -> str | None:
    """Возвращает 12-значный ИИН или None."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 12 and digits != "000000000000":
        return digits
    return None


def art_base(article: str | None) -> str:
    """Базовая статья без части: 'ст.73 ч.1' -> 'ст.73'."""
    if not article:
        return ""
    m = re.match(r"(ст\.\s*[\d\-]+)", str(article).replace(" ", ""))
    if m:
        return m.group(1).replace(" ", "")
    return norm(article)


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip().split(" ")[0]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def is_special_req(category: str | None) -> bool:
    if not category:
        return False
    up = str(category).upper()
    return any(m in up for m in SPECIAL_REQ_MARKERS)


def is_intoxicated(state: str | None) -> bool:
    if not state:
        return False
    low = str(state).lower()
    return any(m in low for m in INTOXICATION_STATES)


def erdr_year(erdr_no: str | None) -> int | None:
    if not erdr_no:
        return None
    m = re.match(r"(\d{2})", str(erdr_no).strip())
    return 2000 + int(m.group(1)) if m else None
