"""Реестр кодексов и ключевых НПА РК для авто-загрузки с adilet.zan.kz."""

ADILET = "https://adilet.zan.kz"


def docx_url(doc_id: str) -> str:
    return f"{ADILET}/rus/docs/{doc_id}/download/docx"


def doc_url(doc_id: str) -> str:
    return f"{ADILET}/rus/docs/{doc_id}"


# parse_mode: article — «Статья N»; point — нумерованные пункты (приказы/правила)
CODES: list[dict] = [
    {"title": "Уголовный кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "226-V", "doc_id": "K1400000226", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Уголовно-процессуальный кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "231-V", "doc_id": "K1400000231", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Уголовно-исполнительный кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "234-V", "doc_id": "K1400000234", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Кодекс Республики Казахстан об административных правонарушениях", "act_type": "кодекс",
     "number": "235-V", "doc_id": "K1400000235", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Кодекс Республики Казахстан о браке (супружестве) и семье", "act_type": "кодекс",
     "number": "518-IV", "doc_id": "K1100000518", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Гражданский процессуальный кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "377-V", "doc_id": "K1500000377", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Налоговый кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "120-VI", "doc_id": "K1700000120", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Трудовой кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "414-V", "doc_id": "K1500000414", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Предпринимательский кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "375-V", "doc_id": "K1500000375", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Социальный кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "224-VII", "doc_id": "K2300000224", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Экологический кодекс Республики Казахстан", "act_type": "кодекс",
     "number": "400-VI", "doc_id": "K2100000400", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Кодекс Республики Казахстан о здоровье народа и системе здравоохранения",
     "act_type": "кодекс", "number": "360-VI", "doc_id": "K2000000360", "hierarchy_level": 2,
     "parse_mode": "article"},
    {"title": "Административный процедурно-процессуальный кодекс Республики Казахстан",
     "act_type": "кодекс", "number": "350-VI", "doc_id": "K2000000350", "hierarchy_level": 2,
     "parse_mode": "article"},
    {"title": "Закон Республики Казахстан «О профилактике правонарушений»", "act_type": "закон",
     "number": "245-VIII", "doc_id": "Z2500000245", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Конституционный закон Республики Казахстан «О прокуратуре»", "act_type": "конституционный закон",
     "number": "155-VII", "doc_id": "Z2200000155", "hierarchy_level": 2, "parse_mode": "article"},
    {"title": "Закон Республики Казахстан «Об органах внутренних дел»", "act_type": "закон",
     "number": "240-VII", "doc_id": "Z1400000251", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Закон РК «О персональных данных и их защите»", "act_type": "закон",
     "number": "94-V", "doc_id": "Z1300000094", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Приказ Генерального Прокурора РК «О некоторых вопросах организации прокурорского надзора»",
     "act_type": "приказ", "number": "32", "doc_id": "V2300031753", "hierarchy_level": 4,
     "parse_mode": "point"},
    {"title": "Приказ МВД РК «Об утверждении положений о ведомствах и территориальных органах МВД»",
     "act_type": "приказ", "number": "662", "doc_id": "V14C0009792", "hierarchy_level": 4,
     "parse_mode": "point"},
    {"title": "Приказ МВД РК «О внесении изменения в приказ №662 (Комитет координации профилактики)»",
     "act_type": "приказ", "number": "1008", "doc_id": "G25C0001008", "hierarchy_level": 4,
     "parse_mode": "point"},
    {"title": "Приказ МВД РК «Правила ведения профилактического учёта и профилактического контроля»",
     "act_type": "приказ", "number": "163", "doc_id": "V2600038111", "hierarchy_level": 4,
     "parse_mode": "point"},
    {"title": "Приказ Минздрава РК №814 — учёт алкоголизма и наркомании (утратил силу, см. ДСМ-203/2020)",
     "act_type": "приказ", "number": "814", "doc_id": "V090005954_", "hierarchy_level": 4,
     "parse_mode": "point", "superseded_by": "V2000021680"},
    {"title": "Приказ Минздрава РК «О медико-социальной помощи в области психического здоровья»",
     "act_type": "приказ", "number": "ҚР ДСМ-203/2020", "doc_id": "V2000021680", "hierarchy_level": 4,
     "parse_mode": "point"},
    {"title": "Закон РК «О наркотических средствах, психотропных веществах и прекурсорах»",
     "act_type": "закон", "number": "279", "doc_id": "Z980000279_", "hierarchy_level": 3,
     "parse_mode": "article"},
    {"title": "Закон РК «Об образовании»", "act_type": "закон", "number": "319-III",
     "doc_id": "Z070000319_", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Закон РК «О местном государственном управлении и самоуправлении»",
     "act_type": "закон", "number": "510-V", "doc_id": "Z1100000510", "hierarchy_level": 3,
     "parse_mode": "article"},
    {"title": "Закон РК «О государственной молодежной политике»", "act_type": "закон",
     "number": "285-V", "doc_id": "Z1500000285", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Закон РК «О противодействии торговле людьми»", "act_type": "закон",
     "number": "101-V", "doc_id": "Z1300000101", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Закон РК «О противодействии терроризму»", "act_type": "закон",
     "number": "416-I", "doc_id": "Z990000416_", "hierarchy_level": 3, "parse_mode": "article"},
    {"title": "Приказ Минздрава РК «Правила медосвидетельствования на опьянение»",
     "act_type": "приказ", "number": "ҚР ДСМ-151/2017", "doc_id": "V1700015519",
     "hierarchy_level": 4, "parse_mode": "point"},
]

CODES_BY_DOC_ID = {c["doc_id"]: c for c in CODES}
ACTS = CODES  # alias
