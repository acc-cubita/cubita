"""نقشِ طرف حساب — چهار پرچمِ مستقل، و سمتی از دفتر که هرکدام روی آن می‌نشیند.

**چه چیزی غلط بود.** `contacts.type` سه مقدار بیشتر نداشت، پس فرم مجبور بود
واسطه‌ی خالص را «تأمین‌کننده» ثبت کند:

```
const contactType = isCustomer && isSupplier ? 'both' : isCustomer ? 'customer' : 'supplier'
```

کاربر همین را دید و پرسید «منطقش چیه؟». منطقی داشت — جریانِ پول از ما به واسطه
است — ولی هزینه‌اش این بود که واسطه در انتخابگرِ **تأمین‌کننده‌ی رسیدِ انبار**
ظاهر می‌شد، انگار می‌شود ازش کالا تحویل گرفت.

**قیدی که این فایل نگه می‌دارد، همان چیزی است که این تغییر می‌توانست بشکند.**
آن برچسبِ غلط بی‌کار نبود: سه گاردِ حسابداری رویش تکیه داشتند تا بشود پورسانتِ
واسطه را پرداخت کرد. اگر نقش درست ثبت شود ولی آن سه گارد به‌روز نشوند، نتیجه
یک باگِ بدتر است — پورسانت روی حساب‌های **دریافتنی** می‌نشیند، یعنی طلبی که
وجود ندارد.
"""
from decimal import Decimal

import pytest

from app.models.inventory import Contact


def _add(db, name, **kw) -> Contact:
    row = Contact(name=name, **kw)
    db.add(row)
    db.flush()
    return row


# ─────────────── مشتق‌بودنِ `type` ───────────────


@pytest.mark.parametrize(("flags", "expected"), [
    ({"is_customer": True, "is_supplier": False}, "customer"),
    ({"is_customer": False, "is_supplier": True}, "supplier"),
    ({"is_customer": True, "is_supplier": True}, "both"),
    ({"is_customer": False, "is_supplier": False}, "none"),
])
def test_type_is_derived_from_the_flags(db, flags, expected):
    """`type` دیگر ستون نیست؛ از دو پرچم ساخته می‌شود — **با مقدارِ چهارم**."""
    row = _add(db, "مشتقِ نوع", **flags)
    assert row.type == expected


@pytest.mark.parametrize(("value", "flags"), [
    ("customer", (True, False)),
    ("supplier", (False, True)),
    ("both", (True, True)),
])
def test_writing_type_still_works(db, value, flags):
    """**پیش‌فرض = رفتارِ دیروز.** ده‌ها فراخوان `type="supplier"` می‌نویسند؛
    همه باید بی‌تغییر کار کنند، وگرنه این مهاجرت نیمی از کد را می‌شکست."""
    row = _add(db, "نوشتنِ نوع", type=value)
    assert (row.is_customer, row.is_supplier) == flags
    assert row.type == value


def test_the_flags_are_queryable_in_sql(db):
    """`Contact.type` باید در **کوئری** هم کار کند، نه فقط روی شیء.

    بدونِ `@type.expression` این فیلتر خطا می‌دهد — و `crm.py` از همین می‌خورد.
    """
    _add(db, "کوئریِ الف", type="customer")
    _add(db, "کوئریِ ب", type="supplier")
    db.flush()
    names = {c.name for c in db.query(Contact).filter(Contact.type == "supplier").all()}
    assert "کوئریِ ب" in names
    assert "کوئریِ الف" not in names


# ─────────────── سمتِ دفتر ───────────────


def test_a_pure_broker_is_a_payable_party(db):
    """**هسته‌ی این اصلاح.** واسطه‌ی خالص دیگر تأمین‌کننده نیست، ولی هنوز باید
    بشود پورسانتش را پرداخت کرد."""
    row = _add(db, "واسطه‌ی خالص", is_broker=True, commission_rate=Decimal(3))
    assert row.type == "none", "*** واسطه‌ی خالص هنوز نقشِ معاملاتی می‌گیرد ***"
    assert row.is_payable_party, "*** پورسانتِ این واسطه قابلِ پرداخت نیست ***"
    assert not row.is_receivable_party


@pytest.mark.parametrize(("kw", "payable"), [
    ({"is_broker": True}, True),
    ({"is_shareholder": True}, True),
    ({"is_employee": True}, True),
    ({"type": "supplier"}, True),
    ({"type": "customer"}, False),
])
def test_who_sits_on_payables(db, kw, payable):
    """سهامدار سودِ سهام می‌گیرد و کارمند حقوق — جریانِ پول از ما به آن‌هاست."""
    assert _add(db, "سمتِ دفتر", **kw).is_payable_party is payable


def test_only_a_customer_sits_on_receivables(db):
    """در سمتِ دریافتنی گشایشی نیست: فقط مشتری به ما بدهکار می‌شود."""
    assert _add(db, "فقط واسطه", is_broker=True).is_receivable_party is False
    assert _add(db, "فقط سهامدار", is_shareholder=True).is_receivable_party is False
    assert _add(db, "مشتری", type="customer").is_receivable_party is True


def test_unset_flags_are_false_not_none(db):
    """پیش از `flush` پرچمِ تنظیم‌نشده `None` است؛ این خاصیت به پاسخِ API می‌رود،
    پس باید `bool` باشد نه `None`."""
    row = Contact(name="بی‌فلاش", type="customer")
    assert row.is_payable_party is False
    assert row.is_receivable_party is True


# ─────────────── مسیرِ API ───────────────


def test_the_api_accepts_the_flags_and_reports_none(client):
    """واسطه‌ی خالص از راهِ API — چیزی که تا دیروز بیان‌شدنی نبود."""
    made = client.post("/api/contacts", json={
        "name": "واسطه‌ی API", "is_customer": False, "is_supplier": False, "is_broker": True,
    })
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["type"] == "none"
    assert body["is_customer"] is False and body["is_supplier"] is False
    assert body["is_broker"] is True


def test_the_flags_beat_type_when_both_are_sent(client):
    """اگر هم `type` بیاید هم پرچم‌ها، **پرچم‌ها برنده‌اند**.

    بدونِ تصمیمِ صریح در روتر، نتیجه به ترتیبِ کلیدهای دیکشنری بند بود — باگی
    که فقط گاهی خودش را نشان می‌دهد.
    """
    made = client.post("/api/contacts", json={
        "name": "تعارضِ نقش", "type": "supplier", "is_customer": True, "is_supplier": False,
    })
    assert made.status_code == 201, made.text
    assert made.json()["type"] == "customer"


def test_type_alone_still_works_over_the_api(client):
    """موبایل و ورودِ گروهی هنوز `type` می‌فرستند و نباید بشکنند."""
    made = client.post("/api/contacts", json={"name": "فقط نوع", "type": "both"})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["type"] == "both"
    assert body["is_customer"] is True and body["is_supplier"] is True


def test_a_patch_that_omits_roles_leaves_them_alone(client):
    """**ویرایشِ جزئی، نه جایگزینی.** `PATCH`ی که نقش نمی‌فرستد نباید صفرش کند —
    همان تله‌ای که روتر از قبل درباره‌اش هشدار داده است.
    """
    made = client.post("/api/contacts", json={
        "name": "ویرایشِ جزئی", "is_customer": False, "is_supplier": False, "is_broker": True,
    }).json()
    patched = client.patch(f"/api/contacts/{made['id']}", json={"phone": "02100000000"})
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["type"] == "none", "*** PATCH نقش را صفر کرد ***"
    assert body["is_broker"] is True
