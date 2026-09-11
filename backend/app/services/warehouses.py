"""انبار به‌عنوان داده‌ی پایه — نگاشتِ حساب، فعال‌بودن، و اثرِ غیرفعال‌سازی.

سه چیز که پیش از این نبود و هر سه رفتاری‌اند:

**۱. معینِ هر انبار (§۹ §۱۰ §۱۱).** تا امروز همه‌ی انبارها به یک حسابِ
موجودیِ کالا می‌نشستند. انبارِ ضایعات و انبارِ مواد اولیه در دفتر از هم
تشخیص‌دادنی نبودند. حالا هر انبار می‌تواند معینِ خودش را داشته باشد — و اگر
نداشته باشد، همان حسابِ پیش‌فرض که امروز هم می‌گیرد.

**۲. «غیرفعال» واقعاً غیرفعال شود (§۱۵).** `is_active` از قبل بود ولی **فقط در
یک مسیر** سنجیده می‌شد (رسیدِ انبارِ خرید). فاکتور فروش، فاکتور خرید، تعدیل و
انتقال همگی انبارِ غیرفعال را می‌پذیرفتند — یعنی این پرچم یک برچسبِ نیمه‌کاره
بود، نه یک قاعده.

**۳. غیرفعال‌کردنِ انبارِ دارای موجودی (§۱۷).** کالا در انبارِ غیرفعال گیر
می‌افتد: نه از آن خارج می‌شود نه به آن وارد. §۱۷ می‌گوید «نگذارید موجودی بی‌صدا
سرگردان شود».

**انبار حساب نیست (§۱۰) و تعریفش رویدادِ مالی نیست (§۳۲).** هیچ‌کدام از توابعِ
این فایل سند نمی‌زنند و هیچ حرکتِ انباری نمی‌سازند.
"""
from __future__ import annotations

from datetime import date as date_
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account
from app.models.inventory import StockLedger, Warehouse
from app.services import chart_codes as cc
from app.services.common import assert_postable_account as assert_postable, get_account
from app.services.printing import fa_number


def resolve(db: Session, warehouse_id: UUID) -> Warehouse:
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "انبار یافت نشد")
    return warehouse


def inventory_account_id(db: Session, warehouse_id: UUID | None) -> UUID:
    """حسابِ موجودیِ کالا برای این انبار (§۹).

    **`NULL` روی انبار یعنی حسابِ پیش‌فرض، نه خطا.** نگاشت اختیاری است (§۱۳) و
    نبودنش دقیقاً همان رفتاری است که کوبیتا تا امروز داشته — پس هیچ ثبتی با
    افزودنِ این قابلیت نمی‌شکند.

    **در لحظه‌ی ثبت حل می‌شود، نه از قبل.** §۳۴: اگر شرکت بعداً نگاشت را عوض
    کند، اسنادِ گذشته باید همان حسابی را نشان دهند که آن روز خورده‌اند. چون سند
    تغییرناپذیر است و ردیفش حساب را در خودش دارد، این خودبه‌خود برقرار است —
    به‌شرط آن‌که هیچ‌جا حساب را از روی انبارِ *فعلی* دوباره حساب نکنیم.
    """
    if warehouse_id is not None:
        warehouse = db.get(Warehouse, warehouse_id)
        if warehouse is not None and warehouse.gl_account_id is not None:
            return warehouse.gl_account_id
    return get_account(db, cc.INVENTORY).id


def assert_usable(db: Session, warehouse_id: UUID | None, *, action: str = "این عملیات") -> Warehouse | None:
    """انبارِ غیرفعال در عملیاتِ تازه انتخاب نمی‌شود (§۱۵).

    گزارش‌ها و کاردکس و اسنادِ گذشته همچنان آن را می‌شناسند — غیرفعال‌کردن
    گذشته را پاک نمی‌کند، فقط جلوی *ثبتِ تازه* را می‌گیرد.
    """
    if warehouse_id is None:
        return None
    warehouse = resolve(db, warehouse_id)
    if not warehouse.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"انبار «{warehouse.name}» غیرفعال است و {action} روی آن ثبت نمی‌شود. "
            "برای ادامه، اول انبار را فعال کنید.",
        )
    return warehouse


