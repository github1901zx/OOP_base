"""
Процессор транзакций: комиссии, конвертация, повторные попытки и фиксация ошибок.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING

from src.day1.model.abstract_account import AccountStatus, Currency
from src.day1.model.bank_account import BankAccount
from src.day2.model.premium_account import PremiumAccount
from src.day1.exeptions.exceptions import AccountClosedError, AccountFrozenError, InvalidOperationError, InsufficientFundsError

from .transaction import Transaction, TransactionStatus, TransactionType
from .queue import TransactionQueue


@dataclass
class ProcessorConfig:
    """Настройки процессора транзакций."""
    # Доп. фиксированная комиссия за внешние операции (в валюте транзакции)
    external_fee_fixed: float = 1.0
    # Количество повторных попыток при временной ошибке
    max_retries: int = 2
    # Базовые курсы валют (пара -> коэффициент). Если нет пары — пытаемся через RUB как базовую валюту.
    rates: Dict[Tuple[Currency, Currency], float] = field(default_factory=dict)


class TransactionProcessor:
    """Обрабатывает транзакции из очереди.

    Правила:
    - Запрет переводов при минусе (кроме премиум-счёта, у которого это регулируется самим withdraw)
    - Запрет на замороженные/закрытые счета
    - Комиссия за внешние переводы
    - Конвертация валют по простым курсам
    - Повторные попытки при временных ошибках
    - Фиксация ошибок в журнале
    - (Day5) Интеграция с аудитом и риск‑анализом: блокировать опасные операции.
    """

    def __init__(self, queue: TransactionQueue, config: Optional[ProcessorConfig] = None,
                 audit_log: Optional["AuditLog"] = None, risk_analyzer: Optional["RiskAnalyzer"] = None) -> None:
        self.queue = queue
        self.config = config or ProcessorConfig()
        self.error_log: List[str] = []
        # Опционально: аудит и анализатор риска (Day5)
        self.audit_log = audit_log
        self.risk_analyzer = risk_analyzer
        # Заполняем дефолтные курсы, если не переданы
        if not self.config.rates:
            self.config.rates = self._default_rates()

    @staticmethod
    def _default_rates() -> Dict[Tuple[Currency, Currency], float]:
        # Простейшие курсы относительно RUB
        pairs: Dict[Tuple[Currency, Currency], float] = {}
        base = {
            Currency.RUB: 1.0,
            Currency.USD: 100.0,
            Currency.EUR: 110.0,
            Currency.KZT: 0.21,
            Currency.CNY: 14.0,
        }
        # коэффициент A->B = base[A] / base[B]
        for a in base:
            for b in base:
                if a == b:
                    continue
                pairs[(a, b)] = base[a] / base[b]
        return pairs

    def convert(self, amount: float, cur_from: Currency, cur_to: Currency) -> float:
        if cur_from == cur_to:
            return amount
        rate = self.config.rates.get((cur_from, cur_to))
        if rate is None:
            raise InvalidOperationError("Нет курса для конвертации валют.")
        return amount * rate

    def process_next(self, now: datetime | None = None) -> bool:
        """Обрабатывает следующую готовую транзакцию. Возвращает True, если что-то обработано."""
        tx = self.queue.pop_ready(now)
        if not tx:
            return False
        # (Day5) Оценка риска перед обработкой
        if self.risk_analyzer is not None:
            from src.day5.model.audit import RiskLevel  # локальный импорт, чтобы избежать жёсткой зависимости
            level, reasons, extra = self.risk_analyzer.assess(
                amount=tx.amount,
                currency=tx.currency,
                sender=tx.sender,
                recipient=tx.recipient,
                now=now,
            )
            # Запись в аудит
            if self.audit_log is not None:
                msg = f"оценка риска: {level.value}"
                if level == RiskLevel.HIGH:
                    self.audit_log.error(msg, tx_id=tx.tx_id, **extra)
                elif level == RiskLevel.MEDIUM:
                    self.audit_log.warning(msg, tx_id=tx.tx_id, **extra)
                else:
                    self.audit_log.info(msg, tx_id=tx.tx_id, **extra)
            # Блокировка опасных операций
            if level == RiskLevel.HIGH:
                reason = "Операция заблокирована службой рисков"
                if reasons:
                    reason += f": {', '.join(reasons)}"
                tx.mark_failed(reason)
                return True
        try:
            self._process_transaction(tx)
            tx.mark_processed()
            return True
        except (AccountFrozenError, AccountClosedError, InsufficientFundsError, InvalidOperationError) as e:
            # Невосстанавливаемые ошибки — помечаем как failed
            tx.mark_failed(str(e))
            self.error_log.append(f"{tx.tx_id}: {type(e).__name__}: {e}")
            return True
        except Exception as e:  # временная ошибка
            tx.attempts += 1
            if tx.attempts > self.config.max_retries:
                tx.mark_failed(f"temporary_error: {e}")
                self.error_log.append(f"{tx.tx_id}: temporary_error: {e}")
            else:
                # Ре-очередь с бэкоффом
                delay = 1 * tx.attempts
                tx.updated_at = datetime.now(timezone.utc)
                self.queue.requeue(tx, delay_seconds=delay)
            return True

    def run_all(self, now: datetime | None = None, safety_limit: int = 1000) -> None:
        """Выполняет все готовые транзакции до опустошения очереди или достижения лимита итераций."""
        count = 0
        while count < safety_limit:
            processed = self.process_next(now)
            if not processed:
                break
            count += 1

    def _ensure_account_active(self, acc: BankAccount | None) -> None:
        if acc is None:
            return
        if acc.status in (AccountStatus.FROZEN, AccountStatus.CLOSED):
            if acc.status == AccountStatus.FROZEN:
                raise AccountFrozenError("Счёт заморожен.")
            else:
                raise AccountClosedError("Счёт закрыт.")

    def _process_transaction(self, tx: Transaction) -> None:
        # Проверяем тип
        if tx.tx_type != TransactionType.TRANSFER:
            raise InvalidOperationError("Неподдерживаемый тип транзакции.")
        # Валидация суммы
        try:
            amount = float(tx.amount)
        except (TypeError, ValueError):
            raise InvalidOperationError("Сумма должна быть числом.")
        if amount <= 0:
            raise InvalidOperationError("Сумма должна быть положительной.")

        # Комиссия (в валюте транзакции)
        fee_total = float(tx.fee_fixed or 0.0)
        if tx.is_external:
            fee_total += float(self.config.external_fee_fixed)

        # Аккаунты должны быть активны, если заданы
        self._ensure_account_active(tx.sender if isinstance(tx.sender, BankAccount) else tx.sender)
        self._ensure_account_active(tx.recipient if isinstance(tx.recipient, BankAccount) else tx.recipient)

        # Кейс 1: Внутренний перевод (sender и recipient заданы)
        if tx.sender is not None and tx.recipient is not None:
            sender: BankAccount = tx.sender  # type: ignore[assignment]
            recipient: BankAccount = tx.recipient  # type: ignore[assignment]
            # Списание у отправителя: сумма + комиссия (в валюте отправителя = tx.currency)
            if tx.currency != sender.currency:
                # конвертируем сумму для списания из валюты транзакции в валюту счёта отправителя
                debit_amount = self.convert(amount, tx.currency, sender.currency)
                debit_fee = self.convert(fee_total, tx.currency, sender.currency) if fee_total > 0 else 0.0
            else:
                debit_amount = amount
                debit_fee = fee_total
            total_debit = debit_amount + debit_fee
            # Для премиум овердрафт допускается их собственным withdraw
            if isinstance(sender, PremiumAccount):
                # списание двумя шагами, чтобы применились их правила/комиссии нет в методе — поэтому уменьшаем напрямую
                # Используем защищённый доступ через методы: сначала снимаем сумму, затем вручную уменьшаем на комиссию
                sender.withdraw(debit_amount)
                # Комиссию снимем как отдельное списание маленькой суммой
                if debit_fee > 0:
                    sender.withdraw(debit_fee)
            else:
                # Для обычных — нельзя уходить в минус: проверим баланс
                if total_debit > sender._balance:  # доступ к защищённому полю в рамках учебного задания
                    raise InsufficientFundsError("Недостаточно средств для перевода.")
                # Списываем
                sender.withdraw(debit_amount)
                if debit_fee > 0:
                    sender.withdraw(debit_fee)

            # Зачисление получателю: конвертация в валюту получателя
            credit_amount = amount
            if tx.currency != recipient.currency:
                credit_amount = self.convert(amount, tx.currency, recipient.currency)
            recipient.deposit(credit_amount)
            return

        # Кейс 2: Внешнее зачисление (sender=None, есть получатель)
        if tx.sender is None and tx.recipient is not None:
            recipient: BankAccount = tx.recipient  # type: ignore[assignment]
            # Комиссию удерживаем из суммы перед зачислением
            credit_amount = amount - fee_total
            if credit_amount <= 0:
                raise InvalidOperationError("Сумма после комиссии должна быть положительной.")
            if tx.currency != recipient.currency:
                credit_amount = self.convert(credit_amount, tx.currency, recipient.currency)
            recipient.deposit(credit_amount)
            return

        # Кейс 3: Внешнее списание (recipient=None, есть отправитель)
        if tx.recipient is None and tx.sender is not None:
            sender: BankAccount = tx.sender  # type: ignore[assignment]
            debit_amount = amount + fee_total
            if tx.currency != sender.currency:
                debit_amount = self.convert(debit_amount, tx.currency, sender.currency)
            # Списать средствами счёта (премиум может уйти в минус)
            sender.withdraw(debit_amount)
            return

        # Иначе некорректная конфигурация
        raise InvalidOperationError("Неверная конфигурация транзакции (нет отправителя и получателя).")
