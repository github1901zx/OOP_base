"""
Day5 — Аудит и риск‑анализ.

Простая система:
- AuditLog: уровни важности, хранение в памяти, запись в файл, фильтрация, отчёты
- RiskAnalyzer: определение подозрительных операций и уровня риска (низкий/средний/высокий)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable
from datetime import datetime, timezone, time, timedelta

from src.day1.model.abstract_account import Currency


class AuditLevel(Enum):
    """Уровни важности записей аудита."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class AuditRecord:
    """Одна запись аудита."""
    level: AuditLevel
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """Простой аудит-лог. Пишет в память и по запросу в файл, умеет фильтровать."""

    def __init__(self) -> None:
        self.records: List[AuditRecord] = []

    def add(self, level: AuditLevel, message: str, **extra: Any) -> None:
        self.records.append(AuditRecord(level=level, message=message, extra=extra))

    def info(self, message: str, **extra: Any) -> None:
        self.add(AuditLevel.INFO, message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        self.add(AuditLevel.WARNING, message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self.add(AuditLevel.ERROR, message, **extra)

    def filter(self, *, level: Optional[AuditLevel] = None,
               predicate: Optional[Callable[[AuditRecord], bool]] = None) -> List[AuditRecord]:
        """Фильтрация по уровню и/или произвольному предикату."""
        items = self.records
        if level is not None:
            items = [r for r in items if r.level == level]
        if predicate is not None:
            items = [r for r in items if predicate(r)]
        return list(items)

    def save_to_file(self, path: str) -> None:
        """Сохранить лог в текстовый файл (простой формат)."""
        with open(path, "w", encoding="utf-8") as f:
            for r in self.records:
                ts = r.timestamp.isoformat()
                lvl = r.level.value
                extra = " ".join(f"{k}={v}" for k, v in r.extra.items())
                f.write(f"[{ts}] {lvl}: {r.message} {extra}\n")

    # --- Отчёты ---
    def get_suspicious_operations(self) -> List[AuditRecord]:
        """Вернуть только подозрительные записи (WARNING/ERROR)."""
        return [r for r in self.records if r.level in (AuditLevel.WARNING, AuditLevel.ERROR)]

    def get_error_statistics(self) -> Dict[str, int]:
        """Простая статистика ошибок по тексту сообщения (подсчёт по префиксу до двоеточия)."""
        stats: Dict[str, int] = {}
        for r in self.filter(level=AuditLevel.ERROR):
            key = r.message.split(":", 1)[0]
            stats[key] = stats.get(key, 0) + 1
        return stats

    def get_clients_risk_profile(self) -> Dict[str, Dict[str, int]]:
        """Риск‑профиль клиента: считаем WARNING/ERROR по владельцу (owner_name в extra)."""
        profile: Dict[str, Dict[str, int]] = {}
        for r in self.get_suspicious_operations():
            owner = str(r.extra.get("owner_name", "?"))
            d = profile.setdefault(owner, {"warning": 0, "error": 0})
            if r.level == AuditLevel.WARNING:
                d["warning"] += 1
            if r.level == AuditLevel.ERROR:
                d["error"] += 1
        return profile


class RiskLevel(Enum):
    """Уровни риска."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RiskConfig:
    """Настройки RiskAnalyzer."""
    # Порог крупной суммы по валюте
    large_amount_threshold: Dict[Currency, float] = field(default_factory=lambda: {
        Currency.RUB: 100_000.0,
        Currency.USD: 2_000.0,
        Currency.EUR: 2_000.0,
        Currency.KZT: 2_000_000.0,
        Currency.CNY: 15_000.0,
    })
    # Частые операции: окно и лимит
    frequency_window_seconds: int = 60
    frequency_limit: int = 3  # >= 3 за минуту — риск
    # Ночной период (UTC): [00:00, 05:00)
    night_from: time = time(0, 0)
    night_to: time = time(5, 0)


class RiskAnalyzer:
    """Примитивный анализатор риска по набору правил.

    Правила (каждое даёт сигнал):
    - Крупная сумма (>= порога) → HIGH
    - Частые операции (>= frequency_limit в окне) → HIGH
    - Перевод на новый счёт (первый раз для пары отправитель→получатель) → MEDIUM
    - Операция ночью → MEDIUM

    Комбинации упрощены: если встретился хотя бы один HIGH сигнал — итог HIGH,
    иначе если есть хотя бы один MEDIUM — итог MEDIUM, иначе LOW.
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or RiskConfig()
        # История для частоты: по отправителю храним времена последних операций
        self._history: Dict[str, List[datetime]] = {}
        # Таблица новых получателей: для отправителя множество уже виденных получателей
        self._known_recipients: Dict[str, set[str]] = {}

    @staticmethod
    def _account_id(obj: Any) -> str:
        """Аккуратно достаём идентификатор счёта, если это банковский счёт."""
        try:
            return str(getattr(obj, "id"))
        except Exception:
            return ""

    @staticmethod
    def _owner_name(obj: Any) -> str:
        try:
            owner = getattr(obj, "owner", None)
            return str(getattr(owner, "name", ""))
        except Exception:
            return ""

    def _is_night(self, dt: datetime) -> bool:
        t = dt.timetz()
        return self.config.night_from <= t.replace(tzinfo=None) < self.config.night_to

    def assess(self, *, amount: float, currency: Currency, sender: Any, recipient: Any,
               now: Optional[datetime] = None) -> Tuple[RiskLevel, List[str], Dict[str, Any]]:
        """Оценка риска. Возвращает (уровень, причины, extra-для-аудита)."""
        now = now or datetime.now(timezone.utc)
        reasons: List[str] = []
        level = RiskLevel.LOW

        # 1) Крупная сумма
        try:
            amt = float(amount)
        except Exception:
            amt = 0.0
        threshold = self.config.large_amount_threshold.get(currency, float("inf"))
        if amt >= threshold:
            level = RiskLevel.HIGH
            reasons.append("крупная сумма")

        # 2) Частые операции (по отправителю)
        sender_id = self._account_id(sender)
        if sender_id:
            hist = self._history.setdefault(sender_id, [])
            # Удаляем старые записи
            window = timedelta(seconds=self.config.frequency_window_seconds)
            cutoff = now - window
            hist[:] = [ts for ts in hist if ts >= cutoff]
            hist.append(now)
            if len(hist) >= self.config.frequency_limit:
                level = RiskLevel.HIGH
                reasons.append("частые операции")

        # 3) Новый получатель для отправителя
        if sender_id:
            rec_id = self._account_id(recipient)
            known = self._known_recipients.setdefault(sender_id, set())
            if rec_id and rec_id not in known:
                # Первый перевод на этот счёт — помечаем MEDIUM, но не повышаем, если уже HIGH
                reasons.append("перевод на новый счёт")
                if level == RiskLevel.LOW:
                    level = RiskLevel.MEDIUM
                known.add(rec_id)

        # 4) Ночная операция
        if self._is_night(now):
            reasons.append("операция ночью")
            if level == RiskLevel.LOW:
                level = RiskLevel.MEDIUM

        extra = {
            "sender_id": sender_id,
            "recipient_id": self._account_id(recipient),
            "owner_name": self._owner_name(sender) or self._owner_name(recipient) or "",
            "amount": amt,
            "currency": currency.value,
            "reasons": ", ".join(reasons) if reasons else "",
            "risk_level": level.value,
        }
        return level, reasons, extra
