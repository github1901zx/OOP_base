"""
InvestmentAccount — инвестиционный счёт с портфелем активов и прогнозом годового роста.
Комментарии на русском, код простой.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from src.day1.model.bank_account import BankAccount
from src.day1.model.abstract_account import AccountStatus, Currency, Owner
from src.day1.exeptions.exceptions import InvalidOperationError


class InvestmentAccount(BankAccount):
    """Инвестиционный счёт.
    - portfolio: распределение по активам (stocks, bonds, etf) в долях 0..1, сумма <= 1
    - project_yearly_growth(): прогнозирует баланс через год по простым средним ставкам
    """

    # Простейшие базовые ставки годовой доходности для типов активов
    DEFAULT_RATES: Dict[str, float] = {
        "stocks": 0.08,  # 8% годовых
        "bonds": 0.03,   # 3% годовых
        "etf": 0.06,     # 6% годовых
    }

    def __init__(
        self,
        owner: Owner,
        account_id: str | None = None,
        balance: float = 0.0,
        status: AccountStatus = AccountStatus.ACTIVE,
        currency: Currency = Currency.RUB,
        portfolio: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(owner=owner, account_id=account_id, balance=balance, status=status, currency=currency)
        # Устанавливаем портфель
        self.portfolio: Dict[str, float] = {
            "stocks": 0.0,
            "bonds": 0.0,
            "etf": 0.0,
        }
        if portfolio is not None:
            # Копируем только поддерживаемые ключи
            for k, v in portfolio.items():
                if k not in self.portfolio:
                    raise InvalidOperationError("Неизвестный тип актива в портфеле.")
                try:
                    val = float(v)
                except (TypeError, ValueError):
                    raise InvalidOperationError("Доля актива должна быть числом.")
                if val < 0:
                    raise InvalidOperationError("Доля актива не может быть отрицательной.")
                self.portfolio[k] = val
        # Проверяем сумму долей
        total = sum(self.portfolio.values())
        if total > 1.0 + 1e-9:
            raise InvalidOperationError("Сумма долей в портфеле не должна превышать 1.0.")

    def withdraw(self, amount: float) -> None:
        """Переопределяем для полиморфизма: правила как в базовом классе."""
        # В реальности могли бы продавать активы перед выводом.
        # Здесь просто используем поведение базового класса (без овердрафта).
        super().withdraw(amount)

    def get_account_info(self) -> Dict[str, Any]:
        info = super().get_account_info()
        info.update({
            "portfolio": dict(self.portfolio),
        })
        return info

    def project_yearly_growth(self, rates: Mapping[str, float] | None = None) -> float:
        """Возвращает прогнозный баланс через год по взвешенной доходности портфеля.
        rates — словарь ставок для ключей stocks/bonds/etf. Если не передан, берём DEFAULT_RATES.
        """
        if self.status != AccountStatus.ACTIVE:
            # Для простоты считаем, что роста нет в неактивном состоянии
            return self._balance
        rates_map = dict(self.DEFAULT_RATES)
        if rates:
            for k, v in rates.items():
                if k in rates_map:
                    try:
                        rates_map[k] = float(v)
                    except (TypeError, ValueError):
                        raise InvalidOperationError("Ставка должна быть числом.")
        # Считаем взвешенную ставку
        weighted_rate = 0.0
        for k, share in self.portfolio.items():
            weighted_rate += share * rates_map.get(k, 0.0)
        # Остаток (1 - сумма долей) считаем как кэш без доходности
        projected = self._balance * (1.0 + weighted_rate)
        return projected

    def __str__(self) -> str:
        base = super().__str__()
        s = self.portfolio.get("stocks", 0.0)
        b = self.portfolio.get("bonds", 0.0)
        e = self.portfolio.get("etf", 0.0)
        return f"{base} | portfolio: stocks={s:.2f}, bonds={b:.2f}, etf={e:.2f}"
