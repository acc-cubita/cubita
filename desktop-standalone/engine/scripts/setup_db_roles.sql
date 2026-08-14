-- نقش‌های پایگاه‌داده. یک‌بار و با کاربر superuser اجرا شود:
--   psql -U postgres -d hesabdari -f scripts/setup_db_roles.sql
--
-- چرا لازم است
-- ============
-- بعد از فعال شدن RLS با FORCE، حتی مالک جدول هم مشمول سیاست ایزوله‌سازی است.
-- این عمدی و درست است — ولی دو پیامد عملیاتی دارد که هر دو باید حل شوند:
--
-- ۱. pg_dump شکست می‌خورد. بدون نقشی که RLS را دور بزند، پشتیبان‌گیری اصلاً کار
--    نمی‌کند و بدتر از آن، با سوییچ --enable-row-security بی‌صدا فقط ردیف‌های
--    قابل‌مشاهده را می‌گیرد؛ یعنی «پشتیبانی» که هنگام بازیابی معلوم می‌شود ناقص
--    بوده. برای نرم‌افزار حسابداری این بدترین حالت ممکن است.
--
-- ۲. مهاجرت‌های داده‌ای هیچ ردیفی نمی‌بینند. این یک‌بار واقعاً اتفاق افتاد: یک
--    backfill با موفقیت گزارش داد و صفر ردیف را عوض کرد.
--
-- تفکیک نقش‌ها
-- ===========
--   cubita_app      اجرای برنامه. مالک جدول نیست، BYPASSRLS ندارد. اگر روزی کسی
--                   برای «رفع مشکل» به این نقش superuser بدهد، تست
--                   test_app_role_cannot_bypass_rls قرمز می‌شود.
--   cubita_migrate  اجرای Alembic و pg_dump. BYPASSRLS دارد چون کارش روی داده‌ی
--                   همه‌ی مستأجرهاست. هرگز نباید در رشته‌ی اتصال برنامه باشد.

\set app_password `echo "${CUBITA_APP_PASSWORD:-CHANGE_ME_app}"`
\set migrate_password `echo "${CUBITA_MIGRATE_PASSWORD:-CHANGE_ME_migrate}"`

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cubita_app') THEN
        CREATE ROLE cubita_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cubita_migrate') THEN
        CREATE ROLE cubita_migrate LOGIN;
    END IF;
END
$$;

ALTER ROLE cubita_app     PASSWORD :'app_password'     NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
ALTER ROLE cubita_migrate PASSWORD :'migrate_password' NOSUPERUSER BYPASSRLS   NOCREATEDB NOCREATEROLE;

-- برنامه فقط داده می‌خواند و می‌نویسد؛ مالکیت و تغییر ساختار کار مهاجرت است.
GRANT CONNECT ON DATABASE hesabdari TO cubita_app, cubita_migrate;
GRANT USAGE ON SCHEMA public TO cubita_app, cubita_migrate;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO cubita_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cubita_app;
GRANT ALL ON ALL TABLES IN SCHEMA public TO cubita_migrate;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO cubita_migrate;

-- جدول‌هایی که مهاجرت‌های بعدی می‌سازند هم باید همین دسترسی را بگیرند
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cubita_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO cubita_app;

\echo ''
\echo 'نقش‌ها ساخته شدند. حالا:'
\echo '  ۱. رمزها را با CUBITA_APP_PASSWORD و CUBITA_MIGRATE_PASSWORD ست کنید و دوباره اجرا کنید'
\echo '  ۲. DATABASE_URL برنامه را به cubita_app تغییر دهید'
\echo '  ۳. مهاجرت و پشتیبان‌گیری را با cubita_migrate اجرا کنید'
\echo ''
