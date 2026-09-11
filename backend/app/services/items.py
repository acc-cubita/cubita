"""کالا و خدمت به‌عنوان داده‌ی پایه — حسابِ هزینه، نرخِ مالیات، و مرزهای رفتاری.

**یک هویت، رفتارِ وابسته به نوع (§۴۶ §۴۷).** کوبیتا از روزِ اول یک جدولِ `items`
داشت و خرید و فروش و انبار و صندوق همه از همان می‌خواندند؛ آن اصلِ اصلیِ فصل از
قبل رعایت شده بود. ولی *رفتار* یکی مانده بود، و این‌جا همان‌جاست که از هم جدا
می‌شوند.

---

**نقصی که این فایل می‌بندد.** `post_purchase_invoice` کلِ مبلغِ فاکتور را بدهکارِ
«موجودی کالا» می‌کرد — چه کالا بود چه خدمت. خریدِ ده ساعت مشاوره‌ی حقوقی یعنی:

* ترازنامه ۵۰ میلیون دارایی نشان می‌داد که **وجود نداشت** و هرگز هم خارج نمی‌شد؛
* گزارشِ انبار صفر می‌گفت، چون از `stock_ledger` مشتق می‌شود و خدمت حرکت ندارد؛
* هزینه **هیچ‌وقت** به سود و زیان نمی‌رسید، پس سود به همان اندازه بیش‌ازواقع بود؛
* و هیچ ترازی به‌هم نمی‌خورد که خبر بدهد — سند متوازن بود.

§۱۶ همین است: «فاکتورِ خریدِ خدمت می‌تواند اثرِ مالی داشته باشد، ولی نباید صرفاً
به‌خاطرِ داشتنِ واحد وارد موجودی شود.»
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.inventory import Item, StockLedger
from app.services import chart_codes as cc
from app.services.common import assert_postable_account as assert_postable
from app.services.common import get_or_create_account


def service_expense_account(db: Session) -> Account:
    """حسابِ پیش‌فرضِ «هزینه خرید خدمات».

    `get_or_create` است نه `get`: این نقش بعد از استقرارِ کسب‌وکارهای موجود اضافه
    شده و چارتِ هیچ‌کدامشان آن را ندارد. اولین خریدِ خدمت خودش می‌سازدش — همان
    الگوی «چک‌های واگذارشده به بانک» و حساب‌های ارزش افزوده.
    """
    return get_or_create_account(
        db,
        cc.SERVICE_EXPENSE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.SERVICE_EXPENSE],
        name="هزینه خرید خدمات",
        acc_type="expense",
        parent_code="5",
    )


def purchase_account_id(db: Session, item: Item, *, inventory_account_id: UUID) -> UUID:
    """حسابی که بهای خریدِ این قلم رویش می‌نشیند (§۱۵ §۱۶).

    **کالا → موجودیِ همان انبار. خدمت → حسابِ هزینه.** این تنها جایی است که این
    دو راه از هم جدا می‌شوند؛ بقیه‌ی موتورِ خرید یکی می‌ماند.

    نگاشتِ اختصاصیِ کالا مقدم است و خالی‌بودنش یعنی پیش‌فرضِ نقش — همان قاعده‌ای
    که معینِ انبار دارد. حساب هیچ‌جا با کد یا نام پیدا نمی‌شود.
    """
    if not item.is_service:
        return inventory_account_id
    if item.expense_account_id is not None:
        return item.expense_account_id
    return service_expense_account(db).id


def assert_expense_account(db: Session, account_id: UUID | None) -> None:
    """معینِ هزینه‌ی کالا باید حسابی باشد که سند می‌پذیرد و نقشِ ماژولِ دیگری نباشد."""
    assert_postable(db, account_id, allow_role=cc.SERVICE_EXPENSE, subject="کالا/خدمت")


def effective_tax_rate(item: Item, invoice_rate: Decimal, *, side: str) -> Decimal:
    """نرخی که واقعاً روی این ردیف می‌نشیند (§۱۳ §۱۴).

    سه لایه، به همین ترتیب:

    ۱. **معاف؟** صفر. معافیت مفهومی جدا از نرخ است — §۱۳ می‌گوید وضعیتِ مالیاتیِ
       خرید و فروش الزاماً یکی نیست، پس هر سمت پرچمِ خودش را دارد.
    ۲. **کالا نرخِ خودش را دارد؟** همان.
    ۳. وگرنه نرخِ سرِ فاکتور — یعنی **رفتارِ امروزِ کوبیتا**. نرخِ کالا برای همه‌ی
       کالاهای موجود صفر است، پس افزودنِ این لایه هیچ فاکتوری را تکان نمی‌دهد.

    آنچه در فاکتور می‌ماند `tax_rate_snapshot`ِ ردیف است، نه این تابع (§۱۴).
    """
    status_ = item.purchase_vat_status if side == "purchase" else item.vat_status
    if status_ == "exempt":
        return Decimal(0)
    own = Decimal(item.tax_rate or 0)
    return own if own > 0 else Decimal(invoice_rate or 0)


def assert_sellable(db: Session, items: list[Item]) -> None:
    """§۷ §۵۳ — هرچه در انبار داریم فروختنی نیست.

    موادِ اولیه و موادِ بسته‌بندی موجودی دارند و گردش می‌کنند، ولی در فاکتورِ
    فروش و صندوق نباید انتخاب شوند. تا امروز این تفکیک اصلاً وجود نداشت.
    """
    blocked = [i.name for i in items if not i.is_sellable]
    if blocked:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{'»، «'.join(blocked)}» قابلِ فروش علامت نخورده و در فروش انتخاب نمی‌شود. "
            "اگر باید فروخته شود، در تعریفِ کالا «قابل فروش» را روشن کنید.",
        )


def has_stock_history(db: Session, item_id: UUID) -> bool:
    return db.query(StockLedger.id).filter(StockLedger.item_id == item_id).first() is not None


def assert_serial_toggle_allowed(db: Session, item: Item, new_value: bool) -> None:
    """§۹ — «ثبت سریالی» را وسطِ گردشِ کالا نمی‌شود عوض کرد.

    کالایی که سال‌ها بی‌سریال گردش کرده، موجودیِ امروزش سریال ندارد. روشن‌کردنِ
    این پرچم یعنی از فردا هر ورود سریال می‌خواهد در حالی که موجودیِ قبلی‌اش
    ناشناس است — و خاموش‌کردنش یعنی سریال‌های ثبت‌شده بی‌معنا شوند.

    فصل می‌گوید این تغییر باید **کنترل‌شده** باشد؛ سمتِ سرور جایی برای «تأیید
    می‌کنم» نیست، پس یا اجازه می‌دهیم یا نه. راهِ برگشت هست: کالای تازه بسازید.
    """
    if new_value == item.is_serial_tracked:
        return
    if has_stock_history(db, item.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{item.name}» گردشِ انباری دارد و «ثبت سریالی»‌اش عوض نمی‌شود؛ "
            "موجودیِ ثبت‌شده سریال ندارد و تغییرِ این تنظیم ردیابی را مبهم می‌کند. "
            "برای شروعِ ردیابیِ سریالی، کالای تازه تعریف کنید.",
        )


def row(db: Session, item: Item, *, default_account: Account | None = None) -> dict:
    """بخشِ «معینِ هزینه»ی ردیفِ فهرست (§۴۸).

    برای **کالا** خالی می‌ماند: بهای خرید به موجودیِ انبار می‌نشیند، نه به حسابِ
    هزینه — نشان‌دادنش کاربر را به اشتباه می‌انداخت.

    `default_account` برای فهرست است: حسابِ پیش‌فرض یک‌بار برای کلِ صفحه حل
    می‌شود، نه یک‌بار برای هر ردیف.
    """
    account = db.get(Account, item.expense_account_id) if item.expense_account_id else None
    is_default = account is None
    if item.is_service and account is None:
        account = default_account if default_account is not None else service_expense_account(db)
    if not item.is_service and item.expense_account_id is None:
        account = None
    return {
        "expense_account_id": item.expense_account_id,
        "expense_account_code": account.code if account else "",
        "expense_account_name": account.name if account else "",
        "expense_account_is_default": is_default,
    }


def default_expense_account_or_none(db: Session) -> Account | None:
    """حسابِ پیش‌فرضِ هزینه‌ی خدمت، **بدونِ ساختنش**.

    فهرستِ کالاها نباید عارضه‌ی جانبی داشته باشد: بازکردنِ صفحه‌ی کالاها نباید
    در چارتِ کسب‌وکاری که هنوز هیچ خدمتی نخریده حساب بسازد.
    """
    return db.query(Account).filter(Account.system_role == cc.SERVICE_EXPENSE).first()
