from datetime import datetime

import pytest

from src.day3.model.client import Client, ClientStatus
from src.day3.model.bank import Bank
from src.day1.model.abstract_account import AccountStatus, Currency


@pytest.fixture()
def bank() -> Bank:
    return Bank(name="TestBank")


@pytest.fixture()
def client_alex() -> Client:
    return Client(full_name="Алексей Петров", client_id="c1", age=25, contacts={"email": "alex@example.com"})


@pytest.fixture()
def client_ivan() -> Client:
    return Client(full_name="Иван Иванов", client_id="c2", age=30, contacts={"email": "ivan@example.com"})


def test_add_client_and_open_accounts(bank: Bank, client_alex: Client):
    bank.add_client(client_alex, password="1234")
    # Открываем базовый счёт
    acc_id1 = bank.open_account(client_id="c1", account_type="basic", currency=Currency.RUB, initial_balance=100.0)
    # Открываем накопительный счёт
    acc_id2 = bank.open_account(
        client_id="c1",
        account_type="savings",
        currency=Currency.RUB,
        initial_balance=200.0,
        min_balance=50.0,
        monthly_interest_rate=0.01,
    )
    assert acc_id1 in bank.accounts
    assert acc_id2 in bank.accounts
    assert acc_id1 in bank.clients["c1"].accounts
    assert acc_id2 in bank.clients["c1"].accounts


def test_authenticate_with_block_after_three_fails(bank: Bank, client_alex: Client):
    bank.add_client(client_alex, password="pass")
    # 1-я неверная
    assert bank.authenticate_client("c1", "wrong") is False
    assert client_alex.status == ClientStatus.ACTIVE
    # 2-я неверная (клиент помечается подозрительным)
    assert bank.authenticate_client("c1", "nope") is False
    assert client_alex.suspicious is True
    # 3-я неверная -> блок
    assert bank.authenticate_client("c1", "still") is False
    assert client_alex.status == ClientStatus.BLOCKED
    # Верный пароль уже не поможет
    assert bank.authenticate_client("c1", "pass") is False


def test_freeze_unfreeze_close_account(bank: Bank, client_alex: Client):
    bank.add_client(client_alex, password="123")
    acc_id = bank.open_account("c1", account_type="basic", initial_balance=10)

    # Заморозка
    bank.freeze_account("c1", acc_id)
    assert bank.accounts[acc_id].status == AccountStatus.FROZEN

    # Разморозка
    bank.unfreeze_account("c1", acc_id)
    assert bank.accounts[acc_id].status == AccountStatus.ACTIVE

    # Закрыть счёт
    bank.close_account("c1", acc_id)
    assert bank.accounts[acc_id].status == AccountStatus.CLOSED
    # Счёт убрали у клиента
    assert acc_id not in bank.clients["c1"].accounts

    # Нельзя разморозить закрытый
    with pytest.raises(PermissionError):
        bank.unfreeze_account("c1", acc_id)


def test_total_balance_and_ranking(bank: Bank, client_alex: Client, client_ivan: Client):
    bank.add_client(client_alex, password="a")
    bank.add_client(client_ivan, password="b")

    a1 = bank.open_account("c1", account_type="basic", initial_balance=100)
    a2 = bank.open_account("c1", account_type="basic", initial_balance=50)
    i1 = bank.open_account("c2", account_type="basic", initial_balance=120)

    assert bank.get_total_balance("c1") == 150
    assert bank.get_total_balance("c2") == 120

    ranking = bank.get_clients_ranking()
    # Первый — c1 с 150, второй — c2 с 120
    assert ranking[0][0] == "c1" and ranking[0][1] == 150
    assert ranking[1][0] == "c2" and ranking[1][1] == 120


def test_operations_forbidden_by_time_window(bank: Bank, client_alex: Client, monkeypatch):
    bank.add_client(client_alex, password="a")

    # Подменяем текущее время на 02:30 — это запрещённый интервал
    def fake_now() -> datetime:
        return datetime(2025, 1, 1, 2, 30)

    bank.current_time_provider = fake_now

    with pytest.raises(PermissionError):
        bank.open_account("c1", account_type="basic", initial_balance=10)

    # При этом в журнале фиксируется подозрительная активность
    assert any("запрещённое" in msg for msg in bank.suspicious_log)
