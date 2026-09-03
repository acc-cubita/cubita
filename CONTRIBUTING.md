# راه‌اندازیِ محیطِ توسعه — از صفر

این سند برای کسی است که تازه به پروژه اضافه شده. هدف: از یک کلونِ خالی تا
اپِ در حالِ اجرا. پیش‌نیازها: **Python 3.13**، **Node 24**، **PostgreSQL 16+**، **Git**.

نقشه‌ی معماری در [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) و قواعدِ کدنویسی در
[CLAUDE.md](CLAUDE.md) است — هر دو را پیش از اولین تغییر بخوان.

---

## ۱. پایگاه‌داده

```bash
# دیتابیس را بساز (با کاربرِ superuserِ پستگرس)
psql -U postgres -c "CREATE DATABASE hesabdari;"

# نقش‌های cubita_app و cubita_migrate را بساز
cd backend
CUBITA_APP_PASSWORD='یک‌رمزِ‌محلی' CUBITA_MIGRATE_PASSWORD='یک‌رمزِ‌دیگر' \
  psql -U postgres -d hesabdari -f scripts/setup_db_roles.sql
```

**چرا دو نقش؟** بعد از `FORCE ROW LEVEL SECURITY` حتی مالکِ جدول هم مشمولِ
ایزوله‌سازی است. `cubita_app` (بدونِ BYPASSRLS) برنامه را می‌راند؛
`cubita_migrate` (با BYPASSRLS) مهاجرت و `pg_dump` را. توضیحِ کاملش داخلِ خودِ
`scripts/setup_db_roles.sql` است. اگر روزی به `cubita_app` دسترسیِ superuser بدهی،
تستِ `test_app_role_cannot_bypass_rls` قرمز می‌شود — همین‌طور باید بماند.

## ۲. بک‌اند

```bash
cd backend
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env      # مقادیر را پر کن (پایین را ببین)
ZARINPAL_SANDBOX=true venv/Scripts/python.exe -m alembic upgrade head
```

مقادیرِ لازم در `.env` برای کارِ محلی:

| کلید | مقدارِ محلی |
|---|---|
| `ENV` | `development` |
| `DATABASE_URL` | `postgresql+psycopg://cubita_app:رمز@localhost:5432/hesabdari` |
| `JWT_SECRET` | هر رشته‌ی تصادفیِ بلند |
| `ALLOWED_ORIGINS` | `http://localhost:5173` |
| `ZARINPAL_SANDBOX` | `true` |

بقیه‌ی کلیدها (زرین‌پال، فروشگاه، پیامک) برای توسعه‌ی محلی لازم نیستند؛ خالی
بگذارشان مگر روی همان بخش کار کنی.

**حسابِ خودت را بساز** (دیتابیسِ محلی خالی است):

```bash
ZARINPAL_SANDBOX=true venv/Scripts/python.exe -m app.seed you@example.com 'YourPass1!'
```

ایمیل باید دامنه‌ی معتبر داشته باشد — `EmailStr` مقادیرِ `.local`/`.test` را با
۴۲۲ رد می‌کند.

**اجرا:**

```bash
ZARINPAL_SANDBOX=true PYTHONUTF8=1 venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`--reload` نگذار — با بارگذاریِ ماژول‌های SQLAlchemy ناسازگار است. بعد از هر
ویرایش دستی ری‌استارت کن.

**تست:** `venv/Scripts/python.exe -m pytest -q` — کلِ سوییت باید سبز بماند.

## ۳. اپِ دسکتاپ/وب

```bash
cd desktop
npm install
npm run dev                                     # Electron + Vite
# یا فقط مرورگر:
WEB_ONLY=1 npx vite --port 5173 --strictPort
```

آدرسِ API در `desktop/src/api.ts` است. برای کارِ محلی باید به
`http://127.0.0.1:8000` اشاره کند، نه به production.

**پیش از هر کامیت:**

```bash
npx tsc -b --force            # صفر خطا
npm run lint
node scripts/audit-pages.mjs  # ۱۲ قاعده‌ی ساختاری، بدونِ error
```

## ۴. اپِ موبایل (اختیاری)

```bash
cd mobile
npm install
cp .env.example .env
npx expo start
```

پوشه‌ی `mobile/android/` در گیت نیست و ماشین‌به‌ماشین ساخته می‌شود
(`npm run android`، با gradlewِ محلی — نه EAS).

---

## گردشِ کار

1. `git pull --rebase origin master`
2. شاخه: `git switch -c feat/عنوانِ-کوتاه`  (`feat/` · `fix/` · `chore/`)
3. کار کن؛ کامیتِ فارسی به سبکِ conventional:
   `feat(inventory): انبارگردانیِ جزئی`
4. **یک ردیف به بخشِ ۱۰ «تاریخچه‌ی ارتقاها»ی `PROJECT_OVERVIEW.md` اضافه کن.**
   بدونِ این، نفرِ دیگر نمی‌فهمد چه شد و چرا.
5. `tsc` + `pytest` + `audit-pages.mjs` سبز
6. `git push -u origin feat/…` و بعد Pull Request روی `master`

**نکته‌ی مهم:** اگر مهاجرتِ Alembic می‌سازی، اول اعلام کن. دو مهاجرتِ همزمان از دو
نفر یعنی دو سرِ موازی و `alembic upgrade head` شکست می‌خورد. با `alembic heads`
چک کن که فقط یک سر باشد.

## کارهایی که فقط صاحبِ پروژه انجام می‌دهد

- استقرار روی production (`acc.cubita.ir`) و demo
- ساخت و بارگذاریِ فایلِ نصبیِ دسکتاپ
- انتشارِ اپ در کافه‌بازار
- تغییرِ رازها و کلیدهای درگاه/پیامک
