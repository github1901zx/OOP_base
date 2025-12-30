"""
Day 6 — Демонстрационная программа.

Простая симуляция всей банковской системы:
- создаёт банк, 6 клиентов и 12 счетов (разных типов)
- генерирует ~40 транзакций (часть ошибочных и подозрительных)
- добавляет транзакции в очередь, обрабатывает процессором
- ведёт аудит и риск-анализ
- показывает пользовательские сценарии и отчёты
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import List, Dict, Tuple

# Day1/Day2
from src.day1.model.abstract_account import Owner, Currency, AccountStatus
from src.day1.model.bank_account import BankAccount
from src.day2.model.savings_account import SavingsAccount
from src.day2.model.premium_account import PremiumAccount
from src.day2.model.investment_account import InvestmentAccount
# Day3
from src.day3.model.bank import Bank
from src.day3.model.client import Client
# Day4
from src.day4.model.transaction import Transaction, TransactionType, TransactionStatus
from src.day4.model.queue import TransactionQueue
from src.day4.model.processor import TransactionProcessor, ProcessorConfig
# Day5
from src.day5.model.audit import AuditLog, RiskAnalyzer


def build_bank() -> Tuple[Bank, Dict[str, Client]]:
    """Создать банк и 6 клиентов."""
    bank = Bank(name="DemoBank")
    clients: Dict[str, Client] = {}
    # Набор имён
    names = [
        ("Алексей Петров", "c1"),
        ("Иван Иванов", "c2"),
        ("Мария Смирнова", "c3"),
        ("Ольга Кузнецова", "c4"),
        ("Дмитрий Соколов", "c5"),
        ("Елена Попова", "c6"),
    ]
    for i, (full_name, cid) in enumerate(names, start=1):
        c = Client(full_name=full_name, client_id=cid, age=25 + i, contacts={"email": f"{cid}@example.com"})
        bank.add_client(c, password=f"p{i}")
        clients[cid] = c
    return bank, clients


def open_accounts(bank: Bank, clients: Dict[str, Client]) -> Dict[str, BankAccount]:
    """Открыть 12 счетов разных типов для клиентов, вернуть словарь по id счета."""
    accounts: Dict[str, BankAccount] = {}
    # Для простоты создаём 2 счета на клиента: базовый + тип по циклу
    types = ["basic", "savings", "premium", "investment"]
    currencies = [Currency.RUB, Currency.USD, Currency.EUR]
    for idx, cid in enumerate(clients.keys(), start=0):
        # Базовый
        acc_basic_id = bank.open_account(
            client_id=cid,
            account_type="basic",
            currency=random.choice(currencies),
            initial_balance=float(500 + 100 * idx),
        )
        accounts[acc_basic_id] = bank.accounts[acc_basic_id]
        # Доп. счёт по циклу типов
        t = types[(idx + 1) % len(types)]
        if t == "savings":
            acc_id = bank.open_account(
                client_id=cid,
                account_type="savings",
                currency=Currency.RUB,
                initial_balance=200.0,
                min_balance=50.0,
                monthly_interest_rate=0.01,
            )
        elif t == "premium":
            acc_id = bank.open_account(
                client_id=cid,
                account_type="premium",
                currency=Currency.RUB,
                initial_balance=0.0,
                overdraft_limit=100.0,
                withdraw_fee_fixed=2.0,
            )
        else:  # investment
            acc_id = bank.open_account(
                client_id=cid,
                account_type="investment",
                currency=Currency.USD,
                initial_balance=300.0,
                portfolio={"stocks": 0.6, "bonds": 0.2, "etf": 0.2},
            )
        accounts[acc_id] = bank.accounts[acc_id]

    # Чтобы были ошибки — заморозим один счёт
    # Возьмём первый id из словаря
    some_acc_id = next(iter(accounts))
    owner_client_id = None
    # найдём клиента-владельца
    for cid, cl in clients.items():
        if some_acc_id in cl.accounts:
            owner_client_id = cid
            break
    if owner_client_id:
        bank.freeze_account(owner_client_id, some_acc_id)
    return accounts


def make_transactions(accounts: Dict[str, BankAccount]) -> List[Transaction]:
    """Сгенерировать список из ~40 транзакций, часть ошибочных и подозрительных."""
    txs: List[Transaction] = []
    acc_list = list(accounts.values())
    now = datetime.now(timezone.utc)

    # 30 внутренних переводов (случайные пары)
    for i in range(1, 31):
        a = random.choice(acc_list)
        b = random.choice(acc_list)
        # избегаем перевода самому себе
        if a is b:
            b = random.choice(acc_list)
        amount = random.choice([10, 20, 50, 100, 200])
        # несколько больших сумм, чтобы пометить подозрительными
        if i % 15 == 0:
            amount = 2000.0
        txs.append(Transaction(
            tx_id=f"t{i}",
            tx_type=TransactionType.TRANSFER,
            amount=float(amount),
            currency=a.currency,  # валюта отправителя
            sender=a,
            recipient=b,
            scheduled_at=now,
            priority=random.randint(0, 10),
        ))

    # 10 внешних операций: 5 зачислений и 5 списаний
    for j in range(31, 36):
        b = random.choice(acc_list)
        amt = random.choice([50, 100, 300])
        txs.append(Transaction(
            tx_id=f"t{j}",
            tx_type=TransactionType.TRANSFER,
            amount=float(amt),
            currency=b.currency,
            sender=None,
            recipient=b,
            is_external=True,
            scheduled_at=now,
            priority=random.randint(0, 5),
        ))
    for j in range(36, 41):
        a = random.choice(acc_list)
        amt = random.choice([20, 40, 80])
        txs.append(Transaction(
            tx_id=f"t{j}",
            tx_type=TransactionType.TRANSFER,
            amount=float(amt),
            currency=a.currency,
            sender=a,
            recipient=None,
            is_external=True,
            scheduled_at=now,
            priority=random.randint(0, 5),
        ))

    # Создадим явную ошибку: слишком большая сумма у обычного счёта (недостаточно средств)
    a = random.choice(acc_list)
    b = random.choice(acc_list)
    txs.append(Transaction(
        tx_id="t_err_big",
        tx_type=TransactionType.TRANSFER,
        amount=1_000_000.0,
        currency=a.currency,
        sender=a,
        recipient=b,
        scheduled_at=now,
        priority=9,
    ))

    # Ночная транзакция для риска: назначим отдельный tx в ночное время
    # Используем отдельный scheduled_at, а обрабатывать будем целым пакетом с ночным now
    night = now.replace(hour=2, minute=30)
    a = random.choice(acc_list)
    b = random.choice(acc_list)
    txs.append(Transaction(
        tx_id="t_night",
        tx_type=TransactionType.TRANSFER,
        amount=500.0,
        currency=a.currency,
        sender=a,
        recipient=b,
        scheduled_at=night,
        priority=10,
    ))

    return txs


def simulate() -> None:
    """Полная симуляция: создание данных, запуск очереди и процессора, вывод результатов."""
    print("=== Day 6: Демонстрация банковской системы ===")
    random.seed(42)  # детерминированность

    bank, clients = build_bank()
    accounts = open_accounts(bank, clients)
    print(f"Создан банк {bank.name}. Клиентов: {len(clients)}. Счетов: {len(accounts)}")

    # Аудит и риски
    audit = AuditLog()
    risk = RiskAnalyzer()  # дефолтные правила из Day 5

    # Очередь и процессор
    queue = TransactionQueue()
    proc = TransactionProcessor(queue, ProcessorConfig(external_fee_fixed=1.0), audit_log=audit, risk_analyzer=risk)

    # Транзакции
    txs = make_transactions(accounts)

    # Логирование попадания в очередь
    for tx in txs:
        print(f"[QUEUE] Добавлена транзакция {tx.tx_id} (prio={tx.priority}, amount={tx.amount} {tx.currency.value})")
        queue.add(tx)

    # Обработка: часть транзакций — в ночное время, чтобы сработали ночные риски
    now_night = datetime.now(timezone.utc).replace(hour=2, minute=30)
    proc.run_all(now=now_night)

    # Итоги по транзакциям
    processed = sum(1 for t in txs if t.status == TransactionStatus.PROCESSED)
    failed = sum(1 for t in txs if t.status == TransactionStatus.FAILED)
    cancelled = sum(1 for t in txs if t.status == TransactionStatus.CANCELLED)
    pending = sum(1 for t in txs if t.status == TransactionStatus.PENDING)
    print("=== Итоги обработки ===")
    print(f"Успешно: {processed}, Ошибки: {failed}, Отменены: {cancelled}, В ожидании: {pending}")

    # Показать несколько ошибок
    for t in txs:
        if t.status == TransactionStatus.FAILED:
            print(f"[FAIL] {t.tx_id}: {t.failure_reason}")

    # Пользовательские сценарии для одного клиента (например, c1)
    print("=== Сценарии клиента c1 ===")
    cid = "c1"
    cl = clients[cid]
    print(f"Клиент: {cl.full_name} (статус: {cl.status.value})")
    print("Счета клиента:")
    for acc_id in cl.accounts:
        acc = bank.accounts[acc_id]
        info = acc.get_account_info()
        print(f" - {acc.__class__.__name__} {acc.id}: {info['balance']:.2f} {info['currency']} ({info['status']})")
    # Простая "история": транзакции, где клиент выступал отправителем или получателем
    print("История транзакций клиента c1:")
    for t in txs:
        def acc_belongs(a: BankAccount | None) -> bool:
            return a is not None and a.id in cl.accounts
        if acc_belongs(getattr(t, 'sender', None)) or acc_belongs(getattr(t, 'recipient', None)):
            print(f" * {t.tx_id}: {t.tx_type.value} {t.amount} {t.currency.value} -> {t.status.value}")

    # Подозрительные операции из аудита (уровни WARNING/ERROR) и внутреннего лога банка
    print("Подозрительные операции (аудит):")
    for rec in audit.filter():
        if rec.level.name in ("WARNING", "ERROR"):
            print(f" - [{rec.level.value}] {rec.message} (extra={rec.extra})")
    if bank.suspicious_log:
        print("Подозрительные события банка:")
        for msg in bank.suspicious_log:
            print(f" - {msg}")

    # Отчёты: топ-3 клиентов, статистика транзакций, общий баланс
    print("=== Отчёты ===")
    ranking = bank.get_clients_ranking()[:3]
    print("Топ-3 клиентов по суммарному балансу:")
    for i, (cid_rank, total) in enumerate(ranking, start=1):
        client_name = bank.clients[cid_rank].full_name
        print(f" {i}. {client_name} — {total:.2f}")

    print("Статистика транзакций:")
    print(f" processed={processed}, failed={failed}, cancelled={cancelled}, pending={pending}")

    # Общий баланс по всем клиентам (без учёта валют, как и метод банка)
    total_bank = 0.0
    for cid_all, cl_all in bank.clients.items():
        total_bank += bank.get_total_balance(cid_all)
    print(f"Общий баланс банка (сумма по всем счетам, без конвертации): {total_bank:.2f}")


def main() -> None:
    # Запуск демонстрации
    simulate()


if __name__ == "__main__":
    main()
