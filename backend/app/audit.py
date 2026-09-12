"""ثبت خودکار ردِ حسابرسی روی تغییرهای مالی.

**چرا خودکار و نه فراخوانی صریح در هر سرویس:** فراخوانی صریح یعنی هر مسیر جدیدی که
کسی اضافه کند باید یادش بماند. برای یک رد حسابرسی که ارزش قانونی دارد، «یادش بماند»
حالت شکست است، نه ریسک قابل قبول. اینجا یک بار به رویداد flush وصل می‌شود و برای هر
مدل ثبت‌شده کار می‌کند — همان الگویی که مهر مستأجر در tenant_context.py دارد.

**چرا فقط سند و نه ردیف‌های سند:** ثبت یک فاکتور ده‌ردیفه نباید یازده رکورد
حسابرسی بسازد. ردیف‌ها جزئی از سندند و با خودِ سند ثبت می‌شوند؛ رکورد سطح سند همان
چیزی است که کسی دنبالش می‌گردد.

**چرا ابطال از تغییر جدا شده:** ابطال جایی است که تقلب پنهان می‌شود. اگر با بقیه‌ی
UPDATEها در یک دسته بیفتد، پیدا کردنش نیاز به فیلتر روی محتوای JSON دارد؛ به‌عنوان
action مستقل، یک کوئری ساده است.
"""
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.observability import request_id_var

#: کلید نگهداری کاربر روی خودِ Session — به همان دلیلی که مستأجر آنجا نگه داشته
#: می‌شود: زیر threadpool، ContextVar بین dependency و اندپوینت منتقل نمی‌شود.
ACTOR_KEY = "cubita_audit_actor"

#: کلیدِ خاموش‌کردنِ موقتِ ثبتِ خودکار. تنها مصرفش عملیاتی است که برای دور زدنِ یک
#: قیدِ دیتابیس چندمرحله‌ای می‌نویسد و مراحلِ میانی‌اش واقعیتِ کسب‌وکاری نیستند —
#: بازشماره‌گذاری. شرحِ کامل بالای `suppressed`.
SUPPRESS_KEY = "cubita_audit_suppressed"

#: متغیر جلسه‌ای که تنها راه مجاز حذف رکورد حسابرسی است (offboarding مستأجر).
PURGE_SETTING = "app.audit_purge"

GUARD_FN = "audit_log_append_only"
GUARD_TRIGGER = "audit_log_no_update_delete"


def append_only_statements(table: str = "audit_log", trigger: str | None = None) -> list[str]:
    """DDL ای که یک جدول را در سطح پایگاه‌داده فقط‌افزودنی می‌کند.

    اینجا زندگی می‌کند و نه فقط داخل مهاجرت، به همان دلیلی که rls_statements در
    tenancy.py است: تست‌ها schema را با create_all می‌سازند و create_all از trigger
    خبر ندارد. اگر این DDL فقط در مهاجرت بود، تست‌ها روی جدولی اجرا می‌شدند که
    قابل ویرایش است — یعنی دقیقاً همان خاصیتی که کل ارزش این جدول است، سنجیده
    نمی‌شد.

    **پارامتری شد چون `check_events` هم همین خاصیت را می‌خواهد** (§۴۷ فصلِ
    عملیاتِ چک): تاریخچه‌ی چک نباید بازنویسی شود تا وضعیتِ فعلی تمیزتر به‌نظر
    برسد. تابعِ گاردْ مشترک می‌ماند، پس دریچه‌ی `app.audit_purge` — که فقط در
    حذفِ مستأجر و بازیابیِ پشتیبان باز می‌شود — برای هر دو جدول یک‌جور کار می‌کند.
    """
    trigger = trigger or f"{table}_no_update_delete"
    return [
        f"""
        CREATE OR REPLACE FUNCTION {GUARD_FN}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('{PURGE_SETTING}', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'این دفتر فقط‌افزودنی است؛ % مجاز نیست', TG_OP
                USING ERRCODE = 'check_violation';
        END;
        $$ LANGUAGE plpgsql;
        """,
        f"DROP TRIGGER IF EXISTS {trigger} ON {table}",
        f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {GUARD_FN}()",
    ]

