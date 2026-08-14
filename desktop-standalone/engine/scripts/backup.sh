#!/usr/bin/env bash
# پشتیبان‌گیری از پایگاه‌داده‌ی کوبیتا، با راستی‌آزمایی.
#
# **مسئله‌ای که این اسکریپت برای آن وجود دارد** (روی همین سیستم اثبات شد):
#
# بعد از FORCE ROW LEVEL SECURITY، اگر pg_dump با نقشی اجرا شود که BYPASSRLS ندارد،
# این اتفاق می‌افتد:
#
#     pg_dump: error: query would be affected by row-level security policy
#     کد خروج: 0                    ← اینجاست فاجعه
#     فایل ۱۶۰ کیلوبایتی ساخته می‌شود، با همه‌ی جدول‌ها، و صفر ردیف.
#
# چون کد خروج صفر است، نه `set -e` می‌گیردش، نه cron هشدار می‌دهد. اسکریپت قبلی
# بعد از dump بی‌قید‌و‌شرط پشتیبان‌های قدیمی‌تر از ۱۴ روز را پاک می‌کرد — یعنی
# دقیقاً ۱۴ روز بعد از فعال شدن RLS، آخرین پشتیبان سالم هم می‌رفت و از آن به بعد
# فقط فایل‌های خالی می‌ماند. بی‌صدا.
#
# سه دفاع اینجا هست، و ترتیبشان مهم است:
#   ۱. پیش‌بررسی: نقش باید BYPASSRLS یا superuser باشد.
#   ۲. پس‌بررسی: هر جدولی که در پایگاه‌داده ردیف دارد باید در پشتیبان هم داشته باشد.
#   ۳. چرخش فقط و فقط بعد از موفقیت هر دو. پشتیبان بد حذف می‌شود، قدیمی‌ها نه.
#
# هرگز از --enable-row-security استفاده نکنید: خطا را خاموش می‌کند و همان پشتیبانِ
# خالی را می‌سازد، فقط بدون پیام.
#
# اجرا (روی سرور، از cron ریشه):
#   /opt/hesabdari/backup.sh /opt/hesabdari/backups
#
# به‌طور پیش‌فرض با نقش postgres از طریق سوکت یونیکس (peer auth) وصل می‌شود، پس
# هیچ رمزی لازم ندارد و هیچ رمزی در فایل نیست. برای استفاده از نقش دیگر:
#   BACKUP_DB_URL=postgresql://role:pass@host/db /opt/hesabdari/backup.sh /dest
set -euo pipefail

DEST="${1:-/opt/hesabdari/backups}"
DB_NAME="${BACKUP_DB_NAME:-hesabdari}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

# نام فایل از نام پایگاه‌داده می‌آید و ثابت نیست. وقتی پیشوند هاردکد بود، پشتیبانِ
# دمو هم `hesabdari_*.dump` نام می‌گرفت — یعنی دو مقصدِ کاملاً متفاوت فایل‌هایی با
# نام یکسان تولید می‌کردند. روزی که کسی زیر فشار دنبال پشتیبان بگردد، آن شباهت
# دقیقاً همان‌جایی است که پشتیبان دمو روی داده‌ی واقعی بازیابی می‌شود.
PREFIX="$DB_NAME"

# دو حالت اتصال: URL صریح، یا peer auth به‌عنوان postgres (پیش‌فرض، بدون رمز).
if [[ -n "${BACKUP_DB_URL:-}" ]]; then
    PSQL=(psql --dbname="$BACKUP_DB_URL")
    PGDUMP=(pg_dump --dbname="$BACKUP_DB_URL")
    RESTORE=(pg_restore)
else
    PSQL=(sudo -u postgres psql --dbname="$DB_NAME")
    PGDUMP=(sudo -u postgres pg_dump --dbname="$DB_NAME")
    RESTORE=(sudo -u postgres pg_restore)
fi

fail() { echo "[پشتیبان‌گیری ناموفق] $*" >&2; exit 1; }

# --- دفاع ۱: نقش باید بتواند همه‌ی ردیف‌ها را ببیند ------------------------------
CAN_SEE_ALL="$("${PSQL[@]}" -At -c \
    "SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user" 2>/dev/null || true)"

if [[ "$CAN_SEE_ALL" != "t" ]]; then
    ROLE="$("${PSQL[@]}" -At -c 'SELECT current_user' 2>/dev/null || echo '؟')"
    fail "نقش «$ROLE» نه BYPASSRLS دارد نه superuser است.
اگر RLS فعال باشد، پشتیبانِ گرفته‌شده با این نقش ساختار کامل و صفر ردیف خواهد داشت
و این در فایل خروجی به چشم نمی‌آید. پشتیبان‌گیری انجام نشد."
fi

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$DEST/${PREFIX}_${STAMP}.dump"

