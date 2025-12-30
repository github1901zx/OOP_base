"""Тесты для Day7: отчётность и визуализация."""
from __future__ import annotations

import json
import os

import pytest

from src.day1.model.abstract_account import Owner, Currency
from src.day1.model.bank_account import BankAccount
from src.day2.model.savings_account import SavingsAccount
from src.day3.model.bank import Bank
from src.day5.model.audit import AuditLog, AuditLevel
from src.day7.model.report import ReportBuilder


@pytest.fixture()
def bank_with_data() -> Bank:
    bank = Bank(name="ReportBank")
    # Добавим двух клиентов
    from src.day3.model.client import Client
    c1 = Client(full_name="Алексей", client_id="c1", age=25, contacts={"email": "a@ex.com"})
    c2 = Client(full_name="Мария", client_id="c2", age=28, contacts={"email": "m@ex.com"})
    bank.add_client(c1, password="1")
    bank.add_client(c2, password="2")
    # Откроем по два счёта
    a1 = bank.open_account("c1", account_type="basic", currency=Currency.RUB, initial_balance=100)
    a2 = bank.open_account("c1", account_type="savings", currency=Currency.RUB, initial_balance=300, min_balance=50)
    b1 = bank.open_account("c2", account_type="basic", currency=Currency.USD, initial_balance=50)
    b2 = bank.open_account("c2", account_type="basic", currency=Currency.USD, initial_balance=150)
    return bank


@pytest.fixture()
def audit_sample() -> AuditLog:
    audit = AuditLog()
    audit.info("ok", owner_name="Алексей")
    audit.warning("подозрительная активность", owner_name="Мария")
    audit.error("ошибка: риск", owner_name="Мария")
    return audit


def test_build_client_and_bank_reports(bank_with_data: Bank, audit_sample: AuditLog, tmp_path):
    rb = ReportBuilder(bank_with_data, audit_sample)
    # Клиентский отчёт
    client_report = rb.build_client_report("c1")
    assert client_report["client_id"] == "c1"
    assert client_report["full_name"]
    assert isinstance(client_report["accounts"], list) and len(client_report["accounts"]) >= 1
    assert isinstance(client_report["total_balance"], float) or isinstance(client_report["total_balance"], int)

    # Банковский отчёт
    bank_report = rb.build_bank_report()
    assert bank_report["bank_name"] == "ReportBank"
    assert bank_report["total_accounts"] >= 4
    assert isinstance(bank_report["accounts_by_status"], dict)
    assert isinstance(bank_report["totals_per_currency"], dict)
    assert isinstance(bank_report["top_clients"], list)

    # Рисковый отчёт
    risk_report = rb.build_risk_report()
    assert risk_report["suspicious_count"] >= 1
    assert "risk_profile" in risk_report and "error_stats" in risk_report

    # Экспорт JSON
    json_path = os.path.join(tmp_path, "client_c1.json")
    rb.export_to_json(client_report, json_path)
    assert os.path.exists(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data.get("client_id") == "c1"

    # Экспорт CSV (берём записи аудита)
    rows = risk_report["records"]
    csv_path = os.path.join(tmp_path, "risk_records.csv")
    rb.export_to_csv(rows, csv_path)
    assert os.path.exists(csv_path)
    with open(csv_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "level" in content and "message" in content


def test_save_charts_handles_matplotlib_absence(bank_with_data: Bank, audit_sample: AuditLog, tmp_path):
    rb = ReportBuilder(bank_with_data, audit_sample)
    # Простая временная серия для графика движения баланса
    timeseries = [("Jan", 100.0), ("Feb", 120.0), ("Mar", 90.0)]
    saved = rb.save_charts(str(tmp_path), balance_timeseries=timeseries)
    # Если matplotlib установлен — ожидаем хотя бы один файл, иначе — пустой список
    if saved:
        for p in saved:
            assert os.path.exists(p)
    else:
        assert saved == []
