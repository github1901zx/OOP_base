"""Тесты для Day5: аудит и риск‑анализ.
Запуск: pytest -q
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os

import pytest

from src.day1.model.abstract_account import Owner, Currency
from src.day1.model.bank_account import BankAccount
from src.day2.model.premium_account import PremiumAccount
from src.day4.model.queue import TransactionQueue
from src.day4.model.transaction import Transaction, TransactionType
from src.day4.model.processor import TransactionProcessor, ProcessorConfig
from src.day5.model.audit import AuditLog, RiskAnalyzer, RiskConfig, RiskLevel, AuditLevel


@pytest.fixture()
def now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def owner(name: str) -> Owner:
    return Owner(name=name, email=f"{name.lower()}@ex.com")


def test_large_amount_blocked(now: datetime, tmp_path):
    # Счета в RUB
    a = BankAccount(owner=owner("A"), balance=200_000, currency=Currency.RUB)
    b = BankAccount(owner=owner("B"), balance=0, currency=Currency.RUB)

    q = TransactionQueue()
    audit = AuditLog()
    risk = RiskAnalyzer(RiskConfig())
    proc = TransactionProcessor(q, ProcessorConfig(external_fee_fixed=1.0), audit_log=audit, risk_analyzer=risk)

    # Крупная сумма >= 100_000 RUB — должна быть заблокирована
    tx = Transaction(tx_id="L1", tx_type=TransactionType.TRANSFER, amount=150_000, currency=Currency.RUB,
                     sender=a, recipient=b, scheduled_at=now, priority=10)
    q.add(tx)

    proc.run_all(now)

    # Заблокирована рисками
    assert tx.status.name == "FAILED"
    assert "заблокирована" in (tx.failure_reason or "")
    # Запись в аудит уровня ERROR
    suspicious = audit.get_suspicious_operations()
    assert any(r.level == AuditLevel.ERROR and r.extra.get("tx_id") == "L1" for r in suspicious)


def test_frequent_ops_blocked_and_medium_not_blocked(now: datetime):
    a = BankAccount(owner=owner("A"), balance=1000, currency=Currency.USD)
    b = BankAccount(owner=owner("B"), balance=0, currency=Currency.USD)

    q = TransactionQueue()
    audit = AuditLog()
    risk = RiskAnalyzer(RiskConfig(frequency_window_seconds=60, frequency_limit=3))
    proc = TransactionProcessor(q, ProcessorConfig(), audit_log=audit, risk_analyzer=risk)

    # Три маленьких операции подряд в окне 60с — третья должна быть заблокирована как HIGH
    base_time = now
    t1 = Transaction(tx_id="F1", tx_type=TransactionType.TRANSFER, amount=1, currency=Currency.USD,
                     sender=a, recipient=b, scheduled_at=base_time, priority=3)
    t2 = Transaction(tx_id="F2", tx_type=TransactionType.TRANSFER, amount=1, currency=Currency.USD,
                     sender=a, recipient=b, scheduled_at=base_time + timedelta(seconds=10), priority=2)
    t3 = Transaction(tx_id="F3", tx_type=TransactionType.TRANSFER, amount=1, currency=Currency.USD,
                     sender=a, recipient=b, scheduled_at=base_time + timedelta(seconds=20), priority=1)
    for t in (t1, t2, t3):
        q.add(t)

    # Обрабатываем по очереди
    proc.run_all(base_time)
    # t1 должен пройти (LOW/MEDIUM), t2 — пройти, t3 — упасть из‑за частоты
    assert t1.status.name == "PROCESSED"
    assert t2.status.name == "PROCESSED"
    assert t3.status.name == "FAILED"

    # В аудит должны быть записи разного уровня
    warnings = [r for r in audit.records if r.level == AuditLevel.WARNING]
    errors = [r for r in audit.records if r.level == AuditLevel.ERROR]
    assert warnings  # хотя бы одна
    assert errors    # и хотя бы одна


def test_new_recipient_and_night_operation_marked_medium(now: datetime):
    # Ночной интервал 00:00–05:00 UTC, поставим 02:00
    night = datetime(2025, 1, 1, 2, 0, tzinfo=timezone.utc)

    a = PremiumAccount(owner=owner("A"), balance=0, currency=Currency.RUB, overdraft_limit=100)
    b1 = BankAccount(owner=owner("B1"), balance=0, currency=Currency.RUB)
    b2 = BankAccount(owner=owner("B2"), balance=0, currency=Currency.RUB)

    q = TransactionQueue()
    audit = AuditLog()
    risk = RiskAnalyzer()
    proc = TransactionProcessor(q, ProcessorConfig(), audit_log=audit, risk_analyzer=risk)

    # Первый перевод на новый счёт b1 — MEDIUM, не блокируем
    t1 = Transaction(tx_id="M1", tx_type=TransactionType.TRANSFER, amount=10, currency=Currency.RUB,
                     sender=a, recipient=b1, scheduled_at=now, priority=2)
    # Ночная операция — MEDIUM, не блокируем
    t2 = Transaction(tx_id="M2", tx_type=TransactionType.TRANSFER, amount=10, currency=Currency.RUB,
                     sender=a, recipient=b2, scheduled_at=night, priority=1)
    q.add(t1)
    q.add(t2)

    proc.run_all(now)
    proc.run_all(night)

    assert t1.status.name == "PROCESSED"
    assert t2.status.name == "PROCESSED"

    # В аудит должны быть WARNING записи
    warnings = [r for r in audit.records if r.level == AuditLevel.WARNING]
    assert any(r.extra.get("tx_id") in {"M1", "M2"} for r in warnings)


def test_audit_reports_and_file_save(tmp_path):
    audit = AuditLog()
    # Сымитируем записи
    audit.info("ok", owner_name="A")
    audit.warning("подозрение", owner_name="A")
    audit.error("ошибка: недостаток", owner_name="B")

    # Фильтрация
    assert len(audit.filter(level=AuditLevel.WARNING)) == 1

    # Риск‑профиль
    profile = audit.get_clients_risk_profile()
    assert profile["A"]["warning"] == 1
    assert profile["B"]["error"] == 1

    # Статистика ошибок
    stats = audit.get_error_statistics()
    assert stats.get("ошибка") == 1

    # Сохранение в файл
    file_path = os.path.join(tmp_path, "audit.txt")
    audit.save_to_file(file_path)
    assert os.path.exists(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "warning" in content and "error" in content
