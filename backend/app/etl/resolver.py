"""Сопоставление и дедупликация лиц (Entity Resolution) при загрузке."""
from datetime import date

from sqlalchemy.orm import Session

from app.core.crypto import encrypt, iin_hash
from app.models.person import Person


class PersonResolver:
    """Находит существующее лицо или создаёт новое. Кэширует в рамках загрузки."""

    def __init__(self, db: Session):
        self.db = db
        self._by_iin: dict[str, int] = {}
        self._by_name: dict[str, int] = {}

    @staticmethod
    def _name_key(last: str, first: str, patr: str, dob: date | None) -> str:
        return f"{last}|{first}|{patr}|{dob.isoformat() if dob else ''}".upper()

    def resolve(
        self,
        *,
        iin: str | None,
        last_name: str = "",
        first_name: str = "",
        patronymic: str = "",
        birth_date: date | None = None,
        gender: str | None = None,
        district: str | None = None,
        locality: str | None = None,
        address: str | None = None,
        phone: str | None = None,
    ) -> Person:
        ih = iin_hash(iin)
        if ih and ih in self._by_iin:
            return self.db.get(Person, self._by_iin[ih])

        name_key = self._name_key(last_name, first_name, patronymic, birth_date)

        person: Person | None = None
        if ih:
            person = self.db.query(Person).filter(Person.iin_hash == ih).first()
        if person is None and not ih and (last_name or first_name):
            if name_key in self._by_name:
                return self.db.get(Person, self._by_name[name_key])
            person = (
                self.db.query(Person)
                .filter(
                    Person.iin_hash.is_(None),
                    Person.last_name == last_name,
                    Person.first_name == first_name,
                    Person.birth_date == birth_date,
                )
                .first()
            )

        if person is None:
            person = Person(
                iin_enc=encrypt(iin) if iin else None,
                iin_hash=ih,
                last_name=last_name,
                first_name=first_name,
                patronymic=patronymic,
                birth_date=birth_date,
                gender=gender,
                district=district,
                locality=locality,
                address_enc=encrypt(address) if address else None,
                phone_enc=encrypt(phone) if phone else None,
            )
            self.db.add(person)
            self.db.flush()
        else:
            # дополняем недостающие поля
            if not person.district and district:
                person.district = district
            if not person.birth_date and birth_date:
                person.birth_date = birth_date

        if ih:
            self._by_iin[ih] = person.id
        else:
            self._by_name[name_key] = person.id
        return person
