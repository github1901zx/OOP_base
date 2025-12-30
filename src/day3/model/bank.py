from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Callable, Dict, List, Optional, Tuple

from src.day1.model.abstract_account import AccountStatus, Currency, Owner
from src.day1.model.bank_account import BankAccount
from src.day2.model.savings_account import SavingsAccount
from src.day2.model.premium_account import PremiumAccount
from src.day2.model.investment_account import InvestmentAccount
from .client import Client, ClientStatus


# Допустимые типы счетов и соответствующие классы
ACCOUNT_TYPES = {
    "basic": BankAccount,
    "bank": BankAccount,  # синоним
    "savings": SavingsAccount,
    "premium": PremiumAccount,
    "investment": InvestmentAccount,
}


@dataclass
class Bank:
    """
    - clients: словарь клиентов по client_id
    - accounts: словарь счетов по account_id
    - credentials: простая база паролей
    - failed_logins: счетчик неудачных попыток для блокировки
    - current_time_provider: функция, возвращающая текущее время (для тестов можно подменять)
    - suspicious_log: журнал подозрительных событий
    """
    name: str = "MyBank"
    clients: Dict[str, Client] = field(default_factory=dict)
    accounts: Dict[str, BankAccount] = field(default_factory=dict)
    credentials: Dict[str, str] = field(default_factory=dict)
    failed_logins: Dict[str, int] = field(default_factory=dict)
    suspicious_log: List[str] = field(default_factory=list)
    current_time_provider: Callable[[], datetime] = datetime.now

    # --- Вспомогательные проверки ---
    @staticmethod
    def _is_restricted_time(dt: datetime) -> bool:
        """Запрет операций с 00:00 до 05:00 включительно интервал [00:00, 05:00)."""
        return time(0, 0) <= dt.time() < time(5, 0)

    def _ensure_ops_allowed(self) -> None:
        if self._is_restricted_time(self.current_time_provider()):
            # Фиксируем подозрительную активность
            self.suspicious_log.append("Операция в запрещённое время")
            # Запрещаем операцию
            raise PermissionError("Операции запрещены с 00:00 до 05:00.")

    def _ensure_client_active(self, client_id: str) -> None:
        client = self.clients.get(client_id)
        if not client:
            raise KeyError("Клиент не найден")
        if client.status == ClientStatus.BLOCKED:
            raise PermissionError("Клиент заблокирован.")

    # --- Клиенты ---
    def add_client(self, client: Client, password: str) -> None:
        """Добавить клиента с установкой пароля для аутентификации."""
        self.clients[client.client_id] = client
        self.credentials[client.client_id] = str(password)
        self.failed_logins[client.client_id] = 0

    def authenticate_client(self, client_id: str, password: str) -> bool:
        """Простейшая аутентификация клиента. 3 неверные попытки подряд = блокировка."""
        if client_id not in self.clients:
            return False
        client = self.clients[client_id]
        if client.status == ClientStatus.BLOCKED:
            return False
        ok = self.credentials.get(client_id) == str(password)
        if ok:
            self.failed_logins[client_id] = 0
            return True
        # неудача
        self.failed_logins[client_id] = self.failed_logins.get(client_id, 0) + 1
        # помечаем подозрительно после 2-х ошибок
        if self.failed_logins[client_id] >= 2:
            client.mark_suspicious()
            self.suspicious_log.append(f"Подозрение: {client_id} несколько неудачных входов")
        # блокируем после 3-х
        if self.failed_logins[client_id] >= 3:
            client.status = ClientStatus.BLOCKED
        return False

    # --- Счета ---
    def open_account(
        self,
        client_id: str,
        account_type: str = "basic",
        currency: Currency = Currency.RUB,
        initial_balance: float = 0.0,
        **kwargs,
    ) -> str:
        """Открыть счёт указанного типа для клиента. Возвращает id счёта.
        account_type: basic|savings|premium|investment
        Доп. параметры пробрасываются в конструкторы дочерних классов (например, min_balance и т.п.).
        """
        self._ensure_ops_allowed()
        self._ensure_client_active(client_id)
        client = self.clients[client_id]

        cls = ACCOUNT_TYPES.get(account_type.lower())
        if not cls:
            raise ValueError("Неизвестный тип счёта")
        # Владелец для абстрактного аккаунта — используем Owner из day1
        owner = Owner(name=client.full_name, email=client.contacts.get("email", ""))

        # Создаём конкретный счёт
        if cls is BankAccount:
            account = BankAccount(owner=owner, balance=initial_balance, currency=currency)
        elif cls is SavingsAccount:
            account = SavingsAccount(owner=owner, balance=initial_balance, currency=currency, **kwargs)
        elif cls is PremiumAccount:
            account = PremiumAccount(owner=owner, balance=initial_balance, currency=currency, **kwargs)
        elif cls is InvestmentAccount:
            portfolio = kwargs.get("portfolio")
            account = InvestmentAccount(owner=owner, balance=initial_balance, currency=currency, portfolio=portfolio)
        else:
            raise ValueError("Неподдерживаемый тип счёта")

        self.accounts[account.id] = account
        client.add_account(account.id)
        return account.id

    def close_account(self, client_id: str, account_id: str) -> None:
        """Закрыть счёт клиента (меняем статус на CLOSED)."""
        self._ensure_ops_allowed()
        self._ensure_client_active(client_id)
        client = self.clients[client_id]
        if account_id not in client.accounts:
            raise PermissionError("Счёт не принадлежит клиенту")
        acc = self.accounts.get(account_id)
        if not acc:
            raise KeyError("Счёт не найден")
        acc.status = AccountStatus.CLOSED
        client.remove_account(account_id)

    def freeze_account(self, client_id: str, account_id: str) -> None:
        """Заморозить счёт клиента (меняем статус на FROZEN)."""
        self._ensure_ops_allowed()
        self._ensure_client_active(client_id)
        client = self.clients[client_id]
        if account_id not in client.accounts:
            raise PermissionError("Счёт не принадлежит клиенту")
        acc = self.accounts.get(account_id)
        if not acc:
            raise KeyError("Счёт не найден")
        acc.status = AccountStatus.FROZEN

    def unfreeze_account(self, client_id: str, account_id: str) -> None:
        """Разморозить счёт (меняем статус на ACTIVE)."""
        self._ensure_ops_allowed()
        self._ensure_client_active(client_id)
        client = self.clients[client_id]
        if account_id not in client.accounts:
            raise PermissionError("Счёт не принадлежит клиенту")
        acc = self.accounts.get(account_id)
        if not acc:
            raise KeyError("Счёт не найден")
        if acc.status == AccountStatus.CLOSED:
            raise PermissionError("Нельзя разморозить закрытый счёт")
        acc.status = AccountStatus.ACTIVE

    # --- Поиск и аналитика ---
    def search_accounts(
        self,
        *,
        client_id: Optional[str] = None,
        owner_name_contains: Optional[str] = None,
        status: Optional[AccountStatus] = None,
    ) -> List[str]:
        """Поиск счетов по простым критериям. Возвращает список id счетов."""
        result: List[str] = []
        for acc_id, acc in self.accounts.items():
            if client_id:
                c = self.clients.get(client_id)
                if not c or acc_id not in c.accounts:
                    continue
            if owner_name_contains:
                if owner_name_contains.lower() not in acc.owner.name.lower():
                    continue
            if status and acc.status != status:
                continue
            result.append(acc_id)
        return result

    def get_total_balance(self, client_id: str) -> float:
        """Подсчитать общий баланс по всем счетам клиента (без учёта валют)."""
        c = self.clients.get(client_id)
        if not c:
            raise KeyError("Клиент не найден")
        total = 0.0
        for acc_id in c.accounts:
            acc = self.accounts.get(acc_id)
            if acc:
                total += acc._balance  # защищённое поле, но для простоты используем напрямую
        return total

    def get_clients_ranking(self) -> List[Tuple[str, float]]:
        """Рейтинг клиентов по суммарному балансу (убывание). Возвращает [(client_id, total_balance), ...]."""
        items: List[Tuple[str, float]] = []
        for cid in self.clients.keys():
            items.append((cid, self.get_total_balance(cid)))
        items.sort(key=lambda x: x[1], reverse=True)
        return items
