"""Тесты для банковского продукта (BankAccount).
Запуск: pytest -q
"""

import re
import pytest

from src.day1.model.bank_account import BankAccount
from src.day1.model.abstract_account import Owner, AccountStatus, Currency
from src.day1.exeptions.exceptions import (
    AccountFrozenError,
    AccountClosedError,
    InvalidOperationError,
    InsufficientFundsError,
)


def make_owner(name: str = "Иван", email: str = "ivan@example.com") -> Owner:
    return Owner(name=name, email=email)


def test_auto_short_uuid_generated():
    acc = BankAccount(owner=make_owner())
    # Должен быть сгенерирован короткий id из 8 символов [0-9a-f]
    assert isinstance(acc.id, str)
    assert len(acc.id) == 8
    assert re.fullmatch(r"[0-9a-f]{8}", acc.id) is not None


def test_deposit_withdraw_happy_path():
    acc = BankAccount(owner=make_owner(), balance=100.0, currency=Currency.RUB)
    acc.deposit(50)
    acc.withdraw(30)
    # Итоговый баланс: 100 + 50 - 30 = 120
    info = acc.get_account_info()
    assert pytest.approx(info["balance"]) == 120.0
    assert info["currency"] == "RUB"


@pytest.mark.parametrize("status, exc", [
    (AccountStatus.FROZEN, AccountFrozenError),
    (AccountStatus.CLOSED, AccountClosedError),
])
@pytest.mark.parametrize("op", ["deposit", "withdraw"])
def test_operations_blocked_by_status(status, exc, op):
    acc = BankAccount(owner=make_owner(), status=status, balance=100)
    with pytest.raises(exc):
        getattr(acc, op)(10)


@pytest.mark.parametrize("bad_amount", [0, -1, -0.01, "abc", None])
@pytest.mark.parametrize("op", ["deposit", "withdraw"])
def test_invalid_amount_raises(bad_amount, op):
    acc = BankAccount(owner=make_owner(), balance=100)
    with pytest.raises(InvalidOperationError):
        getattr(acc, op)(bad_amount)


def test_insufficient_funds():
    acc = BankAccount(owner=make_owner(), balance=20)
    with pytest.raises(InsufficientFundsError):
        acc.withdraw(21)


def test_str_representation_contains_required_parts():
    owner = make_owner("Пётр")
    acc = BankAccount(owner=owner, account_id="ABCDEF12", balance=123.4, currency=Currency.USD)
    s = str(acc)
    # Тип счета (имя класса)
    assert "BankAccount" in s
    # Имя клиента
    assert "Пётр" in s
    # Последние 4 символа id
    assert "****EF12" in s
    # Статус (value из Enum — в нижнем регистре)
    assert "active" in s
    # Баланс и валюта
    assert "123.40 USD" in s


def test_get_account_info_dict():
    owner = make_owner("Анна")
    acc = BankAccount(owner=owner, account_id="12345678", balance=10.5, currency=Currency.KZT)
    info = acc.get_account_info()
    assert info == {
        "id": "12345678",
        "owner": "Анна",
        "status": "active",
        "balance": 10.5,
        "currency": "KZT",
    }


@pytest.mark.parametrize(
    "bad_status,bad_currency",
    [
        ("active", Currency.RUB),  # статус строкой — ошибка
        (AccountStatus.ACTIVE, "RUB"),  # валюта строкой — ошибка
    ],
)
def test_type_validation_in_constructor(bad_status, bad_currency):
    # Если передать неправильные типы статуса или валюты — должно упасть с InvalidOperationError
    with pytest.raises(InvalidOperationError):
        BankAccount(owner=make_owner(), status=bad_status, currency=bad_currency)