# خروجی به stdout و تغییر مسیر در پوسته، نه --file: وقتی pg_dump زیر
# `sudo -u postgres` اجرا می‌شود، --file را *به‌عنوان کاربر postgres* می‌نویسد و
# پوشه‌ی پشتیبان مال کاربر دیگری است، پس Permission denied می‌گیرد. با تغییر مسیر،
# نوشتن کارِ پوسته است و با دسترسی همان کاربری انجام می‌شود که اسکریپت را اجرا کرده.
# فایل ناقص باید برود. اسکریپت قبلی وقتی pg_dump شکست می‌خورد یک فایل ۹۶ کیلوبایتیِ
# نیمه‌کاره جا می‌گذاشت با نامِ درست و تاریخِ امروز — یعنی هر کسی که با `ls` بررسی
# می‌کرد پشتیبان‌گیری سالم به‌نظرش می‌رسید، در حالی که هفته‌ها بود کار نمی‌کرد.
# فایل جعلی از نبودِ فایل بدتر است.
"${PGDUMP[@]}" --format=custom --compress=9 > "$FILE" || {
    rm -f "$FILE"
    fail "خودِ pg_dump خطا داد. فایل ناقص حذف شد."
}

[[ -s "$FILE" ]] || { rm -f "$FILE"; fail "فایل پشتیبان خالی است."; }

# --- دفاع ۲: هر جدول پرداده در پایگاه‌داده باید در پشتیبان هم ردیف داشته باشد ------
# فهرست جدول‌ها از خودِ پایگاه‌داده خوانده می‌شود و نه از یک لیست ثابت، تا با رشد
# اسکیما خودش را به‌روز نگه دارد. لیست ثابت همان چیزی است که کهنه می‌شود و بعد
# جدولی که تازه اضافه شده بی‌صدا از راستی‌آزمایی جا می‌ماند.
# ردیف‌ها بین `COPY ... FROM stdin;` و `\.` شمرده می‌شوند.
#
# دو تله‌ای که خودم داخلشان افتادم و اینجا ثبت می‌شوند تا کسی دوباره نیفتد:
#
#   ۱. `pg_restore` در نسخه‌ی ۱۴ بدون `-f -` اصلاً کار نمی‌کند و خطا می‌دهد. اگر
#      stderr را دور بریزید، شمارش همیشه صفر درمی‌آید و اسکریپت *همیشه* پشتیبان
#      سالم را هم رد می‌کند — بررسی‌ای که چیزی را نمی‌سنجد ولی مطمئن به‌نظر می‌رسد.
#   ۲. شمارش با `pg_restore -l` (فهرست TABLE DATA) بی‌فایده است: در حالت خرابِ RLS
#      همه‌ی ورودی‌ها سر جایشان هستند و فقط ردیف‌ها نیستند. دقیقاً همان چیزی که
#      باید تشخیص داده شود از دید آن روش نامرئی است.
count_rows_in_dump() {
    local table="$1" err
    err="$("${RESTORE[@]}" --data-only --table="$table" -f - "$FILE" 2>&1 >/dev/null)" || {
        echo "خطای pg_restore برای $table: $err" >&2
        return 1
    }
    "${RESTORE[@]}" --data-only --table="$table" -f - "$FILE" 2>/dev/null \
        | awk '/^COPY .* FROM stdin;$/ {inside=1; next} /^\\\.$/ {inside=0} inside {n++} END {print n+0}'
}

MISMATCH=0
while read -r TABLE LIVE; do
    [[ -z "$TABLE" ]] && continue
    IN_DUMP="$(count_rows_in_dump "$TABLE")" || { MISMATCH=1; continue; }
    if [[ "$IN_DUMP" -eq 0 ]]; then
        echo "  ✗ $TABLE: پایگاه‌داده $LIVE ردیف — پشتیبان ۰" >&2
        MISMATCH=1
    else
        echo "  ✓ $TABLE: $IN_DUMP ردیف"
    fi
done < <("${PSQL[@]}" -At -F' ' -c "
    SELECT relname, n_live_tup
      FROM pg_stat_user_tables
     WHERE schemaname = 'public' AND n_live_tup > 0
     ORDER BY n_live_tup DESC
     LIMIT 12")

if [[ "$MISMATCH" -ne 0 ]]; then
    rm -f "$FILE"
    fail "پشتیبان ردیف‌های واقعی را نداشت و حذف شد. پشتیبان‌های قدیمی دست‌نخورده ماندند.
محتمل‌ترین علت: RLS فعال شده و این نقش BYPASSRLS ندارد."
fi

echo "پشتیبان سالم: $FILE ($(du -h "$FILE" | cut -f1))"

# --- دفاع ۳: چرخش فقط بعد از موفقیت ----------------------------------------------
# این خط عمداً آخرین خط است. اسکریپت قبلی آن را بی‌قیدوشرط اجرا می‌کرد و همین باعث
# می‌شد پشتیبان خرابِ امروز، پشتیبان سالمِ دو هفته پیش را هم با خودش ببرد.
DELETED="$(find "$DEST" -name "${PREFIX}_*.dump" -type f -mtime "+$KEEP_DAYS" -print -delete | wc -l)"
echo "چرخش: $DELETED پشتیبان قدیمی‌تر از $KEEP_DAYS روز حذف شد."
