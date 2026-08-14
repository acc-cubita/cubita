"""کمک‌کننده‌ی مهاجرت برای عبور از RLS.

مهاجرت‌ها بدون زمینه‌ی مستأجر اجرا می‌شوند — و نباید هم اجرا شوند، چون کارشان روی
داده‌ی *همه‌ی* مستأجرهاست. ولی سیاست ایزوله‌سازی `current_setting('app.tenant_id')`
را می‌خواند و وقتی خالی است صفر ردیف مچ می‌کند. نتیجه: هر UPDATE داده‌ای در مهاجرت
بی‌صدا صفر ردیف را عوض می‌کند و مهاجرت با موفقیت گزارش می‌دهد.

این دقیقاً یک‌بار اتفاق افتاد: مهاجرت system_role موفق اعلام شد و هیچ حسابی
علامت نخورد.

`SET row_security = off` جواب نمی‌دهد؛ آن گزینه به‌جای دور زدن، خطا می‌دهد. تا وقتی
FORCE روشن است حتی مالک جدول هم مشمول سیاست است. پس FORCE موقتاً و داخل همان
تراکنشِ مهاجرت برداشته می‌شود. چون DDL در Postgres تراکنشی است، اگر مهاجرت شکست
بخورد FORCE هم با آن برمی‌گردد و پنجره‌ای باز نمی‌ماند.

راه‌حل بلندمدت یک نقش جدا با BYPASSRLS برای مهاجرت‌هاست، که ساختنش superuser
می‌خواهد. تا آن وقت، این تنها راه امنِ در دسترس است.
"""
from contextlib import contextmanager

import sqlalchemy as sa


@contextmanager
def rls_disabled(conn, tables):
    """FORCE را روی جدول‌های داده‌شده موقتاً برمی‌دارد تا مهاجرت همه‌ی ردیف‌ها را ببیند."""
    tables = list(tables)
    for t in tables:
        conn.execute(sa.text(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY"))
    try:
        yield
    finally:
        for t in tables:
            conn.execute(sa.text(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY"))