#: ستون‌هایی که تغییرشان رویداد حسابرسی نیست.
NOISE_FIELDS = frozenset({"updated_at", "created_at"})


def audited_models() -> dict[type, str]:
    """مدل‌های تحت حسابرسی و برچسب فارسی‌شان.

    داخل تابع import می‌شود تا حلقه‌ی import نسازد: مدل‌ها به app.database وابسته‌اند
    و این ماژول به مدل‌ها.
    """
    from app.models.accounting import JournalEntry
    from app.models.advanced_inventory import PriceList
    from app.models.banking import Check
    from app.models.invoices import PurchaseInvoice, SalesInvoice, WarehouseIssue, WarehouseReceipt
    from app.models.payroll import Payslip
    from app.models.period_close import FiscalPeriodClose
    from app.models.payment import Payment
    from app.models.receipt import Receipt
    from app.models.returns import PurchaseReturn, SalesReturn
    from app.models.settlement import Settlement
    from app.models.transfers import StockTransfer
    from app.models.treasury import TreasuryTransaction

    return {
        JournalEntry: "سند حسابداری",
        SalesInvoice: "فاکتور فروش",
        PurchaseInvoice: "فاکتور خرید",
        WarehouseReceipt: "رسید انبار خرید",
        WarehouseIssue: "خروج انبار فروش",
        SalesReturn: "برگشت از فروش",
        PurchaseReturn: "برگشت از خرید",
        StockTransfer: "انتقال انبار",
        Payslip: "فیش حقوقی",
        TreasuryTransaction: "تراکنش خزانه",
        #: چک تا امروز در این فهرست نبود — موجودیتی با غنی‌ترین چرخه‌ی عمرِ
        #: خزانه، تنها موجودیتی بود که هیچ ردِ حسابرسی‌ای نمی‌گذاشت.
        Check: "چک",
        FiscalPeriodClose: "بستن دوره",
        Receipt: "رسید دریافت",
        Payment: "اعلامیه پرداخت",
        #: تسویه سندِ حسابداری نمی‌زند، پس دفتر هیچ ردی از تغییرش نشان نمی‌دهد —
        #: و دقیقاً به همین دلیل حسابرسی‌اش واجب‌تر است، نه کمتر (§۴۹).
        Settlement: "تسویه حساب طرف مقابل",
        #: اعلامیه‌ی قیمت هم سند نمی‌زند و هم **سیاست** است: قیمتِ فروش، سقفِ
        #: تخفیف و اینکه فروشنده اصلاً حق دارد نرخ را عوض کند یا نه. تا امروز
        #: تنها تصمیمِ مالیِ شرکت بود که تغییرش هیچ ردی نمی‌گذاشت — و مسیری
        #: وجود داشت که کلِ ماتریس را بی‌صدا پاک می‌کرد (فصلِ اعلامیه قیمت، §۴۰ §۸۵).
        #:
        #: ردیف‌های اعلامیه عمداً این‌جا نیستند: قاعده‌ی این فایل «یک رکورد برای
        #: سند، نه برای هر ردیف» است. تغییرِ گروهیِ فی به‌جایش یک رکوردِ
        #: قبل/بعد با `record_change` می‌سازد.
        PriceList: "اعلامیه قیمت",
    }


def bind_session_actor(db: Session, user) -> None:
    """کاربر جاری را روی Session می‌نشاند تا رویدادِ flush بداند چه کسی مسئول است."""
    db.info[ACTOR_KEY] = (user.id, user.email) if user is not None else None


def _actor(session: Session) -> tuple[uuid.UUID | None, str]:
    actor = session.info.get(ACTOR_KEY)
    return actor if actor else (None, "سیستم")


