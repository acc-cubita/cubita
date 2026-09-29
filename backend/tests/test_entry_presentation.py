"""جزئیات سند: برچسبِ فعلی چارت، بدون تغییر دفتر یا خواندنِ ردیف‌به‌ردیف."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from app.models.accounting import JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.models.tenant import Tenant
from app.schemas.accounting import JournalEntryOut
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.entry_presentation import fill_line_labels
from app.tenant_context import session_tenant


def _entry(db, user, dimensions=False):
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = "hybrid"
    cash = get_account(db, cc.CASH)
    bank = get_account(db, cc.BANK)
    fields = {}
    if dimensions:
        analytic = AnalyticAccount(code="QA-31", name="قرارداد نمونه", created_by_id=user.id)
        center = CostCenter(code="QA-12", name="شعبهٔ نمونه", created_by_id=user.id)
        db.add_all([analytic, center])
        db.flush()
        fields = {"analytic_id": analytic.id, "cost_center_id": center.id}
    entry = make_journal_entry(db, date(2026, 6, 1), "انتقال وجه", "manual", user, [
        JournalLine(account_id=bank.id, debit=Decimal(600), credit=0, description="یک", **fields),
        JournalLine(account_id=bank.id, debit=Decimal(400), credit=0, description="دو"),
        JournalLine(account_id=cash.id, debit=0, credit=Decimal(1000), description="سه"),
    ])
    return entry, bank, cash


def test_detail_returns_labels_and_preserves_money_and_order(db, user, client):
    entry, bank, cash = _entry(db, user, dimensions=True)
    entry_id = entry.id
    bank.is_active = False  # تاریخچه باید نام حساب غیرفعال را هم نشان دهد.
    db.flush()
    db.expire_all()
    response = client.get(f"/api/journal-entries/{entry_id}")
    assert response.status_code == 200
    result = response.json()
    assert [line["description"] for line in result["lines"]] == ["یک", "دو", "سه"]
    assert [Decimal(line["debit"]) for line in result["lines"]] == [600, 400, 0]
    assert [Decimal(line["credit"]) for line in result["lines"]] == [0, 0, 1000]
    assert [line["account_name"] for line in result["lines"]] == [bank.name, bank.name, cash.name]
    assert result["lines"][0]["account_code"] == bank.code
    assert result["lines"][0]["analytic_name"] == "قرارداد نمونه"
    assert result["lines"][0]["analytic_code"] == "QA-31"
    assert result["lines"][0]["cost_center_name"] == "شعبهٔ نمونه"
    assert result["lines"][0]["cost_center_code"] == "QA-12"
    assert result["lines"][1]["analytic_name"] is None
    assert result["entry_date"] == "2026-06-01"
    assert not db.new and not db.dirty and not db.deleted


def test_labels_are_batched_and_restricted_to_entry_tenant(db, user):
    entry, _, _ = _entry(db, user, dimensions=True)
    out = JournalEntryOut.model_validate(entry)
    with patch.object(db, "execute", wraps=db.execute) as execute:
        fill_line_labels(db, entry, out)
        assert execute.call_count == 3  # هر بُعد یک query؛ حسابِ تکراری query تازه ندارد.
        for call in execute.call_args_list:
            statement = call.args[0]
            assert "tenant_id =" in str(statement)
            assert entry.tenant_id in statement.compile().params.values()


def test_missing_labels_stay_explicit_without_inventing_names(db, user, client):
    entry, _, _ = _entry(db, user)
    out = JournalEntryOut.model_validate(entry)
    out.lines[0].account_id = uuid4()  # DTO ناقص؛ خودِ دفتر را دست نمی‌زنیم.
    fill_line_labels(db, entry, out)
    assert out.lines[0].account_name is None
    assert out.lines[0].account_code is None
    assert out.lines[1].account_name
    assert client.get(f"/api/journal-entries/{uuid4()}").status_code == 404
