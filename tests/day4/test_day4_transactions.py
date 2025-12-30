"""Тесты для Day4: система транзакций, очередь и процессор."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.day1.model.abstract_account import Owner, Currency, AccountStatus
from src.day1.model.bank_account import BankAccount
from src.day2.model.premium_account import PremiumAccount
from src.day4.model.transaction import Transaction, TransactionType, TransactionStatus
from src.day4.model.queue import TransactionQueue
from src.day4.model.processor import TransactionProcessor, ProcessorConfig


def owner(name: str) -> Owner:
    return Owner(name=name, email=f"{name.lower()}@example.com")


def test_day4_full_flow():
    # Счета
    acc_a = BankAccount(owner=owner("Alice"), balance=1000.0, currency=Currency.RUB)
    acc_b = BankAccount(owner=owner("Bob"), balance=0.0, currency=Currency.USD)
    acc_p = PremiumAccount(owner=owner("Premium"), balance=0.0, currency=Currency.RUB, overdraft_limit=100.0)
    acc_frozen = BankAccount(owner=owner("Frozen"), balance=100.0, currency=Currency.RUB, status=AccountStatus.FROZEN)

    now = datetime.now(timezone.utc)

    # Очередь и процессор
    q = TransactionQueue()
    proc = TransactionProcessor(q, ProcessorConfig(external_fee_fixed=1.0))

    # 10 транзакций
    txs = [
        # 1. Внутренний перевод A(RUB)->B(USD) 100 RUB
        Transaction(tx_id="t1", tx_type=TransactionType.TRANSFER, amount=100, currency=Currency.RUB,
                    sender=acc_a, recipient=acc_b, scheduled_at=now, priority=10),
        # 2. Внешнее зачисление на A 200 RUB (будет удержана внешняя комиссия 1 RUB)
        Transaction(tx_id="t2", tx_type=TransactionType.TRANSFER, amount=200, currency=Currency.RUB,
                    sender=None, recipient=acc_a, is_external=True, scheduled_at=now, priority=9),
        # 3. Внутренний перевод A->B 50 RUB + внутренняя комиссия 2 RUB
        Transaction(tx_id="t3", tx_type=TransactionType.TRANSFER, amount=50, currency=Currency.RUB,
                    sender=acc_a, recipient=acc_b, fee_fixed=2, scheduled_at=now, priority=8),
        # 4. Внешнее списание со счёта A 100 RUB (комиссия 1 RUB)
        Transaction(tx_id="t4", tx_type=TransactionType.TRANSFER, amount=100, currency=Currency.RUB,
                    sender=acc_a, recipient=None, is_external=True, scheduled_at=now, priority=7),
        # 5. Попытка перевода B(USD)->A(RUB) 10 USD — не хватит средств
        Transaction(tx_id="t5", tx_type=TransactionType.TRANSFER, amount=10, currency=Currency.USD,
                    sender=acc_b, recipient=acc_a, scheduled_at=now, priority=6),
        # 6. Перевод со замороженного счёта — должен упасть
        Transaction(tx_id="t6", tx_type=TransactionType.TRANSFER, amount=10, currency=Currency.RUB,
                    sender=acc_frozen, recipient=acc_b, scheduled_at=now, priority=5),
        # 7. Перевод P(RUB)->A(RUB) 50 RUB — разрешённый овердрафт у премиум
        Transaction(tx_id="t7", tx_type=TransactionType.TRANSFER, amount=50, currency=Currency.RUB,
                    sender=acc_p, recipient=acc_a, scheduled_at=now, priority=4),
        # 8. Перевод A->P 20 RUB
        Transaction(tx_id="t8", tx_type=TransactionType.TRANSFER, amount=20, currency=Currency.RUB,
                    sender=acc_a, recipient=acc_p, scheduled_at=now, priority=3),
        # 9. Внешнее зачисление на B 300 USD (минус внешняя комиссия 1 USD)
        Transaction(tx_id="t9", tx_type=TransactionType.TRANSFER, amount=300, currency=Currency.USD,
                    sender=None, recipient=acc_b, is_external=True, scheduled_at=now, priority=2),
        # 10. Внешнее списание с P 10 RUB (комиссия 1 RUB)
        Transaction(tx_id="t10", tx_type=TransactionType.TRANSFER, amount=10, currency=Currency.RUB,
                    sender=acc_p, recipient=None, is_external=True, scheduled_at=now, priority=1),
    ]

    # Кладём в очередь
    for tx in txs:
        q.add(tx)

    # Выполняем все готовые
    proc.run_all(now)

    # Проверки статусов: должно быть 8 успешных, 2 с ошибкой
    statuses = {tx.tx_id: tx.status for tx in txs}
    assert list(statuses.values()).count(TransactionStatus.PROCESSED) == 8
    assert list(statuses.values()).count(TransactionStatus.FAILED) == 2

    # Конкретные ошибки: t5 недостаточно средств, t6 замороженный счёт
    assert txs[4].status == TransactionStatus.FAILED
    assert "Недостаточно средств" in (txs[4].failure_reason or "")
    assert txs[5].status == TransactionStatus.FAILED
    assert any(word in (txs[5].failure_reason or "") for word in ["заморожен", "заморожен".capitalize()])

    # Итоговые балансы
    # A: 1000 -100 +199 -52 -101 +50 -20 = 976 RUB
    assert pytest.approx(acc_a.get_account_info()["balance"], rel=1e-6) == 976.0
    # B: 0 +1 +0.5 +299 = 300.5 USD
    assert pytest.approx(acc_b.get_account_info()["balance"], rel=1e-6) == 300.5
    # P: 0 -50 +20 -11 = -41 RUB (овердрафт разрешён)
    assert pytest.approx(acc_p.get_account_info()["balance"], rel=1e-6) == -41.0

    # Очередь опустела по готовым заданиям (pending нет)
    assert len(q.list_pending()) == 0