def stock_positions(db: Session, warehouse_id: UUID, *, as_of: date_ | None = None) -> list[dict]:
    """کالاهایی که در این انبار موجودیِ غیرصفر دارند.

    از همان `stock_ledger` می‌آید که همه‌جای دیگر هم از آن می‌آید — نه شمارشِ
    دومی که بتواند با موجودی اختلاف پیدا کند.
    """
    query = (
        db.query(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.warehouse_id == warehouse_id)
        .group_by(StockLedger.item_id)
    )
    if as_of is not None:
        query = query.filter(StockLedger.entry_date <= as_of)
    return [
        {"item_id": item_id, "qty": Decimal(qty)}
        for item_id, qty in query.all()
        if Decimal(qty) != 0
    ]


def assert_can_deactivate(db: Session, warehouse: Warehouse) -> None:
    """§۱۷ — انباری که هنوز کالا دارد بی‌صدا غیرفعال نمی‌شود.

    **سیاستِ انتخاب‌شده: مسدود، نه هشدار.** دلیلش این است که سمتِ سرور جایی برای
    «تأیید می‌کنم» نیست؛ یا اجازه می‌دهیم یا نه. و اجازه‌ی خاموش یعنی کالا در
    انباری گیر می‌افتد که نه چیزی از آن خارج می‌شود نه به آن وارد — دقیقاً همان
    «سرگردانیِ موجودی» که فصل منعش می‌کند.

    برگشت‌پذیر هم هست: کاربر یا کالا را منتقل می‌کند یا انبار را فعال نگه
    می‌دارد. پیام هر دو راه را می‌گوید و تعداد را هم — «عملیات ناموفق» کاربر را
    می‌فرستد دنبالِ چیزی که خودمان می‌دانیم.
    """
    positions = stock_positions(db, warehouse.id)
    if positions:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"انبار «{warehouse.name}» هنوز {fa_number(len(positions))} قلم کالا با موجودیِ "
            "غیرصفر دارد و غیرفعال نمی‌شود. اول کالاها را به انبارِ دیگری منتقل کنید "
            "یا از انبار خارجشان کنید.",
        )


def row(db: Session, warehouse: Warehouse) -> dict:
    """ردیفِ فهرست — با کد و عنوانِ حسابِ معین (§۲۹).

    وقتی نگاشت خالی است، حسابِ پیش‌فرض نشان داده می‌شود و `is_default` می‌گوید
    که این انتخابِ کاربر نبوده. نشان‌ندادنش یعنی کاربر فکر کند این انبار به
    هیچ حسابی نمی‌نشیند، که غلط است.
    """
    account = db.get(Account, warehouse.gl_account_id) if warehouse.gl_account_id else None
    default = account is None
    if account is None:
        account = get_account(db, cc.INVENTORY)
    return {
        "id": warehouse.id,
        "code": warehouse.code,
        "name": warehouse.name,
        "name2": warehouse.name2,
        "responsible": warehouse.responsible,
        "phone": warehouse.phone,
        "address": warehouse.address,
        "address2": warehouse.address2,
        "is_active": warehouse.is_active,
        "gl_account_id": warehouse.gl_account_id,
        "gl_account_code": account.code if account else "",
        "gl_account_name": account.name if account else "",
        "gl_account_is_default": default,
    }


def assert_postable_account(db: Session, account_id: UUID | None) -> None:
    """معینِ انبار باید حسابی باشد که واقعاً سند می‌پذیرد.

    قاعده مشترک است و در `common` نشسته تا نگاشتِ انبار و نگاشتِ کالا یک رفتار
    داشته باشند؛ استثنا این‌جا نقشِ `inventory` است — همان پیش‌فرضی که انبارِ
    بی‌نگاشت هم می‌گیرد.
    """
    assert_postable(db, account_id, allow_role=cc.INVENTORY, subject="انبار")
