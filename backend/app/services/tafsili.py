"""سطحِ اجبارِ تفصیلی و گزارشِ ردیف‌های بی‌تفصیلی.

حسابِ «تفصیلی پذیر» (`Account.accepts_tafsili`) یعنی ردیفِ سندش باید بُعدِ تحلیلی
(`analytic_id`) داشته باشد. سؤال این بود که *چقدر* اجباری — و جوابش را کسب‌وکار
می‌دهد، نه ما:

* **`strict` (اجباری)** — همه‌جا. سندِ دستی و ردیفی که ماژول‌ها می‌سازند (فاکتور،
  انبار، تولید، حقوق) هر دو بدونِ تفصیلی رد می‌شوند. تنها حالتی که واقعاً سوراخ را
  می‌بندد، به این قیمت که یک تیکِ نادرست در چارت می‌تواند ثبتِ فاکتور را متوقف کند.
* **`hybrid` (ترکیبی)** — پیش‌فرض. فقط سندِ دستی مسدود می‌شود؛ ردیفِ ماژول‌ها رد
  می‌شود ولی در گزارش می‌آید.
* **`floating` (شناور)** — هیچ‌چیز مسدود نمی‌شود. همان تصمیمی که برای *ماهیتِ حساب*
  گرفته شده بود: «گزارش، نه گارد».

**گزارش در هر سه حالت کار می‌کند.** این ستونِ فقراتِ طراحی است: انتخابِ کاربر تعیین
می‌کند چه چیزی *مسدود* شود، نه چه چیزی *دیده* شود. حتی در `floating` هم ردیفِ
بی‌تفصیلی نامرئی نمی‌ماند — فقط جلویش گرفته نمی‌شود.

سندِ **برگشتی** هیچ‌وقت مسدود نمی‌شود: ابعادش را عیناً از سندِ اصلی کپی می‌کند، و
اگر ابطال به‌خاطرِ قاعده‌ای که *بعد از* ثبتِ اصل سخت‌گیرتر شده رد شود، کاربر در
سندی گیر می‌افتد که نه می‌تواند نگه دارد نه برگرداند.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.tenant import Tenant
from app.tenant_context import session_tenant

#: حالت‌های اجبار، از سخت‌گیر به آزاد.
TAFSILI_MODES = ("strict", "hybrid", "floating")

#: NULL روی مستأجر یعنی همین — و همین رفتارِ پیش از افزودنِ این تنظیم است، پس
#: مهاجرتِ ۰۰۸۹ هیچ کسب‌وکاری را تکان نمی‌دهد.
DEFAULT_TAFSILI_MODE = "hybrid"

TAFSILI_MODE_LABELS = {
    "strict": "اجباری",
    "hybrid": "ترکیبی",
    "floating": "شناور",
}

TAFSILI_MODE_HINTS = {
    "strict": (
        "هیچ ردیفی — نه دستی، نه از فاکتور و انبار و تولید — بدونِ تفصیلی ثبت نمی‌شود. "
        "کامل‌ترین گزارشِ تفصیلی را می‌دهد، ولی تیکِ «تفصیلی پذیر» روی حسابی که "
        "ماژول‌ها به آن سند می‌زنند می‌تواند ثبتِ فاکتور را متوقف کند."
    ),
    "hybrid": (
        "سندِ دستی بدونِ تفصیلی ثبت نمی‌شود، ولی ردیفی که ماژول‌ها می‌سازند رد می‌شود "
        "و فقط در گزارش می‌آید. حالتِ میانه و پیش‌فرض."
    ),
    "floating": (
        "هیچ‌چیز مسدود نمی‌شود؛ ردیف‌های بی‌تفصیلی فقط در گزارش دیده می‌شوند. "
        "همان رویه‌ای که برای «حساب‌های خلافِ ماهیت» هم داریم."
    ),
}

#: پیامدِ هر حالت، تفکیک‌شده — تا رابط بتواند دقیقاً بگوید «اگر این را بزنی چه
#: می‌شود» به‌جای یک جمله‌ی کلی. کلیدها همان سه چیزی‌اند که واقعاً فرق می‌کنند.
TAFSILI_MODE_EFFECTS = {
    "strict": {
        "manual": "سندِ دستی بدونِ تفصیلی ثبت نمی‌شود.",
        "module": "فاکتور، انبار، تولید و حقوق هم بدونِ تفصیلی ثبت نمی‌شوند و خطا می‌گیرند.",
        "contact": (
            "**هر طرف حسابِ تازه حتماً کدِ تفصیلی می‌گیرد.** فرم کدِ آزادِ بعدی را "
            "پیشنهاد می‌دهد و اگر خالی بگذارید سرور خودش یکی می‌سازد؛ عنوانِ تفصیلی "
            "هم از نام و نام خانوادگی پیشنهاد می‌شود و اگر تکراری باشد قرمز می‌شود."
        ),
        "report": "گزارش تقریباً خالی می‌ماند؛ هرچه در آن باشد مربوط به پیش از این تنظیم است.",
        "warning": (
            "اگر حسابی را «تفصیلی پذیر» کنید که ماژول‌ها خودکار به آن سند می‌زنند "
            "(مثلِ حساب‌های دریافتنی)، ثبتِ فاکتور متوقف می‌شود تا تفصیلی تعیین شود."
        ),
    },
    "hybrid": {
        "manual": "سندِ دستی بدونِ تفصیلی ثبت نمی‌شود.",
        "module": "ردیفی که ماژول‌ها می‌سازند رد می‌شود و چیزی متوقف نمی‌گردد.",
        "contact": (
            "**طرف حساب می‌تواند کدِ تفصیلی بگیرد ولی مجبور نیست.** فیلدهای کد و "
            "عنوانِ تفصیلی در فرم هستند و کدِ پیشنهادی هم می‌آید؛ خالی گذاشتنشان "
            "طرف‌حساب را رد نمی‌کند."
        ),
        "report": "ردیف‌های ماژول‌ها که تفصیلی ندارند در گزارش فهرست می‌شوند.",
        "warning": (
            "سوراخ باز می‌ماند ولی دیده می‌شود: گزارشِ تفصیلی ممکن است ناقص باشد و "
            "گزارشِ «ردیف‌های بدونِ تفصیلی» می‌گوید چقدرش جا افتاده."
        ),
    },
    "floating": {
        "manual": "سندِ دستی هم بدونِ تفصیلی ثبت می‌شود؛ فیلدِ تفصیلی هست ولی اجباری نیست.",
        "module": "ردیفِ ماژول‌ها هم آزاد است.",
        "contact": (
            "**فیلدهای تفصیلیِ طرف حساب پنهان می‌شوند.** وقتی هیچ‌جا تفصیلی خواسته "
            "نمی‌شود، خواستنش موقعِ ساختِ طرف‌حساب فقط دو فیلدِ بی‌مصرف است. "
            "طرف‌حساب‌هایی که از قبل تفصیلی دارند، آن را نگه می‌دارند."
        ),
        "report": "تنها جایی که ردیف‌های بی‌تفصیلی دیده می‌شوند همین گزارش است.",
        "warning": (
            "هیچ‌چیز مسدود نمی‌شود، پس تکمیلِ تفصیلی کاملاً به عهده‌ی کاربر است. "
            "همان رویه‌ای که برای «حساب‌های خلافِ ماهیت» هم داریم."
        ),
    },
}

#: سندی که ماژول ساخته، نه کاربر. `manual` تنها منبعی است که آدم پشتش نشسته و
#: می‌تواند همان لحظه تفصیلی را انتخاب کند.
MANUAL_SOURCE = "manual"


def get_mode(db: Session) -> str:
    """حالتِ این کسب‌وکار. بدونِ زمینه‌ی مستأجر، پیش‌فرض — تا اسکریپت و seed نشکنند."""
    tenant_id = session_tenant(db)
    if tenant_id is None:
        return DEFAULT_TAFSILI_MODE
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        return DEFAULT_TAFSILI_MODE
    return tenant.tafsili_enforcement or DEFAULT_TAFSILI_MODE


def set_mode(tenant: Tenant, mode: str) -> str:
    if mode not in TAFSILI_MODES:
        raise ValueError("سطحِ اجبارِ تفصیلی نامعتبر است")
    tenant.tafsili_enforcement = mode
    return mode


def _blocks(mode: str, source_type: str) -> bool:
    """آیا با این حالت، ردیفِ چنین سندی باید مسدود شود؟"""
    if source_type.startswith("void_"):
        return False  # سندِ برگشتی هرگز — ابعادش کپیِ اصل است
    if mode == "floating":
        return False
    if mode == "strict":
        return True
    return source_type == MANUAL_SOURCE


def assert_lines_have_tafsili(
    db: Session,
    pairs: list[tuple[UUID, UUID | None]],
    *,
    source_type: str,
) -> None:
    """اگر حالت اجازه ندهد، ردیفِ بی‌تفصیلی روی حسابِ تفصیل‌پذیر را رد می‌کند.

    `pairs` باید (شناسه‌ی حساب، تفصیلیِ **نهایی**) باشد — یعنی پس از ارث‌بریِ سطحِ
    سند؛ وگرنه سندی که تفصیلی‌اش را یک‌بار بالا داده رد می‌شد.
    """
    mode = get_mode(db)
    if not _blocks(mode, source_type):
        return

    missing_ids = {account_id for account_id, analytic_id in pairs if analytic_id is None}
    if not missing_ids:
        return
    needs = (
        db.query(Account)
        .filter(Account.id.in_(missing_ids), Account.accepts_tafsili.is_(True))
        .order_by(Account.code)
        .all()
    )
    if not needs:
        return

    names = "، ".join(f"{a.code} {a.name}" for a in needs)
    if source_type == MANUAL_SOURCE:
        detail = f"این حساب‌ها تفصیلی‌پذیرند و ردیفشان بدونِ تفصیلی ثبت نمی‌شود: {names}"
    else:
        #: پیامِ ماژول باید بگوید *کجا* تنظیم عوض می‌شود، وگرنه کاربر با فاکتوری
        #: روبه‌رو می‌شود که ثبت نمی‌شود و دلیلش را در چارت نمی‌بیند.
        detail = (
            f"سطحِ اجبارِ تفصیلی روی «اجباری» است و این حساب‌ها تفصیلی ندارند: {names}. "
            "یا تفصیلی را روی حساب تعیین کنید، یا از تنظیمات ← کدینگ سطحِ اجبار را "
            "به «ترکیبی» تغییر دهید."
        )
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail)


def assert_entry_has_tafsili(db: Session, entry: JournalEntry) -> None:
    """همان گارد، ولی روی سندی که ردیف‌هایش از قبل ساخته شده‌اند.

    مسیرهایی که مستقیم `JournalEntry(...)` می‌سازند (انبار، تولید، انبارگردانی) از
    این در می‌آیند؛ مسیرهای عبوری از `make_journal_entry` هم همین را صدا می‌زنند.
    """
    assert_lines_have_tafsili(
        db,
        [(line.account_id, line.analytic_id) for line in entry.lines],
        source_type=entry.source_type or "",
    )


def contact_tafsili_requirement(db: Session) -> str:
    """طرف حساب در این حالت چه نیازی به تفصیلی دارد: required | optional | hidden.

    قاعده‌ای که کاربر گذاشت: در «اجباری» و «ترکیبی» می‌شود کدِ تفصیلی داد — در
    اولی اجباری، در دومی اختیاری. در «شناور» اصلاً پرسیده نمی‌شود، چون وقتی هیچ‌جا
    تفصیلی خواسته نمی‌شود، خواستنش موقعِ ساختِ طرف‌حساب دو فیلدِ بی‌مصرف است.
    """
    return {"strict": "required", "hybrid": "optional", "floating": "hidden"}[get_mode(db)]


def suggest_contact_tafsili_code(db: Session) -> str:
    """کدِ آزادِ بعدیِ تفصیلی — تا فرم حدس نزند و کدِ تکراری نفرستد.

    شماره‌ای ساده و پیوسته، نه `next_document_number`: تفصیلی سندِ شماره‌دار نیست و
    بی‌شماره‌شدنِ یک کد (چون کاربر فرم را نیمه رها کرده) هیچ ایرادی ندارد. آنچه
    اهمیت دارد فقط آزاد بودنِ کد است، و آن را در لحظه‌ی ساخت هم دوباره می‌سنجیم.
    """
    from app.models.analytic import AnalyticAccount

    used = {code for (code,) in db.query(AnalyticAccount.code).all()}
    n = len(used) + 1
    while str(n) in used:
        n += 1
    return str(n)


def tafsili_title_taken(db: Session, title: str, exclude_id: UUID | None = None) -> bool:
    """آیا عنوانِ تفصیلی از قبل استفاده شده؟

    عنوانِ تکراری *ممنوع* نیست — دو «رجبی بهنام» می‌توانند واقعاً وجود داشته باشند —
    ولی کاربر باید **بداند**، وگرنه در فهرستِ تفصیلی دو ردیفِ هم‌نام می‌بیند و
    نمی‌فهمد کدام کدام است. پس فرم قرمزش می‌کند، نه اینکه ردش کند.
    """
    from app.models.analytic import AnalyticAccount

    title = (title or "").strip()
    if not title:
        return False
    query = db.query(AnalyticAccount.id).filter(AnalyticAccount.name == title)
    if exclude_id is not None:
        query = query.filter(AnalyticAccount.id != exclude_id)
    return query.first() is not None


def resolve_contact_analytic(
    db: Session,
    user,
    *,
    code: str | None,
    title: str | None,
    #: `None` یعنی «نفرستاده شده»، رشته‌ی خالی یعنی «پاکش کن». در ویرایشِ جزئی این
    #: دو یکی نیستند و یکی‌گرفتنشان عنوانِ لاتینِ ثبت‌شده را بی‌خبر پاک می‌کرد.
    title2: str | None = "",
    fallback_title: str = "",
    existing_id: UUID | None = None,
):
    """تفصیلیِ طرف حساب را می‌سازد یا برمی‌گرداند، طبقِ حالتِ فعلی.

    اگر `existing_id` بیاید همان استفاده می‌شود (ویرایشِ طرف‌حسابی که از قبل
    تفصیلی دارد) و کد/عنوانش به‌روز می‌شود. وگرنه کدِ داده‌شده تفصیلیِ تازه‌ای
    می‌سازد.

    در حالتِ `hidden` هیچ تفصیلی‌ای ساخته نمی‌شود ولی تفصیلیِ *موجود* هم حذف
    نمی‌شود: عوض‌کردنِ یک تنظیم نباید داده‌ای را که قبلاً ثبت شده پاک کند.
    """
    from app.models.analytic import AnalyticAccount

    requirement = contact_tafsili_requirement(db)
    code = (code or "").strip()
    #: عنوانی که *کاربر* داده، پیش از جایگزین‌شدن با نامِ طرف‌حساب. این تفاوت مهم
    #: است: نامِ جایگزین همیشه پر است، پس اگر مبنا قرار می‌گرفت هر طرف‌حسابی — حتی
    #: در حالتِ «ترکیبی» و بدونِ خواستِ کاربر — تفصیلی می‌گرفت.
    explicit_title = bool((title or "").strip())
    title = (title or "").strip() or fallback_title.strip()

    if existing_id is not None:
        row = db.get(AnalyticAccount, existing_id)
        if row is not None:
            if code and code != row.code:
                _assert_analytic_code_free(db, code, exclude_id=row.id)
                row.code = code
            if title:
                row.name = title
            if title2 is not None:
                row.name2 = title2.strip()
            return row

    if requirement == "hidden":
        return None
    if not code:
        #: کدِ خالی یعنی «خودت بده»، نه خطا — شماره‌ی تفصیلی ارجاعِ داخلی است و
        #: کاربر معمولاً حرفی درباره‌اش ندارد. در حالتِ «ترکیبی» هم اگر کاربر
        #: *عنوان* داده باشد، نیتش روشن است: تفصیلی می‌خواهد. تنها حالتی که چیزی
        #: ساخته نمی‌شود این است که هر دو خالی باشند و اجباری هم نباشد.
        if requirement == "required" or explicit_title:
            code = suggest_contact_tafsili_code(db)
        else:
            return None

    _assert_analytic_code_free(db, code)
    row = AnalyticAccount(
        code=code,
        name=title or fallback_title or code,
        name2=(title2 or "").strip(),
        group_name="طرف حساب",
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    return row


def _assert_analytic_code_free(db: Session, code: str, exclude_id: UUID | None = None) -> None:
    from app.models.analytic import AnalyticAccount

    query = db.query(AnalyticAccount).filter(AnalyticAccount.code == code)
    if exclude_id is not None:
        query = query.filter(AnalyticAccount.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"کدِ تفصیلیِ «{code}» قبلاً استفاده شده است"
        )


def find_missing_tafsili(
    db: Session, date_from: date | None = None, date_to: date | None = None
) -> list[dict]:
    """ردیف‌هایی که روی حسابِ تفصیل‌پذیر نشسته‌اند ولی تفصیلی ندارند.

    **در هر سه حالت کار می‌کند** — حتی وقتی هیچ‌چیز مسدود نمی‌شود. کارش این است که
    سوراخِ گزارشِ تفصیلی را نمایان کند: جمعِ حساب درست است، ولی تفکیکش ناقص، و
    بدونِ این گزارش هیچ‌جا نمی‌گوید چقدرش جا افتاده.

    سندِ باطل‌شده شمرده نمی‌شود؛ اثرِ مالی‌اش صفر شده و آوردنش فقط نویز است.
    """
    query = (
        db.query(
            Account.id,
            Account.code,
            Account.name,
            JournalEntry.id,
            JournalEntry.number,
            JournalEntry.entry_date,
            JournalEntry.source_type,
            JournalLine.debit,
            JournalLine.credit,
            JournalLine.description,
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(
            Account.accepts_tafsili.is_(True),
            JournalLine.analytic_id.is_(None),
            JournalEntry.voided_at.is_(None),
        )
    )
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)

    rows = query.order_by(JournalEntry.entry_date.desc(), Account.code).all()
    return [
        {
            "account_id": account_id,
            "account_code": code,
            "account_name": name,
            "entry_id": entry_id,
            "entry_number": number,
            "entry_date": entry_date,
            "source_type": source_type,
            #: منبع را نگه می‌داریم چون در حالتِ «ترکیبی» تقریباً همه‌ی ردیف‌های
            #: این گزارش از ماژول‌ها می‌آیند — و همان است که باید دیده شود.
            "is_manual": source_type == MANUAL_SOURCE,
            "debit": debit,
            "credit": credit,
            "description": description,
        }
        for account_id, code, name, entry_id, number, entry_date, source_type, debit, credit, description in rows
    ]