def _jsonable(value):
    """مقدار را به چیزی تبدیل می‌کند که JSONB بپذیرد.

    Decimal به رشته می‌رود و نه float: مبلغ مالی که از float عبور کند دقتش را از
    دست می‌دهد، و رد حسابرسی‌ای که عدد را کمی جابه‌جا کند بدتر از نبودنش است.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    #: مقدارهای تودرتو (فهرستِ قبل/بعدِ یک عملیاتِ گروهی) بازگشتی تبدیل می‌شوند،
    #: نه با `str()` — وگرنه یک ردِ حسابرسیِ ساخت‌یافته به یک متنِ خوانانشدنی
    #: تبدیل می‌شد، و اگر اصلاً تبدیل نمی‌شد درجِ رکورد با TypeError می‌ترکید.
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def _changed_fields(obj) -> dict:
    """ستون‌هایی که واقعاً عوض شده‌اند، با مقدار قبل و بعد."""
    changes: dict[str, dict] = {}
    state = inspect(obj)
    for attr in state.mapper.column_attrs:
        if attr.key in NOISE_FIELDS:
            continue
        history = state.attrs[attr.key].history
        if not history.has_changes():
            continue
        before = history.deleted[0] if history.deleted else None
        after = history.added[0] if history.added else None
        changes[attr.key] = {"from": _jsonable(before), "to": _jsonable(after)}
    return changes


def _describe(label: str, obj, action: str) -> str:
    number = getattr(obj, "number", None)
    who = f"{label} شماره {number}" if number is not None else label
    return {
        "create": f"{who} ثبت شد",
        "void": f"{who} باطل شد",
        "finalize": f"{who} دائم شد",
        "update": f"{who} ویرایش شد",
        "delete": f"{who} حذف شد",
    }[action]


def _entry(session: Session, obj, label: str, action: str, changes: dict | None) -> AuditLog:
    actor_id, actor_email = _actor(session)
    return AuditLog(
        tenant_id=getattr(obj, "tenant_id", None),
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=type(obj).__name__,
        entity_id=obj.id,
        summary=_describe(label, obj, action),
        changes=changes or None,
        request_id=request_id_var.get(),
    )


@event.listens_for(Session, "before_flush")
def _record_financial_changes(session: Session, flush_context, instances) -> None:
    """هر تغییر مالیِ این flush را به رکورد حسابرسی تبدیل می‌کند.

    before_flush جای درستش است چون هنوز می‌شود به session اضافه کرد و تاریخچه‌ی
    تغییرها هنوز پاک نشده. در after_flush هر دو از دست رفته‌اند.
    """
    if session.info.get(SUPPRESS_KEY):
        return

    registry = audited_models()
    if not registry:
        return

    pending: list[AuditLog] = []

    for obj in session.new:
        label = registry.get(type(obj))
        if label is None:
            continue
        # شناسه در لحظه‌ی INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این، هر
        # رکورد حسابرسی entity_id تهی می‌گرفت — همان باگی که در stock_ledger
        # اتفاق افتاده بود.
        if obj.id is None:
            obj.id = uuid.uuid4()
        pending.append(_entry(session, obj, label, "create", None))

    for obj in session.dirty:
        label = registry.get(type(obj))
        if label is None:
            continue
        changes = _changed_fields(obj)
        if not changes:
            continue
        # ابطال یک UPDATE معمولی نیست و نباید لای بقیه گم شود.
        #
        # دائم‌شدن هم همین‌طور، و به همان دلیل: لحظه‌ای که سند وارد سابقه‌ی رسمی
        # می‌شود دومین رویدادِ مهمِ چرخه‌ی عمر است. با `update` ثبت می‌شد و خلاصه‌اش
        # می‌گفت «… ویرایش شد» — که غلط توصیف می‌کند، چون هیچ‌چیز ویرایش نشده.
        # سؤالِ «چه کسی این سند را نهایی کرد؟» جوابش فیلتر روی JSONِ changes بود.
        #
        # ترتیب مهم است: ابطال اول. سندی که هم‌زمان باطل و دائم شود وجود ندارد،
        # ولی اگر روزی پیش بیاید «باطل شد» خبرِ مهم‌تری است.
        if "voided_at" in changes and changes.get("voided_at", {}).get("from") is None:
            action = "void"
        elif changes.get("status", {}).get("to") == "permanent":
            action = "finalize"
        else:
            action = "update"
        pending.append(_entry(session, obj, label, action, changes))

    for obj in session.deleted:
        label = registry.get(type(obj))
        if label is None:
            continue
        pending.append(_entry(session, obj, label, "delete", None))

    for entry in pending:
        session.add(entry)


# ── استثنای آگاهانه‌ی «صریح به‌جای خودکار» ───────────────────────────────────
#
# docstringِ بالای همین فایل می‌گوید ثبت باید خودکار باشد نه صریح، چون «یادش
# بماند» برای ردی که ارزشِ قانونی دارد حالتِ شکست است. آن استدلال درباره‌ی
# **پوشش** است و سرِ جایش می‌ماند.
#
# این دو تا پوشش را کم نمی‌کنند؛ برای عملیاتی‌اند که *مراحلِ میانی‌اش واقعیت
# ندارند*. `renumber_entries` برای دور زدنِ قیدِ یکتای (مستأجر، شماره) اول همه‌ی
# شماره‌ها را منفی می‌کند و بعد نهایی. ثبتِ خودکار از آن دو flush دو رکورد
# می‌ساخت که یکی‌شان می‌گفت «سند شماره -۱ ویرایش شد» — وضعیتی که هرگز واقعیت
# نداشت — و هیچ‌کدام «۵ → ۳» را نشان نمی‌داد، یعنی همان تنها چیزی که کسی دنبالش
# می‌گردد.
#
# پس ثبتِ خودکار برای آن دو flush خاموش می‌شود و یک رکوردِ درست جایش می‌نشیند.


@contextmanager
def suppressed(session: Session):
    """ثبتِ خودکار را در این بلوک خاموش می‌کند.

    تودرتو امن است و پرچم را به مقدارِ قبلی برمی‌گرداند، نه به False — وگرنه بلوکِ
    داخلی خاموشیِ بلوکِ بیرونی را لغو می‌کرد.

    **هرکس این را به کار می‌برد موظف است خودش رکوردِ درست را بنویسد**
    (`record_change`). خاموش‌کردنِ بی‌جایگزین یعنی تغییرِ مالیِ بی‌رد.
    """
    previous = session.info.get(SUPPRESS_KEY, False)
    session.info[SUPPRESS_KEY] = True
    try:
        yield
    finally:
        session.info[SUPPRESS_KEY] = previous


def record_change(session: Session, obj, changes: dict, summary: str) -> None:
    """یک رکوردِ حسابرسیِ صریح با خلاصه‌ی دلخواه.

    `changes` همان شکلِ `{"field": {"from": ..., "to": ...}}`ِ ثبتِ خودکار را دارد
    تا خواننده‌ی دفتر مجبور نباشد دو قالب را بشناسد.

    مقدارها از همان `_jsonable`ِ مسیرِ خودکار رد می‌شوند — بی آن، یک `Decimal`ِ
    ساده درجِ رکورد را با `TypeError` می‌شکست و **کلِ تراکنشِ مالی** را با خودش
    می‌برد، فقط به‌خاطرِ ردِ حسابرسی.
    """
    label = audited_models().get(type(obj))
    if label is None:
        return
    changes = _jsonable(changes) if changes else None
    actor_id, actor_email = _actor(session)
    session.add(
        AuditLog(
            tenant_id=getattr(obj, "tenant_id", None),
            actor_id=actor_id,
            actor_email=actor_email,
            action="update",
            entity_type=type(obj).__name__,
            entity_id=obj.id,
            summary=summary,
            changes=changes or None,
            request_id=request_id_var.get(),
        )
    )
