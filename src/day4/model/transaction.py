"""
Модель транзакции для Day4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime, timezone

from src.day1.model.abstract_account import Currency


class TransactionType(Enum):
    """Типы транзакций (для простоты используем перевод)."""
    TRANSFER = "transfer"


class TransactionStatus(Enum):
    """Статусы транзакции."""
    PENDING = "pending"       # ожидает выполнения
    CANCELLED = "cancelled"   # отменена
    PROCESSED = "processed"   # успешно выполнена
    FAILED = "failed"         # неуспешна (ошибка)


@dataclass
class Transaction:
    """
    Транзакция перевода средств.

    Поля:
      - tx_id: идентификатор
      - tx_type: тип (Transfer)
      - amount: сумма (в валюте отправителя)
      - currency: валюта суммы
      - fee_fixed: фиксированная комиссия (в валюте отправителя)
      - sender: счёт-отправитель (может быть None для внешнего зачисления)
      - recipient: счёт-получатель (может быть None для внешнего списания)
      - status, failure_reason: статус и причина ошибки
      - created_at, scheduled_at, processed_at, updated_at: метки времени (UTC)
      - priority: приоритет (больше — важнее)
      - attempts: количество попыток
      - is_external: флаг «внешняя» операция (для доп. комиссии)
    """
    tx_id: str
    tx_type: TransactionType
    amount: float
    currency: Currency
    sender: Optional[object]
    recipient: Optional[object]
    fee_fixed: float = 0.0
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 0
    is_external: bool = False

    # Технические поля
    status: TransactionStatus = TransactionStatus.PENDING
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0

    def mark_failed(self, reason: str) -> None:
        self.status = TransactionStatus.FAILED
        self.failure_reason = reason
        self.updated_at = datetime.now(timezone.utc)

    def mark_processed(self) -> None:
        self.status = TransactionStatus.PROCESSED
        self.failure_reason = None
        self.processed_at = datetime.now(timezone.utc)
        self.updated_at = self.processed_at

    def cancel(self, reason: str = "cancelled_by_user") -> None:
        self.status = TransactionStatus.CANCELLED
        self.failure_reason = reason
        self.updated_at = datetime.now(timezone.utc)
