"""
Очередь транзакций с поддержкой приоритета, планирования и отмены.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict

from .transaction import Transaction, TransactionStatus


@dataclass(order=True)
class _QueueItem:
    """Внутренний элемент в куче: сортировка по scheduled_at, затем по -priority (приоритет выше — раньше).
    Также используется порядковый номер для стабильности.
    """
    scheduled_at: datetime
    neg_priority: int
    order: int
    tx_id: str = field(compare=False)


class TransactionQueue:
    """Простая приоритетная очередь транзакций.
    - add(tx): добавить транзакцию
    - cancel(tx_id): отменить
    - pop_ready(now): извлечь следующую готовую к выполнению
    - __len__(): количество активных (не отменённых/не выполненных) в очереди
    - list_pending(): список id ожидающих
    """

    def __init__(self) -> None:
        self._heap: List[_QueueItem] = []
        self._items: Dict[str, Transaction] = {}
        self._order_seq: int = 0

    def add(self, tx: Transaction) -> None:
        if tx.tx_id in self._items:
            # перезапись запрещаем для простоты
            raise ValueError("Транзакция с таким id уже есть в очереди.")
        self._items[tx.tx_id] = tx
        self._order_seq += 1
        item = _QueueItem(
            scheduled_at=tx.scheduled_at,
            neg_priority=-int(tx.priority),
            order=self._order_seq,
            tx_id=tx.tx_id,
        )
        heapq.heappush(self._heap, item)

    def cancel(self, tx_id: str, reason: str = "cancelled_by_user") -> bool:
        tx = self._items.get(tx_id)
        if not tx:
            return False
        if tx.status in {TransactionStatus.PROCESSED, TransactionStatus.CANCELLED}:
            return False
        tx.cancel(reason)
        return True

    def pop_ready(self, now: datetime | None = None) -> Transaction | None:
        """Достаёт следующую транзакцию, у которой наступило время выполнения."""
        now = now or datetime.now(timezone.utc)
        while self._heap:
            top = self._heap[0]
            if top.scheduled_at > now:
                return None
            heapq.heappop(self._heap)
            tx = self._items.get(top.tx_id)
            if tx is None:
                continue
            # Пропускаем отменённые/уже обработанные
            if tx.status != TransactionStatus.PENDING:
                continue
            return tx
        return None

    def requeue(self, tx: Transaction, delay_seconds: int = 0) -> None:
        """Вернуть транзакцию обратно в очередь (например, для повторной попытки).
        Элемент уже есть в self._items, поэтому просто добавляем новую запись в кучу.
        """
        if tx.status != TransactionStatus.PENDING:
            return
        # переназначаем время
        tx.scheduled_at = (tx.scheduled_at or datetime.now(timezone.utc))
        if delay_seconds > 0:
            tx.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        # положим новый элемент в кучу без изменения self._items
        self._order_seq += 1
        heapq.heappush(self._heap, _QueueItem(
            scheduled_at=tx.scheduled_at,
            neg_priority=-int(tx.priority),
            order=self._order_seq,
            tx_id=tx.tx_id,
        ))

    def __len__(self) -> int:
        return sum(1 for tx in self._items.values() if tx.status == TransactionStatus.PENDING)

    def list_pending(self) -> List[str]:
        return [tx_id for tx_id, tx in self._items.items() if tx.status == TransactionStatus.PENDING]
