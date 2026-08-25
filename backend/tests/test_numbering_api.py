"""روش‌های شماره‌گذاری: فهرست، تنظیمِ شماره‌ی شروع، و ممنوعیتِ برگرداندنِ شمارنده."""
import pytest
from fastapi import HTTPException

from app.models.counters import DOC_TYPES, DocumentCounter
from app.routers.numbering import DOC_LABELS, NumberingIn, list_numbering, set_numbering
from app.services.numbering import next_document_number


def test_every_doc_type_has_persian_label():
    for t in DOC_TYPES:
        assert t in DOC_LABELS, f"نوع سند {t} برچسب فارسی ندارد"


def test_list_returns_all_counters_in_declared_order(db):
    rows = list_numbering(db=db)
    assert [r.doc_type for r in rows] == [t for t in DOC_TYPES]
    assert all(r.next_number == r.last_number + 1 for r in rows)


def test_set_start_number_moves_counter_forward(db, user):
    class _P:
        pass

    set_numbering("sales_invoice", NumberingIn(next_number=1241), principal=_P(), db=db)
    counter = db.query(DocumentCounter).filter(DocumentCounter.doc_type == "sales_invoice").first()
    assert counter.last_number == 1240
    # سندِ بعدی واقعاً همان شماره را می‌گیرد.
    assert next_document_number(db, "sales_invoice") == 1241


def test_cannot_move_counter_backwards(db):
    class _P:
        pass

    set_numbering("payslip", NumberingIn(next_number=50), principal=_P(), db=db)
    with pytest.raises(HTTPException) as err:
        set_numbering("payslip", NumberingIn(next_number=10), principal=_P(), db=db)
    assert err.value.status_code == 400


def test_unknown_doc_type_is_404(db):
    class _P:
        pass

    with pytest.raises(HTTPException) as err:
        set_numbering("not_a_doc", NumberingIn(next_number=5), principal=_P(), db=db)
    assert err.value.status_code == 404
