"""
Day 7 — Система отчётности и визуализации.

ReportBuilder формирует текстовые/структурированные отчёты и сохраняет графики.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple
import json
import csv
import os

from src.day3.model.bank import Bank
from src.day5.model.audit import AuditLog, AuditRecord

try:
    import matplotlib.pyplot as plt
    _HAVE_MPL = True
except Exception:
    plt = None
    _HAVE_MPL = False


class ReportBuilder:
    """Построитель отчётов по банку, клиентам и рискам."""

    def __init__(self, bank: Bank, audit_log: Optional[AuditLog] = None) -> None:
        self.bank = bank
        self.audit_log = audit_log

    # --- Генерация отчётов (как структуру dict) ---
    def build_client_report(self, client_id: str) -> Dict[str, Any]:
        """Отчёт по клиенту: базовая информация, список счетов, суммы."""
        client = self.bank.clients.get(client_id)
        if not client:
            raise KeyError("Клиент не найден")
        accounts: List[Dict[str, Any]] = []
        for acc_id in client.accounts:
            acc = self.bank.accounts.get(acc_id)
            if not acc:
                continue
            info = acc.get_account_info()
            accounts.append(info)
        total_balance = self.bank.get_total_balance(client_id)
        report = {
            "client_id": client.client_id,
            "full_name": client.full_name,
            "status": client.status.value,
            "accounts": accounts,
            "total_balance": total_balance,
        }
        return report

    def build_bank_report(self) -> Dict[str, Any]:
        """Отчёт по банку: количество счетов по статусу, суммы по валютам, топ клиентов."""
        # Считаем агрегаты
        by_status: Dict[str, int] = {}
        totals_per_currency: Dict[str, float] = {}
        for acc in self.bank.accounts.values():
            # по статусам
            st = getattr(acc.status, "value", str(acc.status))
            by_status[st] = by_status.get(st, 0) + 1
            # по валютам
            cur = getattr(acc.currency, "value", str(acc.currency))
            totals_per_currency[cur] = totals_per_currency.get(cur, 0.0) + float(acc._balance)
        # рейтинг клиентов (top-3)
        ranking = self.bank.get_clients_ranking()
        top3 = ranking[:3]
        report = {
            "bank_name": self.bank.name,
            "total_accounts": len(self.bank.accounts),
            "accounts_by_status": by_status,
            "totals_per_currency": totals_per_currency,
            "top_clients": [{"client_id": cid, "total_balance": total} for cid, total in top3],
        }
        return report

    def build_risk_report(self) -> Dict[str, Any]:
        """Отчёт по рискам на основании AuditLog (если он есть)."""
        if not self.audit_log:
            return {
                "suspicious_count": 0,
                "risk_profile": {},
                "error_stats": {},
                "records": [],
            }
        suspicious = self.audit_log.get_suspicious_operations()
        risk_profile = self.audit_log.get_clients_risk_profile()
        error_stats = self.audit_log.get_error_statistics()
        # Уложим записи в простой вид
        recs: List[Dict[str, Any]] = []
        for r in suspicious:
            recs.append({
                "level": r.level.value,
                "message": r.message,
                "timestamp": r.timestamp.isoformat(),
                "extra": dict(r.extra),
            })
        return {
            "suspicious_count": len(suspicious),
            "risk_profile": risk_profile,
            "error_stats": error_stats,
            "records": recs,
        }

    @staticmethod
    def export_to_json(data: Dict[str, Any], path: str) -> None:
        """Экспорт словаря в JSON файл (UTF-8)."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def export_to_csv(rows: Sequence[Dict[str, Any]], path: str) -> None:
        """Экспорт списка словарей в CSV. Поля берём по объединению всех ключей."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # Собираем набор всех ключей
        headers: List[str] = []
        seen = set()
        for row in rows:
            for k in row.keys():
                if k not in seen:
                    headers.append(k)
                    seen.add(k)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def save_charts(
        self,
        output_dir: str,
        *,
        pie_accounts_by_status: bool = True,
        bar_total_by_client: bool = True,
        balance_timeseries: Optional[List[Tuple[str, float]]] = None,
    ) -> List[str]:
        """Сохранить стандартный набор диаграмм в каталог.

        - Круговая: распределение счетов по статусам
        - Столбчатая: суммарные балансы по клиентам
        - Линейная: движение баланса (по переданному time series: [(label, value), ...])

        Возвращает список путей с сохранёнными изображениями. Если matplotlib недоступен — возвращает пустой список.
        """
        saved: List[str] = []
        if not _HAVE_MPL:
            return saved
        os.makedirs(output_dir, exist_ok=True)

        # 1) Pie: аккаунты по статусам
        if pie_accounts_by_status:
            data = self.build_bank_report()["accounts_by_status"]
            labels = list(data.keys()) or ["n/a"]
            sizes = list(data.values()) or [1]
            fig, ax = plt.subplots(figsize=(4, 4))  
            ax.pie(sizes, labels=labels, autopct="%1.1f%%")  
            ax.set_title("Счета по статусам")  
            path = os.path.join(output_dir, "pie_accounts_by_status.png")
            fig.tight_layout()  
            fig.savefig(path)  
            plt.close(fig)  
            saved.append(path)

        # 2) Bar: суммарные балансы по клиентам
        if bar_total_by_client:
            ranking = self.bank.get_clients_ranking()
            labels = [cid for cid, _ in ranking] or ["n/a"]
            values = [total for _, total in ranking] or [0.0]
            fig, ax = plt.subplots(figsize=(5, 3))  
            ax.bar(labels, values)  
            ax.set_title("Баланс по клиентам")  
            ax.set_xlabel("Клиент")  
            ax.set_ylabel("Сумма")  
            path = os.path.join(output_dir, "bar_total_by_client.png")
            fig.tight_layout()  
            fig.savefig(path)  
            plt.close(fig)  
            saved.append(path)

        # 3) Line: движение баланса (кастомная серия)
        if balance_timeseries:
            x = [label for label, _ in balance_timeseries]
            y = [float(val) for _, val in balance_timeseries]
            fig, ax = plt.subplots(figsize=(5, 3))  
            ax.plot(x, y, marker="o")  
            ax.set_title("Движение баланса")  
            ax.set_xlabel("Период")  
            ax.set_ylabel("Сумма")  
            path = os.path.join(output_dir, "line_balance_timeseries.png")
            fig.tight_layout()  
            fig.savefig(path)  
            plt.close(fig)  
            saved.append(path)

        return saved
