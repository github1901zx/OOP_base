"""
PremiumAccount — премиальный счёт с овердрафтом и фиксированной комиссией на снятие.
"""
from __future__ import annotations

from typing import Any, Dict

from src.day1.model.bank_account import BankAccount
from src.day1.model.abstract_account import AccountStatus, Currency, Owner
from src.day1.exeptions.exceptions import InvalidOperationError, InsufficientFundsError


class PremiumAccount(BankAccount):
    """Премиальный счёт.
    - overdraft_limit — разрешённый овердрафт (на сколько можно уйти в минус)
    - withdraw_fee_fixed — фиксированная комиссия за каждое снятие
    """

    def __init__(
        self,
        owner: Owner,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
        overdraft_limit: float = 0.0,
        withdraw_fee_fixed: float = 0.0,
    ) -> None:
        super().__init__(owner=owner, account_id=account_id, balance=balance, status=status, currency=currency)
        # Валидация лимита овердрафта
        try:
            self.overdraft_limit = float(overdraft_limit)
        except (TypeError, ValueError):
            raise InvalidOperationError("overdraft_limit должен быть числом.")
        if self.overdraft_limit < 0:
            raise InvalidOperationError("overdraft_limit не может быть отрицательным.")
        # Валидация фиксированной комиссии
        try:
            self.withdraw_fee_fixed = float(withdraw_fee_fixed)
        except (TypeError, ValueError):
            raise InvalidOperationError("withdraw_fee_fixed должен быть числом.")
        if self.withdraw_fee_fixed < 0:
            raise InvalidOperationError("withdraw_fee_fixed не может быть отрицательной.")

    def withdraw(self, amount: float) -> None:
        """Снятие: разрешаем уходить в минус в пределах overdraft_limit.
        Комиссия списывается дополнительно к сумме.
        """
        self._ensure_active()
        value = self._validate_amount(amount)
        total_debit = value + self.withdraw_fee_fixed
        # Проверяем, что после списания баланс не меньше допустимого (минус лимит)
        if self._balance - total_debit < -self.overdraft_limit:
            raise InsufficientFundsError("Превышен лимит овердрафта.")
        self._balance -= total_debit

    def get_account_info(self) -> Dict[str, Any]:
        info = super().get_account_info()
        info.update({
            "overdraft_limit": self.overdraft_limit,
            "withdraw_fee_fixed": self.withdraw_fee_fixed,
        })
        return info

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} | overdraft={self.overdraft_limit:.2f} | fee={self.withdraw_fee_fixed:.2f}"
