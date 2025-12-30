from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ClientStatus(Enum):
    """Статус клиента."""
    ACTIVE = "active"   # активный
    BLOCKED = "blocked" # заблокирован (например, за неудачные попытки входа)


@dataclass
class Client:
    """Модель клиента банка.

    Атрибуты:
      - full_name: ФИО
      - client_id: уникальный идентификатор клиента
      - age: возраст (должен быть >= 18)
      - contacts: контакты (телефон, email и т.п.)
      - status: статус клиента
      - accounts: список номеров (id) его счетов
      - suspicious: пометка о подозрительной активности
    """
    full_name: str
    client_id: str
    age: int
    contacts: Dict[str, str] = field(default_factory=dict)
    status: ClientStatus = ClientStatus.ACTIVE
    accounts: List[str] = field(default_factory=list)
    suspicious: bool = False

    def __post_init__(self) -> None:
        # Проверка возраста
        if int(self.age) < 18:
            raise ValueError("Клиент должен быть старше или равен 18 лет.")

    def add_account(self, account_id: str) -> None:
        """Добавить номер счёта клиенту (без дублей)."""
        if account_id not in self.accounts:
            self.accounts.append(account_id)

    def remove_account(self, account_id: str) -> None:
        """Удалить номер счёта клиента, если он есть."""
        if account_id in self.accounts:
            self.accounts.remove(account_id)

    def mark_suspicious(self) -> None:
        """Пометить клиента как подозрительного."""
        self.suspicious = True
