"""
SavingsAccount — накопительный счёт с минимальным остатком и ежемесячной доходностью.
Комментарии на русском, код простой.
"""
from __future__ import annotations

from typing import Any, Dict

from src.day1.model.bank_account import BankAccount
from src.day1.model.abstract_account import AccountStatus, Currency, Owner
from src.day1.exeptions.exceptions import InvalidOperationError, InsufficientFundsError


class SavingsAccount(BankAccount):
    """Накопительный счёт.
    - min_balance — минимальный остаток (нельзя опускаться ниже него при снятии)
    - monthly_interest_rate — месячная ставка доходности (доля, например 0.01 = 1% в месяц)
    - apply_monthly_interest() — начисляет проценты на текущий баланс
    """

    def __init__(
        self,
        owner: Owner,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
        min_balance: float = 0.0,
        monthly_interest_rate: float = 0.0,
    ) -> None:
        super().__init__(owner=owner, account_id=account_id, balance=balance, status=status, currency=currency)
        # Валидация минимального остатка
        try:
            self.min_balance = float(min_balance)
        except (TypeError, ValueError):
            raise InvalidOperationError("min_balance должен быть числом.")
        if self.min_balance < 0:
            raise InvalidOperationError("min_balance не может быть отрицательным.")
        # Валидация процентной ставки (разрешаем 0 и положительные значения)
        try:
            self.monthly_interest_rate = float(monthly_interest_rate)
        except (TypeError, ValueError):
            raise InvalidOperationError("monthly_interest_rate должен быть числом.")
        if self.monthly_interest_rate < 0:
            raise InvalidOperationError("monthly_interest_rate не может быть отрицательным.")

    def withdraw(self, amount: float) -> None:
        """Снятие: нельзя опускаться ниже min_balance."""
        value = self._validate_amount(amount)
        # Проверка статуса как в базовом классе
        self._ensure_active()
        # Проверяем остаток после снятия
        if self._balance - value < self.min_balance:
            raise InsufficientFundsError("Нельзя опускаться ниже минимального остатка.")
        self._balance -= value

    def apply_monthly_interest(self) -> None:
        """Начисляем проценты на весь текущий баланс.
        Проценты не начисляются, если счёт заморожен или закрыт.
        """
        if self.status != AccountStatus.ACTIVE:
            return
        if self.monthly_interest_rate <= 0:
            return
        self._balance += self._balance * self.monthly_interest_rate

    def get_account_info(self) -> Dict[str, Any]:
        info = super().get_account_info()
        info.update({
            "min_balance": self.min_balance,
            "monthly_interest_rate": self.monthly_interest_rate,
        })
        return info

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} | min={self.min_balance:.2f} | rate={self.monthly_interest_rate:.4f}/m"
