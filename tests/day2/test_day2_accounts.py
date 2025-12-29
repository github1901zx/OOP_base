"""Тесты для продвинутых типов счетов — Day 2.
Запуск: pytest -q
"""
from __future__ import annotations

import pytest

from src.day1.model.abstract_account import Owner, AccountStatus, Currency
from src.day2.model.savings_account import SavingsAccount
from src.day2.model.premium_account import PremiumAccount
from src.day2.model.investment_account import InvestmentAccount
from src.day1.exeptions.exceptions import InvalidOperationError, InsufficientFundsError, AccountFrozenError, AccountClosedError


def owner(name: str = "Иван", email: str = "ivan@example.com") -> Owner:
    return Owner(name=name, email=email)


# SavingsAccount

def test_savings_min_balance_and_interest():
    acc = SavingsAccount(owner=owner(), balance=1000, min_balance=200, monthly_interest_rate=0.01)
    # Снятие до границы
    acc.withdraw(800)  # останется 200
    assert pytest.approx(acc.get_account_info()["balance"]) == 200
    # Нельзя ниже минимума
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(1)
    # Начисляем проценты
    acc.apply_monthly_interest()  # +1%
    assert pytest.approx(acc.get_account_info()["balance"]) == 202.0


def test_savings_interest_skipped_if_not_active():
    acc = SavingsAccount(owner=owner(), balance=100, status=AccountStatus.FROZEN, monthly_interest_rate=0.5)
    acc.apply_monthly_interest()
    assert pytest.approx(acc.get_account_info()["balance"]) == 100


# PremiumAccount

def test_premium_overdraft_and_fee():
    acc = PremiumAccount(owner=owner(), balance=100, overdraft_limit=50, withdraw_fee_fixed=5)
    # Снимаем 90, с комиссией 5 => списание 95, баланс 5
    acc.withdraw(90)
    assert pytest.approx(acc.get_account_info()["balance"]) == 5
    # Снимаем ещё 50, с комиссией 5 => списание 55, баланс -50 (допустимо)
    acc.withdraw(50)
    assert pytest.approx(acc.get_account_info()["balance"]) == -50
    # Превышение лимита овердрафта
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(1)  # потребует ещё 6, ушло бы ниже -50


def test_premium_status_blocks_operations():
    acc_frozen = PremiumAccount(owner=owner(), status=AccountStatus.FROZEN)
    with pytest.raises(AccountFrozenError):
        acc_frozen.withdraw(1)
    acc_closed = PremiumAccount(owner=owner(), status=AccountStatus.CLOSED)
    with pytest.raises(AccountClosedError):
        acc_closed.withdraw(1)


# InvestmentAccount

def test_investment_portfolio_and_projection():
    acc = InvestmentAccount(owner=owner(), balance=1000, portfolio={"stocks": 0.5, "bonds": 0.3, "etf": 0.2})
    # Базовые ставки: 0.5*0.08 + 0.3*0.03 + 0.2*0.06 = 0.04 + 0.009 + 0.012 = 0.061
    projected = acc.project_yearly_growth()
    assert pytest.approx(projected, rel=1e-6) == 1000 * (1 + 0.061)


def test_investment_invalid_portfolio():
    with pytest.raises(InvalidOperationError):
        InvestmentAccount(owner=owner(), portfolio={"gold": 1.0})  # неизвестный ключ
    with pytest.raises(InvalidOperationError):
        InvestmentAccount(owner=owner(), portfolio={"stocks": -0.1})  # отрицательная доля
    with pytest.raises(InvalidOperationError):
        InvestmentAccount(owner=owner(), portfolio={"stocks": 0.6, "bonds": 0.5})  # сумма > 1


def test_investment_projection_custom_rates_and_status():
    acc = InvestmentAccount(owner=owner(), balance=500, portfolio={"stocks": 1.0})
    # Кастомная ставка 10% по акциям
    projected = acc.project_yearly_growth({"stocks": 0.10})
    assert pytest.approx(projected) == 550
    # В неактивном статусе роста нет
    acc.status = AccountStatus.FROZEN
    assert pytest.approx(acc.project_yearly_growth()) == 500
