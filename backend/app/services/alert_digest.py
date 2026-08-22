"""دایجستِ روزانه‌ی هشدارها به اپ موبایل (Push).

برای هر مستأجری که **دستگاهِ Push ثبت کرده**، در کانتکستِ RLS خودش هشدارهای «نیازِ
رسیدگی» (شدتِ danger/warning) را زنده می‌سنجد و **یک اعلانِ خلاصه** می‌فرستد که با
لمس به صفحه‌ی هشدارهای اپ می‌رود (`route=alerts`).

عمداً ساده و بی‌حالت: چیزی در DB نمی‌نویسد و «چه چیزی قبلاً فرستاده شده» را ردیابی
نمی‌کند — تنها گلوگاهِ ضدنویز، خودِ زمان‌بندیِ روزانه است (یک خلاصه در صبح). آیتم‌های
صرفاً info (سندِ تکرارشونده‌ی پیش‌رو، یادآوریِ تقویمِ پیش‌رو) به‌تنهایی اعلان تولید
نمی‌کنند تا صبح‌ها بی‌جهت زنگ نخورد.

فقط مستأجرهایی پردازش می‌شوند که حداقل یک device_token دارند — یعنی اپ نصب است؛
بقیه هزینه‌ی محاسبه ندارند.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken
from app.services import push as push_service
from app.services.alerts import get_alerts
from app.tenant_context import tenant_scope

#: برچسبِ فارسیِ دسته‌ها برای متنِ خلاصه.
_CATEGORY_LABEL = {
    "check": "چک",
    "receivable": "مطالبات معوق",
    "credit": "عبور از سقف اعتبار",
    "recurring": "سند تکرارشونده",
    "calendar": "یادآوری تقویم",
    "stock": "موجودی منفی",
    "installment": "قسط معوق",
}
#: فقط این شدت‌ها اعلان تولید می‌کنند (info صبح‌ها زنگ نمی‌زند).
_ACTIONABLE = ("danger", "warning")

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(n: int) -> str:
    return str(n).translate(_FA_DIGITS)


def _summarize(items: list[dict]) -> tuple[int, str] | None:
    """از آیتم‌های هشدار یک (تعداد، متنِ خلاصه) می‌سازد؛ None اگر چیزی برای اعلان نبود."""
    actionable = [it for it in items if it.get("severity") in _ACTIONABLE]
    if not actionable:
        return None
    counts: dict[str, int] = {}
    for it in actionable:
        cat = it.get("category", "")
        counts[cat] = counts.get(cat, 0) + 1
    # تا ۳ دسته‌ی پرشمار، مرتب‌شده نزولی: «چک (۲)، مطالبات معوق (۱)»
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    body = "، ".join(f"{_CATEGORY_LABEL.get(cat, cat)} ({_fa(n)})" for cat, n in top)
    return len(actionable), body


def send_daily_digests(db: Session, *, as_of: date | None = None) -> dict:
    """یک بار روی همه‌ی مستأجرهای دارای اپ می‌گذرد و دایجستِ هشدار می‌فرستد.

    خودش commit نمی‌کند (خواندنی است)؛ فراخواننده تراکنش را می‌بندد.
    """
    tenant_ids = [
        tid
        for (tid,) in db.query(DeviceToken.tenant_id)
        .filter(DeviceToken.tenant_id.isnot(None))
        .distinct()
        .all()
    ]
    processed = pushed = 0
    for tid in tenant_ids:
        with tenant_scope(db, tid):
            data = get_alerts(db, as_of)
            processed += 1
            summary = _summarize(data["items"])
            if summary is None:
                continue
            count, body = summary
            # شکستِ ارسال هرگز کلِ کرون را نمی‌شکند (safe_notify پوششِ استثنا دارد).
            before = pushed
            try:
                n = push_service.notify_tenant(
                    db,
                    tid,
                    title=f"کوبیتا — {_fa(count)} مورد نیازِ رسیدگی",
                    body=body,
                    data={"route": "alerts"},
                )
                if n:
                    pushed += 1
            except Exception:  # noqa: BLE001 — یک مستأجرِ خراب نباید بقیه را قطع کند
                pushed = before
    return {"tenants": processed, "pushed": pushed}
