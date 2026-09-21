"""نمره‌ی سلامتِ دفتر — و مهم‌تر، **توضیحِ** نمره.

یک عددِ تنها («۶۱») چیزی جز دعوا نمی‌سازد: مشتری می‌پرسد «یعنی چه؟» و ما جوابی
جز «الگوریتم» نداریم. پس این ماژول هرگز فقط عدد نمی‌دهد؛ یک **جدول** می‌دهد که
سطر‌به‌سطر می‌گوید کدام بررسی چند امتیاز داشت، چند ردیف پیدا کرد و چقدر کم کرد.
آن جدول، خودِ نمره است.

فرمول:

    امتیازِ کم‌شده‌ی هر بررسی = وزن × چگالی
    چگالی = min(1، تعداد ÷ اشباع)      اشباع: خطا ۵، هشدار ۲۰
    نمره   = max(0، ۱۰۰ − مجموع)

**چرا تعداد و نه مبلغ:** مبلغ‌های این بررسی‌ها هم‌جنس نیستند. اختلافِ ارزش‌گذاریِ
انبار و فاکتورِ خریدِ تکراری دو «واحدِ نادرستی» متفاوت‌اند و جمعشان عددی می‌سازد
که معنایی ندارد.

**چرا «درصدِ بررسی‌های قبول‌شده» نه:** یک سندِ نامتوازن و هزار سندِ نامتوازن نمره‌ی
یکسان می‌گرفتند.

**چرا وزن‌ها در خودِ اجرا منجمد می‌شوند:** اگر فردا وزنی را تنظیم کنیم، کارنامه‌ی
پارسالِ مشتری نباید بازنویسی شود. تاریخچه باید ثابت بماند وگرنه بی‌ارزش است.
"""
from __future__ import annotations

from decimal import Decimal

#: وزنِ پیش‌فرض بر اساسِ شدت.
WEIGHT_BY_SEVERITY: dict[str, int] = {"error": 10, "warning": 4}

#: وزنِ ویژه‌ی بعضی بررسی‌ها. هر کلیدی که این‌جا نباشد وزنِ شدتش را می‌گیرد.
#: ترازنبودنِ دفتر و سند روی سرفصلِ گروه، ریشه‌ای‌ترند: هر گزارشی را دروغ می‌کنند.
WEIGHT_BY_KEY: dict[str, int] = {
    "unbalanced_entries": 20,
    "group_account_lines": 15,
    "trial_vs_ledger": 15,
    "duplicate_supplier_invoice": 12,
    "entries_before_period_close": 12,
}

#: چند ردیف یعنی «فراگیر». یک موردِ خطا یک‌پنجمِ وزنش را می‌گیرد، پنج مورد همه‌اش.
SATURATION_BY_SEVERITY: dict[str, int] = {"error": 5, "warning": 20}

#: مرزهای درجه. برچسب‌ها عمداً قضاوتِ اخلاقی نمی‌کنند: «نیازمندِ رسیدگی» نه «ضعیف».
GRADE_HEALTHY = 85
GRADE_WARNING = 60

GRADE_LABELS: dict[str, str] = {
    "healthy": "سالم",
    "warning": "نیازمندِ رسیدگی",
    "critical": "بحرانی",
}


def weight_for(key: str, severity: str) -> int:
    return WEIGHT_BY_KEY.get(key, WEIGHT_BY_SEVERITY.get(severity, 0))


def score_report(report: dict) -> dict:
    """گزارشِ موتور را به نمره، درجه و جدولِ توضیح تبدیل می‌کند.

    خروجی:
        {score, grade, error_count, warning_count, finding_count, summary: [...]}

    هر ردیفِ `summary` همان چیزی است که روی صفحه نشان داده می‌شود و همان چیزی که
    در `assurance_runs.summary` منجمد می‌شود.
    """
    summary: list[dict] = []
    lost = Decimal(0)
    error_count = 0
    warning_count = 0
    finding_count = 0

    for check in report.get("checks", []):
        severity = check["severity"]
        count = int(check.get("count") or 0)
        weight = weight_for(check["key"], severity)
        saturation = SATURATION_BY_SEVERITY.get(severity, 1)
        density = min(Decimal(1), Decimal(count) / Decimal(saturation)) if count else Decimal(0)
        penalty = (Decimal(weight) * density).quantize(Decimal("0.01"))
        lost += penalty
        finding_count += count
        if count:
            if severity == "error":
                error_count += count
            else:
                warning_count += count
        summary.append(
            {
                "key": check["key"],
                "title": check["title"],
                "description": check.get("description", ""),
                "severity": severity,
                "family": check.get("family", "ledger"),
                "count": count,
                "weight": weight,
                "lost": float(penalty),
            }
        )

    score = max(Decimal(0), Decimal(100) - lost).quantize(Decimal("0.01"))

    #: دفترِ ناتراز همیشه بحرانی است، هر عددی که نمره بدهد — همان قاعده‌ای که
    #: خودِ `run_integrity_check` برای `ok` دارد.
    balanced = report.get("total_debit") == report.get("total_credit")
    if not balanced:
        grade = "critical"
    elif score >= GRADE_HEALTHY:
        grade = "healthy"
    elif score >= GRADE_WARNING:
        grade = "warning"
    else:
        grade = "critical"

    return {
        "score": score,
        "grade": grade,
        "error_count": error_count,
        "warning_count": warning_count,
        "finding_count": finding_count,
        "summary": summary,
    }
