#!/usr/bin/env bash
# پشتیبان‌گیری از پایگاه‌داده‌ی کوبیتا.
#
# **باید با نقشی اجرا شود که BYPASSRLS دارد** (cubita_migrate).
#
# چرا این‌قدر تأکید: بعد از FORCE ROW LEVEL SECURITY، pg_dump با نقش معمولی شکست
# می‌خورد. وسوسه‌ی طبیعی این است که سوییچ --enable-row-security اضافه شود تا خطا
# برطرف شود — و آن کار یک پشتیبانِ ظاهراً سالم می‌سازد که همه‌ی جدول‌ها را دارد
# ولی ردیف‌هایشان خالی است، چون pg_dump زمینه‌ی مستأجر ندارد و سیاست صفر ردیف
# مچ می‌کند. این با اندازه‌ی فایل یا شمارش جدول‌ها هم معلوم نمی‌شود؛ فقط روز
# بازیابی معلوم می‌شود، که دیر است.
#
# پس این اسکریپت هرگز از آن سوییچ استفاده نمی‌کند و **قبل** از dump بررسی می‌کند
# که نقش واقعاً BYPASSRLS دارد.
#
# اجرا:
#   BACKUP_DB_URL=postgresql://cubita_migrate:PASS@host:5432/hesabdari ./scripts/backup.sh /var/backups/cubita
set -euo pipefail

DEST="${1:-./backups}"
DB_URL="${BACKUP_DB_URL:-}"

if [[ -z "$DB_URL" ]]; then
    echo "خطا: BACKUP_DB_URL ست نشده." >&2
    echo "باید به نقش cubita_migrate اشاره کند (دارای BYPASSRLS)، نه به نقش برنامه." >&2
    exit 1
fi

# --- پیش‌بررسی: نقش باید بتواند همه‌ی ردیف‌ها را ببیند -------------------------
CAN_SEE_ALL="$(psql --dbname="$DB_URL" -At -c \
    "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user")"

if [[ "$CAN_SEE_ALL" != "t" ]]; then
    ROLE="$(psql --dbname="$DB_URL" -At -c 'SELECT current_user')"
    cat >&2 <<MSG
خطا: نقش «$ROLE» نه BYPASSRLS دارد نه superuser است.

پشتیبانی که با این نقش گرفته شود ردیف‌های جدول‌های مستأجرمحور را نخواهد داشت،
و این در فایل خروجی به چشم نمی‌آید. پشتیبان‌گیری متوقف شد.

رفع: scripts/setup_db_roles.sql را یک‌بار با superuser اجرا کنید و BACKUP_DB_URL
را به نقش cubita_migrate بدهید.
MSG
    exit 1
fi

mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$DEST/cubita_${STAMP}.dump"

# فرمت custom تا بازیابی گزینشی جدول ممکن باشد؛ فشرده‌سازی داخلی دارد.
pg_dump --dbname="$DB_URL" --format=custom --compress=9 --no-owner --no-privileges --file="$FILE"

# --- پس‌بررسی: ردیف‌های واقعی در پشتیبان با پایگاه‌داده بخوانند ------------------
# پشتیبان تست‌نشده پشتیبان نیست. جدول‌های حیاتی با شمارش واقعی سنجیده می‌شوند، نه
# با شمارش نامِ جدول‌ها — چون دقیقاً همان چیزی است که در حالت خراب سالم به نظر می‌رسد.
for TABLE in accounts journal_lines; do
    LIVE="$(psql --dbname="$DB_URL" -At -c "SELECT count(*) FROM $TABLE")"
    IN_DUMP="$(pg_restore --data-only --table="$TABLE" "$FILE" 2>/dev/null | grep -cE '^[0-9a-f]{8}-' || true)"
    if [[ "$LIVE" -gt 0 && "$IN_DUMP" -eq 0 ]]; then
        echo "خطا: جدول $TABLE در پایگاه‌داده $LIVE ردیف دارد ولی در پشتیبان صفر." >&2
        echo "پشتیبان ناقص است و حذف شد." >&2
        rm -f "$FILE"
        exit 1
    fi
    echo "  $TABLE: $IN_DUMP ردیف در پشتیبان (پایگاه‌داده: $LIVE)"
done

echo "پشتیبان ساخته شد: $FILE ($(du -h "$FILE" | cut -f1))"

# --- نگهداری ------------------------------------------------------------------
KEEP="${BACKUP_KEEP_DAYS:-30}"
find "$DEST" -name 'cubita_*.dump' -type f -mtime "+$KEEP" -delete
echo "پشتیبان‌های قدیمی‌تر از $KEEP روز حذف شدند."
