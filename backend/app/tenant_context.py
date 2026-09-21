"""مستأجر جاری، و چسباندنش به تراکنش پایگاه‌داده.

**چرا ContextVar و نه متغیر ماژول:** هر درخواست باید مستأجر خودش را ببیند. متغیر
سراسری بین درخواست‌های هم‌زمان مشترک می‌شود و دقیقاً همان نشتی را می‌سازد که RLS
قرار بود جلویش را بگیرد.

**چرا after_begin و نه یک‌بار در ابتدای درخواست:** مقدار با SET LOCAL ست می‌شود که
به تراکنش محدود است. هر بار که تراکنش جدیدی شروع شود — از جمله بعد از هر commit —
مقدار از بین رفته و باید دوباره ست شود. این رویداد در شروع هر تراکنش شلیک می‌شود،
پس حتی اگر جایی وسط کار commit کند، تراکنش بعدی باز هم مستأجر درست را دارد.

**چرا SET LOCAL و نه SET:** SET ساده به کل اتصال می‌چسبد و اتصال به connection pool
برمی‌گردد. یعنی درخواست بعدی — که می‌تواند مال مستأجر دیگری باشد — همان مقدار را
به ارث می‌برد. این بدترین حالت شکست ممکن در این سیستم است.

**چرا set_config و نه رشته‌سازی:** SET LOCAL پارامتر bind نمی‌پذیرد، پس تنها راهش
درج مقدار داخل متن SQL بود. set_config(name, value, true) دقیقاً همان کار را می‌کند
ولی مقدار را به‌عنوان پارامتر می‌گیرد.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.tenancy import TENANT_SETTING

_current_tenant: ContextVar[UUID | None] = ContextVar("current_tenant", default=None)

#: کلید نگهداری مستأجر روی خودِ Session
SESSION_KEY = "cubita_tenant_id"

#: نگهبانِ «کلید اصلاً نبود» — با «کلید بود و None بود» فرق دارد، و `tenant_scope`
#: باید هر دو را درست برگرداند.
_MISSING = object()


def set_current_tenant(tenant_id: UUID | None) -> None:
    _current_tenant.set(tenant_id)


def get_current_tenant() -> UUID | None:
    return _current_tenant.get()


def bind_session_tenant(db: Session, tenant_id: UUID | None) -> None:
    """مستأجر را روی خودِ Session می‌نشاند.

    **چرا نه فقط ContextVar:** FastAPI اندپوینت‌های sync را در threadpool اجرا
    می‌کند و هر dependency در نخ خودش با یک *کپی* از زمینه کار می‌کند. مقداری که
    در get_principal ست شود به نخ اندپوینت نمی‌رسد. این باعث می‌شد خواندن‌ها کار
    کنند (آن‌ها زمینه را از اتصال DB می‌گیرند) ولی هر نوشتنی بشکند — یعنی بدترین
    نوع باگ: نامرئی در تست‌های خواندنی، مرگبار در production.

    Session تنها چیزی است که به‌صورت صریح در تمام مسیر درخواست پاس داده می‌شود،
    پس زمینه به آن می‌چسبد. ContextVar به‌عنوان fallback برای اسکریپت‌ها و
    مسیرهایی که Session در دست ندارند باقی می‌ماند.
    """
    db.info[SESSION_KEY] = tenant_id
    _current_tenant.set(tenant_id)


def session_tenant(db: Session) -> UUID | None:
    return db.info.get(SESSION_KEY) or _current_tenant.get()


def require_session_tenant(db: Session) -> UUID:
    tenant_id = session_tenant(db)
    if tenant_id is None:
        raise RuntimeError("مستأجر جاری ست نشده — این مسیر نباید بدون زمینه‌ی مستأجر اجرا شود")
    return tenant_id


@contextmanager
def tenant_scope(db: Session, tenant_id: UUID | None):
    """مستأجر را برای یک بلوک ست می‌کند و روی همان تراکنشِ باز هم اعمالش می‌کند.

    ست کردن ContextVar به‌تنهایی کافی نیست وقتی تراکنش از قبل شروع شده: after_begin
    دیگر شلیک نمی‌شود، پس مقدار را همین‌جا هم روی اتصال جاری می‌نشانیم.

    **و در پایان هر سه چیز برمی‌گردند، نه فقط ContextVar.** تا امروز `finally`
    فقط `_current_tenant.reset(token)` می‌زد؛ `db.info[SESSION_KEY]` و متغیرِ
    `app.tenant_id`ِ خودِ Postgres — که سیاستِ RLS رویش می‌نشیند — دست‌نخورده
    می‌ماندند. یعنی بعد از خروج از بلوک، هم `session_tenant()` و هم پایگاه‌داده
    فکر می‌کردند مستأجرِ جاری هنوز مستأجرِ **داخلی** است.

    نگزیده بود چون هیچ فراخوانی بعد از بلوک کارِ مستأجرمحور نمی‌کرد: `_fulfill`
    بعدش فقط جدولِ سراسریِ سفارش را می‌نویسد، و دو فراخوانِ دیگر حلقه‌اند و هر
    دور مقدار را بازنویسی می‌کنند. ولی «هنوز نگزیده» با «امن» یکی نیست — اولین
    کدی که بعد از بلوک یک کوئریِ مستأجرمحور بزند، آن را زیرِ مستأجرِ اشتباه
    می‌زند. با تست بازتولید شد ([test_tenant_scope_restores](../../tests/test_tenant_scope_restores.py)).
    """
    token = _current_tenant.set(tenant_id)
    #: `_MISSING` لازم است چون «نبودِ کلید» با «کلیدِ None» یکی نیست: اولی یعنی
    #: هرگز ست نشده، دومی یعنی صریحاً بی‌مستأجر.
    previous = db.info.get(SESSION_KEY, _MISSING)
    db.info[SESSION_KEY] = tenant_id
    try:
        apply_tenant_to_transaction(db, tenant_id)
        yield
    finally:
        _current_tenant.reset(token)
        if previous is _MISSING:
            db.info.pop(SESSION_KEY, None)
        else:
            db.info[SESSION_KEY] = previous
        #: زمینه‌ی پایگاه‌داده هم باید برگردد، وگرنه RLS زیرِ مستأجرِ اشتباه
        #: می‌ماند حتی وقتی کد درست فکر می‌کند.
        apply_tenant_to_transaction(db, session_tenant(db))


def apply_tenant_to_transaction(db: Session, tenant_id: UUID | None) -> None:
    db.execute(text("SELECT set_config(:k, :v, true)"), {"k": TENANT_SETTING, "v": str(tenant_id or "")})


@event.listens_for(Session, "after_begin")
def _bind_tenant_to_new_transaction(session, transaction, connection) -> None:
    # از Session خوانده می‌شود نه ContextVar، به همان دلیلی که در bind_session_tenant
    # توضیح داده شد: زیر threadpool، ContextVar قابل اعتماد نیست.
    tenant_id = session.info.get(SESSION_KEY) or _current_tenant.get()
    if tenant_id is None:
        return
    connection.execute(text("SELECT set_config(:k, :v, true)"), {"k": TENANT_SETTING, "v": str(tenant_id)})


@event.listens_for(Session, "before_flush")
def _stamp_tenant_on_new_rows(session, flush_context, instances) -> None:
    """مستأجر را روی هر ردیف جدید می‌نشاند.

    بدون این، هر سرویس باید دستی tenant_id بدهد و کافی بود یک جا فراموش شود تا
    نوشتن با خطای RLS شکست بخورد (یا بدتر، اگر روزی سیاست شل شود، ردیف بی‌صاحب
    بسازد). اینجا یک بار انجام می‌شود و برای هر ۳۴ مدل کار می‌کند.

    RLS همچنان لایه‌ی پشتیبان است نه جایگزین: اگر این مهر به هر دلیلی نخورد،
    WITH CHECK در پایگاه‌داده جلوی نوشتن را می‌گیرد.

    مدلی که `__tenant_stamp__ = False` بگذارد کنار گذاشته می‌شود. تنها مصرفش امروز
    `StaffAuditLog` است: ستونِ `tenant_id` دارد ولی سراسری است، و ردیفی که واقعاً
    مستأجر ندارد (مثلِ «ورودِ کارمندِ ستاد») نباید بی‌صدا مهرِ مستأجرِ فعال بخورد —
    ردِ کاری که به مشتریِ بی‌ربط نسبت داده شود، بدتر از نبودنش است.
    """
    tenant_id = session.info.get(SESSION_KEY) or _current_tenant.get()
    if tenant_id is None:
        return
    for obj in session.new:
        if getattr(type(obj), "__tenant_stamp__", True) is False:
            continue
        if hasattr(type(obj), "tenant_id") and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tenant_id


def current_tenant_in_db(db: Session) -> str | None:
    """مقداری که پایگاه‌داده واقعاً می‌بیند — برای تست و عیب‌یابی."""
    return db.execute(text("SELECT current_setting(:k, true)"), {"k": TENANT_SETTING}).scalar()
