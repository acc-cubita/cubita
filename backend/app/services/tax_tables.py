"""جدولِ مالیاتِ حقوق: حل‌کننده، اعتبارسنجی، و تفکیکِ پله‌به‌پله.

سه مسئولیت که عمداً از `services/payroll.py` بیرون ماندند، چون آن فایل موتورِ
محاسبه است و این‌جا **قاعده** است — دو چیزِ جدا که فصل هم جدایشان می‌خواهد:

    جدولِ مالیات   می‌گوید چه نرخی روی چه پایه‌ای
    شعبه‌ی مالیاتی می‌گوید چطور تعدیل شود (ماهانه / سالانه / بدون تعدیل)
    موتور          این دو را با هم اجرا می‌کند
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.payroll import TaxTable, TaxTableBracket

#: UUIDِ صفر — همان جای‌گزینِ `NULL` که ایندکسِ یکتای مهاجرت استفاده می‌کند.
NIL_GROUP = UUID("00000000-0000-0000-0000-000000000000")


@dataclass(frozen=True)
class BracketStep:
    """یک پله‌ی مصرف‌شده در محاسبه — برای توضیح‌پذیری، نه برای ذخیره."""

    seq: int
    lower: Decimal
    #: `None` یعنی سقفِ نامحدود.
    upper: Decimal | None
    rate: Decimal
    #: چه مقدار از مبنا در همین پله مصرف شد.
    consumed: Decimal
    #: مالیاتی که همین پله ساخت.
    tax: Decimal
    #: مالیاتِ تجمعی تا پایانِ همین پله.
    cumulative: Decimal


def bracket_rows(table: TaxTable) -> list[dict]:
    """پله‌های جدول به همان شکلی که موتور می‌فهمد: `{"up_to", "rate"}`.

    **مرتب‌سازی از روی سقف است، نه از روی `seq`.** ترتیبِ نمایش نباید مرجعِ
    مالیات باشد؛ یک ردیفِ جابه‌جاشده در رابط نباید عددِ مالیات را عوض کند.
    """
    rows = sorted(
        table.brackets,
        key=lambda b: (b.up_to is None, Decimal(str(b.up_to or 0))),
    )
    return [
        {"up_to": None if b.up_to is None else str(b.up_to), "rate": str(b.rate)}
        for b in rows
    ]


def resolve_tax_table(
    db: Session,
    *,
    on: date,
    tax_group_id: UUID | None,
    calculation_type: str = "salary",
) -> TaxTable | None:
    """جدولِ مؤثر در یک تاریخ، برای یک گروه و یک هدفِ محاسبه.

    قطعی است و هیچ‌جا حدس نمی‌زند:

    * فقط جدول‌هایی که `effective_from` آن‌ها از `on` نگذشته؛ تازه‌ترینشان برنده.
    * گروهِ **دقیق** بر گروهِ `NULL` (پیش‌فرض) می‌چربد — پس حکمی که «مناطق محروم»
      دارد جدولِ مناطق محروم را می‌گیرد، و حکمِ بی‌گروه جدولِ پیش‌فرض را.
    * از روی **عنوان** چیزی پیدا نمی‌شود. عنوان نمایشی است.

    `None` یعنی هیچ جدولی برای این ترکیب تعریف نشده — که برای «عیدی» حالتِ
    عادیِ امروز است و معنایش «مالیاتی نیست»، نه «خطا».
    """
    #: **هم‌جنس‌سازی پیش از مقایسه.** فیلترِ SQL رشته را هم می‌فهمد، ولی مقایسه‌ی
    #: پایتونیِ پایین‌تر `UUID == str` را `False` می‌دهد — و آن‌وقت گروهِ دقیق
    #: بی‌صدا به جدولِ پیش‌فرض سُر می‌خورد. یعنی حکمِ «مناطق محروم» مالیاتِ
    #: عادی می‌گرفت، بی هیچ خطایی.
    if tax_group_id is not None and not isinstance(tax_group_id, UUID):
        tax_group_id = UUID(str(tax_group_id))

    candidates = (
        db.query(TaxTable)
        .filter(
            TaxTable.calculation_type == calculation_type,
            TaxTable.effective_from <= on,
            or_(TaxTable.tax_group_id == tax_group_id, TaxTable.tax_group_id.is_(None))
            if tax_group_id is not None
            else TaxTable.tax_group_id.is_(None),
        )
        .order_by(TaxTable.effective_from.desc())
        .all()
    )
    if not candidates:
        return None

    #: گروهِ دقیق اول. بینِ هم‌گروه‌ها، تازه‌ترین تاریخِ اجرا — و ایندکسِ یکتا
    #: تضمین می‌کند دو جدول با همان تاریخ و همان گروه وجود نداشته باشند، پس
    #: انتخاب هیچ‌وقت مبهم نیست.
    exact = [t for t in candidates if t.tax_group_id == tax_group_id]
    pool = exact or [t for t in candidates if t.tax_group_id is None]
    return pool[0] if pool else None


def explain(brackets: list[dict], annual_taxable: Decimal) -> list[BracketStep]:
    """تفکیکِ پله‌به‌پله‌ی یک مبنا — «این عدد از کجا آمد؟».

    فصل صریح است که مالیات نباید فقط یک عدد باشد. این‌جا هیچ‌چیز ذخیره نمی‌شود:
    از پله‌ها و مبنا **بازسازی** می‌شود، پس نمی‌تواند با آن‌ها ناسازگار شود.

    «مبلغ جزء» و «مبلغ کل»ِ فرمِ مرجع همین `tax` و `cumulative`اند.
    """
    from app.services.payroll import _ascending, _round

    steps: list[BracketStep] = []
    if annual_taxable <= 0:
        return steps

    lower = Decimal(0)
    cumulative = Decimal(0)
    for seq, bracket in enumerate(_ascending(brackets), start=1):
        rate = Decimal(str(bracket["rate"]))
        up_to = bracket.get("up_to")
        upper = None if up_to is None else Decimal(str(up_to))

        ceiling = annual_taxable if upper is None else min(annual_taxable, upper)
        consumed = ceiling - lower
        if consumed > 0:
            tax = _round(consumed * rate)
            cumulative += tax
            steps.append(
                BracketStep(
                    seq=seq,
                    lower=lower,
                    upper=upper,
                    rate=rate,
                    consumed=consumed,
                    tax=tax,
                    cumulative=cumulative,
                )
            )

        if upper is None or annual_taxable <= upper:
            break
        lower = upper
    return steps


def assert_scope_free(
    db: Session,
    *,
    table_id: UUID | None,
    effective_from: date,
    calculation_type: str,
    tax_group_id: UUID | None,
) -> None:
    """دامنه‌ی جدول نباید با جدولِ دیگری تصادم کند.

    **پیش از هر `flush`** صدا زده می‌شود: ایندکسِ یکتای پایگاه داده گاردِ نهایی
    است، ولی خطای «کلید تکراری» به کاربر نمی‌گوید کدام جدول مزاحم است و چه کند.

    دو جدولِ هم‌زمان با همان گروه و همان نوعِ محاسبه یعنی حل‌کننده باید بی‌صدا
    یکی را انتخاب کند — دقیقاً چیزی که نباید بشود.
    """
    query = db.query(TaxTable).filter(
        TaxTable.effective_from == effective_from,
        TaxTable.calculation_type == calculation_type,
        TaxTable.tax_group_id.is_(None) if tax_group_id is None else TaxTable.tax_group_id == tax_group_id,
    )
    if table_id is not None:
        query = query.filter(TaxTable.id != table_id)
    clash = query.first()
    if clash is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"جدول دیگری («{clash.title}») با همین تاریخ اجرا، همین گروه مالیاتی و همین نوع "
            "محاسبه وجود دارد. تاریخ اجرا را عوض کنید یا همان جدول را ویرایش کنید.",
        )


def assert_table_sane(db: Session, table: TaxTable) -> None:
    """پله‌های جدول را می‌سنجد — همان قاعده‌ی `PayrollSettingsIn`، همان تابع."""
    from app.schemas.payroll import assert_brackets_sane

    rows = sorted(
        table.brackets,
        key=lambda b: (b.up_to is None, Decimal(str(b.up_to or 0))),
    )
    try:
        assert_brackets_sane([(None if b.up_to is None else Decimal(str(b.up_to)), Decimal(str(b.rate))) for b in rows])
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def table_is_used(db: Session, table_id: UUID) -> bool:
    """آیا فیشی به این جدول استناد کرده است؟"""
    from app.models.payroll import Payslip

    return db.query(Payslip.id).filter(Payslip.tax_table_id == table_id).first() is not None


def eidi_tax(db: Session, amount: Decimal, *, on: date) -> Decimal:
    """مالیاتِ عیدی، از **جدولِ عیدیِ** مؤثرِ همان تاریخ.

    `Decimal(0)` اگر جدولی تعریف نشده — که حالتِ امروزِ کوبیتاست و «مالیاتی
    نیست» معنا می‌دهد، نه خطا.

    عیدی پرداختی است که یک‌بار در سال انجام می‌شود، پس پله‌ها **مستقیم** روی خودِ
    مبلغ اعمال می‌شوند: نه سالانه‌سازی، نه معافیتِ سالانه‌ی حقوق، نه تعدیلِ
    تجمیعی. آن‌ها قواعدِ *حقوقِ ماهانه*اند و جدولِ عیدی جدا است دقیقاً چون
    این‌طور نیست.
    """
    from app.services.payroll import calc_annual_tax

    if amount <= 0:
        return Decimal(0)
    table = resolve_tax_table(db, on=on, tax_group_id=None, calculation_type="eidi")
    if table is None:
        return Decimal(0)
    return calc_annual_tax(amount, bracket_rows(table))


def build_tax_breakdown(db: Session, payslip_id: UUID):
    """تفکیکِ مالیاتِ یک فیش، از روی جدولی که همان لحظه استفاده شد.

    مبنا **سالانه** است و نه ماهانه، چون موتور تعدیلِ تجمیعی می‌کند: مالیاتِ هر
    ماه سهمی از مالیاتِ سالانه است، و تفکیکِ ماهانه‌ی پله‌ها عددی می‌ساخت که با
    هیچ‌چیزِ واقعی جمع نمی‌زد.
    """
    from app.models.payroll import PayrollPeriod, PayrollSettings, Payslip
    from app.schemas.payroll import TaxBreakdownOut, TaxBreakdownStep

    payslip = db.get(Payslip, payslip_id)
    if payslip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فیش یافت نشد")

    period = db.get(PayrollPeriod, payslip.period_id)
    settings = (
        db.query(PayrollSettings).filter(PayrollSettings.year == period.year).first()
        if period is not None
        else None
    )
    exemption = Decimal(settings.tax_exemption_annual) if settings is not None else Decimal(0)

    table = db.get(TaxTable, payslip.tax_table_id) if payslip.tax_table_id else None
    rows = bracket_rows(table) if table is not None else (settings.tax_brackets if settings else [])

    annual_taxable = Decimal(payslip.taxable_pay) * 12
    after_exemption = max(Decimal(0), annual_taxable - exemption)
    group = getattr(table, "tax_group", None) if table is not None else None

    return TaxBreakdownOut(
        payslip_id=payslip.id,
        tax_amount=Decimal(payslip.tax_amount),
        annual_taxable=annual_taxable,
        annual_exemption=exemption,
        tax_table_id=table.id if table is not None else None,
        tax_table_title=table.title if table is not None else "",
        tax_group_name=(getattr(group, "name", "") or "") if group is not None else "",
        steps=[
            TaxBreakdownStep(
                seq=step.seq,
                from_amount=step.lower,
                up_to=step.upper,
                rate=step.rate,
                consumed=step.consumed,
                tax=step.tax,
                cumulative=step.cumulative,
            )
            for step in explain(rows, after_exemption)
        ],
    )


def mirror_default_tax_table(db: Session, *, year: int, brackets) -> TaxTable:
    """پلکانِ فرمِ «تنظیمات حقوق» را در **جدولِ پیش‌فرضِ حقوقِ همان سال** می‌نشاند.

    بی این آینه، سالِ تازه‌ای که فقط از فرمِ تنظیمات ساخته شود هیچ جدولی نمی‌داشت
    و حل‌کننده به مسیرِ میراثی برمی‌گشت — یعنی دو راهِ پیکربندی که از هم عقب
    می‌مانند.

    این **دو حقیقت نمی‌سازد**: نوشتن دو جا انجام می‌شود ولی خواندنِ مالیات فقط از
    جدول است. فرمِ تنظیمات همان «حالتِ ساده»ی همین جدول است؛ گروه و نوعِ محاسبه‌ی
    اختصاصی از صفحه‌ی جداول مالیات می‌آید.

    تاریخِ اجرا اولِ فروردینِ همان سال است — تنها چیزی که از یک *سال* برمی‌آید.
    جدول‌های گروه‌محور دست نمی‌خورند: آن‌ها تصمیمِ صریحِ کاربرند.
    """
    from app.jalali import jalali_to_gregorian

    effective_from = jalali_to_gregorian(year, 1, 1)
    table = (
        db.query(TaxTable)
        .filter(
            TaxTable.effective_from == effective_from,
            TaxTable.calculation_type == "salary",
            TaxTable.tax_group_id.is_(None),
        )
        .first()
    )
    if table is None:
        table = TaxTable(
            title=f"جدول مالیات حقوق {year} — پیش‌فرض",
            effective_from=effective_from,
            tax_group_id=None,
            calculation_type="salary",
        )
        db.add(table)
        db.flush()

    assert_scope_free(
        db,
        table_id=table.id,
        effective_from=table.effective_from,
        calculation_type='salary',
        tax_group_id=None,
    )
    replace_brackets(db, table, [(b.up_to, b.rate) for b in brackets])
    return table


def replace_brackets(db: Session, table: TaxTable, rows: list[tuple[Decimal | None, Decimal]]) -> None:
    """پله‌های جدول را جایگزین می‌کند و بعد می‌سنجدشان.

    **حذف و flush، بعد درج.** بی این ترتیب، SQLAlchemy می‌تواند ردیف‌های تازه را
    پیش از حذفِ قبلی‌ها بفرستد و قیدِ یکتای `(جدول، seq)` وسطِ کار بشکند — یعنی
    ویرایشِ یک جدولِ موجود با همان تعدادِ پله همیشه خطا بدهد.
    """
    table.brackets.clear()
    db.flush()
    table.brackets = [
        TaxTableBracket(seq=index, up_to=up_to, rate=rate)
        for index, (up_to, rate) in enumerate(rows, start=1)
    ]
    db.flush()
    assert_table_sane(db, table)
