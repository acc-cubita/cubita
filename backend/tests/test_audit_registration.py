"""ثبتِ listenerِ حسابرسی نباید به یک زنجیره‌ی importِ اتفاقی بند باشد.

**آنچه اتفاق افتاد.** `app.audit` با `@event.listens_for(Session, "before_flush")`
خودش را روی هر نشستِ SQLAlchemy می‌نشاند — ولی هیچ‌جای کد صریح import‌اش نمی‌کرد.
در اپِ وب اتفاقی از راهِ `app.deps` می‌آمد (هر router به آن وابسته است)، پس همه‌چیز
سالم به‌نظر می‌رسید.

بیرونِ آن زنجیره اما پوشش صفر بود: یک اسکریپتِ سرور که `SessionLocal` گرفت و یک
جلسه‌ی انبارگردانی را لغو کرد، **هیچ ردی در `audit_log` نگذاشت**. نه خطایی، نه
هشداری — فقط یک تغییرِ ثبت‌نشده. برای دفتری که ردِ حسابرسی‌اش ارزشِ قانونی دارد،
این بدترین شکلِ شکست است: شکستِ خاموش.

این تست‌ها همان را از دو زاویه قفل می‌کنند: یکی ساختاری (آیا ماژول بار می‌شود؟)
و یکی رفتاری (آیا یک flushِ ساده واقعاً رد می‌گذارد؟).
"""
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from app.models.audit import AuditLog
from app.models.sales_ops import SaleType

BACKEND = Path(__file__).resolve().parents[1]


def test_importing_the_database_module_alone_loads_the_audit_listener():
    """**گاردِ اصلی.** و عمداً در زیرپروسه است.

    در یک اجرای pytest، `app.audit` را ده‌ها فایلِ دیگر از قبل import کرده‌اند؛
    هر تستِ درون‌پروسه‌ای این‌جا همیشه سبز می‌شود و هیچ‌چیز را ثابت نمی‌کند. تنها
    راهِ سنجیدنِ «آیا *فقط* `app.database` کافی است» یک پروسه‌ی تازه است.
    """
    probe = (
        "import sys\n"
        "import app.database\n"
        "assert 'app.audit' in sys.modules, "
        "'ثبتِ حسابرسی بار نشد — هر اسکریپتی که فقط SessionLocal بگیرد ردش را گم می‌کند'\n"
        "from sqlalchemy import event\n"
        "from sqlalchemy.orm import Session\n"
        "import app.audit\n"
        "assert event.contains(Session, 'before_flush', app.audit._record_financial_changes), "
        "'ماژول بار شد ولی listener ثبت نشده'\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "OK" in result.stdout


def test_a_plain_session_flush_leaves_an_audit_trail(db, tenant_id):
    """**گاردِ رفتاری.** بدونِ عبور از HTTP، فقط ORM.

    همان مسیری که یک اسکریپت یا cron می‌رود. `actor` تنظیم نشده، پس «سیستم» ثبت
    می‌شود — که برای کارِ سرپرستی درست است؛ آنچه پذیرفتنی نیست **نبودِ** رکورد است.
    """
    row = SaleType(tenant_id=tenant_id, name=f"نقدی-{uuid4().hex[:8]}")
    db.add(row)
    db.flush()

    before = db.query(AuditLog).filter(AuditLog.entity_id == row.id).count()
    row.name = f"اعتباری-{uuid4().hex[:8]}"
    db.flush()

    logs = db.query(AuditLog).filter(AuditLog.entity_id == row.id).all()
    assert len(logs) > before, "*** تغییر هیچ ردی نگذاشت ***"

    latest = logs[-1]
    assert latest.entity_type == "SaleType"
    assert latest.changes["name"]["to"] == row.name
    #: بی‌نام بودنِ عامل اشکال نیست؛ بی‌رد بودنِ تغییر هست.
    assert latest.actor_email == "سیستم"


def test_the_listener_is_registered_exactly_once(db, tenant_id):
    """import شدن از چند جا نباید رکوردِ تکراری بسازد.

    حالا که `app.database` هم import‌اش می‌کند و `app.deps` هم، این سؤال واقعی
    است: اگر دکوراتور دوبار اجرا می‌شد، هر تغییر دو رکورد می‌ساخت و شمارشِ
    حسابرسی بی‌معنی می‌شد. (ماژولِ پایتون یک‌بار بار می‌شود، ولی تستش ارزان است.)
    """
    row = SaleType(tenant_id=tenant_id, name=f"امانی-{uuid4().hex[:8]}")
    db.add(row)
    db.flush()
    row.name = f"صادراتی-{uuid4().hex[:8]}"
    db.flush()

    logs = db.query(AuditLog).filter(AuditLog.entity_id == row.id).all()
    creates = [log for log in logs if log.action == "create"]
    updates = [log for log in logs if log.action == "update"]
    assert len(creates) == 1, f"به‌جای یک رکوردِ ثبت، {len(creates)} تا ساخته شد"
    assert len(updates) == 1, f"به‌جای یک رکوردِ ویرایش، {len(updates)} تا ساخته شد"
