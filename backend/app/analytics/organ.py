"""Классификация органа, допустившего/ответственного за нарушение: полиция (ОВД) vs МИО.

В исходных данных орган указан текстом (`AdminCase.organ`, `AdminCase.subdivision`,
`PreventiveRecord.responsible`). Здесь распознаём по маркерам:
- police — органы внутренних дел (РОВД/РУВД/ДП/ГОВД/УИП/МПС/полиция);
- mio — местные исполнительные органы (акиматы, отделы образования/соцзащиты/
  здравоохранения, ЦОН, КДН, комиссии по делам несовершеннолетних);
- unknown — не распознано.
"""

POLICE_MARKERS = (
    "РОВД", "РУВД", "ГОВД", "ДП ", "ДЕПАРТАМЕНТ ПОЛИЦИИ", "ОТДЕЛ ПОЛИЦИИ",
    "УПРАВЛЕНИЕ ПОЛИЦИИ", "ПОЛИЦ", "УИП", "МПС", "ОВД", "ОАП", "АП ОАП",
)
MIO_MARKERS = (
    "АКИМАТ", "АКИМ", "МЕСТН", "ИСПОЛНИТЕЛЬН", "ОТДЕЛ ОБРАЗОВАН", "УПРАВЛЕНИЕ ОБРАЗОВАН",
    "СОЦЗАЩИТ", "СОЦИАЛЬН", "ЗДРАВООХРАН", "ЦОН", "КДН", "КОМИССИ ПО ДЕЛАМ",
    "ОБРАЗОВАНИЯ", "ЗАНЯТОСТ", "ОПЕК",
)

# Категории профилактического учёта, ответственность за социальную профилактику
# по которым относится в т.ч. к МИО (несовершеннолетние, социально уязвимые).
MIO_PREVENTIVE_MARKERS = (
    "НЕСОВЕРШЕННОЛЕТ", "ФОРМА 205", "ОПЕК", "СОЦИАЛЬН", "БЕЗ ПОПЕЧЕН",
)


def classify_organ(organ: str | None, subdivision: str | None = None) -> str:
    """Возвращает 'police' | 'mio' | 'unknown' по тексту органа/подразделения."""
    blob = " ".join(filter(None, [organ, subdivision])).upper()
    if not blob.strip():
        return "unknown"
    if any(m in blob for m in MIO_MARKERS):
        return "mio"
    if any(m in blob for m in POLICE_MARKERS):
        return "police"
    return "unknown"


def is_mio_preventive(category: str | None) -> bool:
    """Признак, что категория профучёта относится к зоне ответственности МИО."""
    if not category:
        return False
    up = str(category).upper()
    return any(m in up for m in MIO_PREVENTIVE_MARKERS)


def case_line(case) -> str:
    """Линия ответственности по административному делу (police/mio/unknown)."""
    return classify_organ(getattr(case, "organ", None), getattr(case, "subdivision", None))
