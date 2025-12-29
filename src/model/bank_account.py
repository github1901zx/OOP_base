"""
Простая реализация банковского счёта на базе AbstractAccount.
Комментарии на русском, код максимально простой.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

from src.model.abstract_account import AbstractAccount, AccountStatus, Currency, Owner
from src.exeptions.exceptions import (
    AccountClosedError,
    AccountFrozenError,
    InvalidOperationError,
    InsufficientFundsError,
)


class BankAccount(AbstractAccount):
    """Конкретный тип банковского счёта."""

    def __init__(
        self,
        owner: Owner,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
    ) -> None:
        # Если номер счёта не передали — генерируем короткий UUID (8 символов)
        if not account_id:
            account_id = uuid.uuid4().hex[:8]
        # Инициализируем базовый класс
        super().__init__(account_id=account_id, owner=owner, balance=balance, status=status, currency=currency)
        # Простейшая валидация входных данных
        if not isinstance(self.status, AccountStatus):
            raise InvalidOperationError("Некорректный статус счёта.")
        if not isinstance(self.currency, Currency):
            raise InvalidOperationError("Некорректная валюта счёта.")

    # Вспомогательная проверка статуса
    def _ensure_active(self) -> None:
        if self.status == AccountStatus.FROZEN:
            raise AccountFrozenError("Счёт заморожен. Операция запрещена.")
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError("Счёт закрыт. Операция запрещена.")

    # Вспомогательная проверка суммы
    @staticmethod
    def _validate_amount(amount: float) -> float:
        try:
            value = float(amount)
        except (TypeError, ValueError):
            raise InvalidOperationError("Сумма должна быть числом.")
        if value <= 0:
            raise InvalidOperationError("Сумма должна быть положительной и больше нуля.")
        return value

    def deposit(self, amount: float) -> None:
        """Пополнение счёта."""
        self._ensure_active()
        value = self._validate_amount(amount)
        self._balance += value

    def withdraw(self, amount: float) -> None:
        """Снятие со счёта."""
        self._ensure_active()
        value = self._validate_amount(amount)
        if value > self._balance:
            raise InsufficientFundsError("Недостаточно средств.")
        self._balance -= value

    def get_account_info(self) -> Dict[str, Any]:
        """Возвращает простую информацию о счёте."""
        return {
            "id": self.id,
            "owner": self.owner.name,
            "status": self.status.value,
            "balance": self._balance,
            "currency": self.currency.value,
        }
