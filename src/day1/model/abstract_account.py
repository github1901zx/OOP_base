"""
Абстрактная модель банковского счёта.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class AccountStatus(Enum):
    """Статусы счёта."""
    ACTIVE = "active"      # активный
    FROZEN = "frozen"      # замороженный
    CLOSED = "closed"      # закрытый


class Currency(Enum):
    """Поддерживаемые валюты."""
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


@dataclass
class Owner:
    """Простая модель владельца счёта."""
    name: str
    email: str


class AbstractAccount(ABC):
    """
    Абстрактный банковский счёт.
    Содержит идентификатор, владельца, защищённый баланс и статус.
    """

    def __init__(self, account_id: str, owner: Owner, balance: float = 0.0,
                 status: AccountStatus = AccountStatus.ACTIVE, currency: Currency = Currency.RUB) -> None:
        # Уникальный идентификатор счёта (строка)
        self.id: str = account_id
        # Данные владельца
        self.owner: Owner = owner
        # Защищённый баланс (начальное значение >= 0)
        self._balance: float = float(balance) if balance is not None else 0.0
        if self._balance < 0:
            self._balance = 0.0
        # Статус счёта
        self.status: AccountStatus = status
        # Валюта счёта
        self.currency: Currency = currency

    # Абстрактные методы операций
    @abstractmethod
    def deposit(self, amount: float) -> None:
        """Пополнение счёта на указанную сумму."""

    @abstractmethod
    def withdraw(self, amount: float) -> None:
        """Снятие со счёта указанной суммы."""

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Возвращает словарь с информацией о счёте."""

    # toString
    def __str__(self) -> str:
        # Тип счёта — имя класса
        account_type = self.__class__.__name__
        # Имя клиента
        client = self.owner.name if self.owner else "Unknown"
        # Последние 4 символа идентификатора
        last4 = str(self.id)[-4:] if self.id else "????"
        # Статус
        status = self.status.value if isinstance(self.status, AccountStatus) else str(self.status)
        # Баланс и валюта
        cur = self.currency.value if isinstance(self.currency, Currency) else str(self.currency)
        return f"{account_type} | {client} | ****{last4} | {status} | {self._balance:.2f} {cur}"
