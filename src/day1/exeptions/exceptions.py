"""
Пользовательские исключения для банковских счетов.
"""


class AccountFrozenError(Exception):
    """Исключение: операция запрещена, так как счёт заморожен."""


class AccountClosedError(Exception):
    """Исключение: операция запрещена, так как счёт закрыт."""


class InvalidOperationError(Exception):
    """Исключение: некорректная операция (например, неверная сумма)."""


class InsufficientFundsError(Exception):
    """Исключение: недостаточно средств для выполнения операции."""
