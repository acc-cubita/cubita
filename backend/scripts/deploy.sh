#!/usr/bin/env bash
# استقرار کوبیتا روی VPS — با برگشت خودکار اگر چیزی بشکند.
#
# اجرا روی سرور، به‌عنوان root:
#   /opt/hesabdari/deploy.sh production
#   /opt/hesabdari/deploy.sh demo
#
# پیش‌نیاز: /tmp/cubita_code.tgz و /tmp/cubita_web_<پروفایل>.tgz آپلود شده باشند.
#
# **چرا پروفایل و نه دو اسکریپت:** تا وقتی دو نسخه‌ی جدا بود، دمو هشت مهاجرت عقب
# ماند و کسی متوجه نشد — از جمله نقشِ «دمو» که هنوز wildcard داشت. دو اسکریپتِ
# موازی همیشه واگرا می‌شوند، چون فقط یکی‌شان موقع تغییر به چشم می‌آید.
#
# **چرا سرویس متوقف می‌شود:** مهاجرت ۰۰۱۵ ستون tenant_id را NOT NULL می‌کند و کد
# قدیمی آن را پر نمی‌کند. پس پنجره‌ای هست که در آن اسکیمای تازه + کد قدیمی یعنی
# هر نوشتنی خطا می‌دهد. چند ثانیه است، ولی صفر کردنش درست‌تر از کوچک کردنش است.
#
# **برگشت:** اگر هر گامی شکست بخورد، کد به آرشیو قبل از استقرار برمی‌گردد و سرویس
# دوباره بالا می‌آید. مهاجرت‌های alembic هرکدام در تراکنش خودشان اجرا می‌شوند، پس
# مهاجرتِ شکست‌خورده خودش را برمی‌گرداند. اگر پایگاه‌داده نیاز به بازیابی داشت،
# دستورش در پایان چاپ می‌شود — عمداً خودکار نیست، چون بازیابی خودکارِ اشتباه
# می‌تواند وضعیت را بدتر کند.
set -euo pipefail

# --- پروفایل مقصد ------------------------------------------------------------------
# fail closed روی پروفایل ناشناخته، به همان دلیلی که config.py روی ENV ناشناخته
# بالا نمی‌آید: یک تایپو نباید به «یک چیزی را یک‌جایی مستقر کن» ترجمه شود.
PROFILE="${1:-}"
case "$PROFILE" in
    production)
        APP_DIR=/opt/hesabdari
        SERVICE=hesabdari-backend
        OS_USER=hesabdari
        DB_NAME=hesabdari
        PORT=8001
        APP_URL=https://acc.cubita.ir
        ;;
    demo)
        APP_DIR=/opt/cubita-demo
        SERVICE=cubita-demo-backend
        OS_USER=cubitademo
        DB_NAME=cubita_demo
        PORT=8002
        APP_URL=https://demo.cubita.ir
        ;;
    *)
        echo "استفاده: $0 {production|demo}" >&2
        [[ -n "$PROFILE" ]] && echo "پروفایل ناشناخته: ${PROFILE}" >&2
        exit 2
        ;;
esac

CODE_TGZ=/tmp/cubita_code.tgz
WEB_TGZ="/tmp/cubita_web_${PROFILE}.tgz"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="$APP_DIR/rollback_code_$STAMP.tgz"
BACKUP_BEFORE=""

say() { echo; echo "=== $* ==="; }

rollback() {
    echo
    echo "!!! استقرار شکست خورد — برگشت به وضعیت قبل" >&2
    if [[ -f "$ARCHIVE" ]]; then
        # پوشه‌ها اول خالی می‌شوند و بعد آرشیو باز می‌شود.
        #
        # نسخه‌ی اول فقط `tar xzf` روی پوشه می‌زد، و tar فایل‌هایی را که در آرشیو
        # نیستند پاک نمی‌کند. نتیجه‌اش یک حالت *ترکیبی* بود: main.py قدیمی کنار
        # فایل‌های تازه‌ای که هرگز وجود نداشتند. آن حالت از هر دو نسخه بدتر است،
        # چون نه قدیمی است نه جدید و هیچ‌کدام از دو مسیر تست‌شده نیست.
        rm -rf "$APP_DIR/app" "$APP_DIR/alembic"
        tar xzf "$ARCHIVE" -C "$APP_DIR"
        chown -R "$OS_USER:$OS_USER" "$APP_DIR/app" "$APP_DIR/alembic" 2>/dev/null || true
        echo "کد برگردانده شد از: $ARCHIVE" >&2
    fi
    # **`restart` و نه `start`.** گامِ ۷ سرویس را *پیش از* بررسی‌هایش بالا می‌آورد،
    # پس وقتی یکی از آن بررسی‌ها می‌شکند سرویس همین حالا با کدِ **تازه** در حافظه
    # در حال اجراست. و `systemctl start` روی سرویسِ بالا هیچ کاری نمی‌کند.
    #
    # نتیجه‌اش دقیقاً همان حالتِ ترکیبی است که بالا درباره‌ی tar نوشته شده، فقط از
    # راهِ دیگر: دیسک کدِ قدیمی، فرایند کدِ تازه. ۱۴۰۵/۰۶/۲۹ همین افتاد — استقرار
    # «برگشت» ولی production ساعت‌ها اصنافِ تازه را از حافظه سرو می‌کرد و اولین
    # ری‌استارت آن را بی‌صدا عقب می‌برد. بدتر از هر دو نسخه، چون هیچ‌کدام از دو
    # مسیرِ تست‌شده نیست.
    systemctl restart "$SERVICE" 2>/dev/null || systemctl start "$SERVICE" 2>/dev/null || true
    sleep 3
    echo "وضعیت سرویس: $(systemctl is-active $SERVICE)" >&2

    # برگشت باید *ثابت* کند که کدِ در حال اجرا همان کدِ روی دیسک است، نه اینکه
    # فرض کند. یک شکستِ بی‌صدا در همین‌جا همان مینی است که این تابع قرار بود
    # خنثی‌اش کند.
    if ! curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
        echo "هشدار: سرویس بعد از برگشت پاسخ نمی‌دهد — دستی بررسی کنید" >&2
    fi
    if [[ -n "$BACKUP_BEFORE" ]]; then
        cat >&2 <<MSG

اگر اسکیمای پایگاه‌داده هم عوض شده و باید برگردد، دستی اجرا کنید:
  sudo -u postgres pg_restore -d $DB_NAME --clean --if-exists "$BACKUP_BEFORE"
MSG
    fi
    exit 1
}
trap rollback ERR

say "پروفایل: $PROFILE  ($APP_DIR، سرویس $SERVICE، پایگاه‌داده $DB_NAME، پورت $PORT)"

# --- ۰. ورودی‌ها ------------------------------------------------------------------
# قبل از دست زدن به هر چیزی. نبودِ آرشیو وب نباید بعد از توقف سرویس کشف شود.
[[ -f "$CODE_TGZ" ]] || { echo "آرشیو کد پیدا نشد: $CODE_TGZ" >&2; exit 1; }
[[ -f "$WEB_TGZ" ]] || { echo "آرشیو وبِ این پروفایل پیدا نشد: $WEB_TGZ" >&2; exit 1; }

# backup.sh ممکن است هنوز روی این مقصد نصب نشده باشد. استقرار بدون پشتیبان انجام
# نمی‌شود — نه با هشدار، اصلاً.
#
# **با `bash` صدا زده می‌شود، نه با بیتِ اجرا.** یک‌بار استقرار *بعد از* اجرای
# مهاجرت‌ها شکست خورد چون اسکریپت‌ها در گیت `100644` بودند و `tar` بی‌اجرا بازشان
# کرد. برگشت کد را برگرداند ولی دیتابیس جلو مانده بود — بدترین جای ممکن برای
# شکست. مودِ فایل چیزی است که از مخزن تا آرشیو تا دیسک باید سالم بماند و هر حلقه
# می‌تواند خرابش کند؛ `bash <file>` به هیچ‌کدام تکیه ندارد.
BACKUP_SH="$APP_DIR/backup.sh"
[[ -r "$BACKUP_SH" ]] || BACKUP_SH="$APP_DIR/scripts/backup.sh"
[[ -r "$BACKUP_SH" ]] || { echo "backup.sh روی $APP_DIR پیدا نشد؛ استقرار بدون پشتیبان انجام نمی‌شود." >&2; exit 1; }

# و پشتیبانِ *بعد از* استقرار، اسکریپتِ نسخه‌ی تازه را اجرا می‌کند — همان که هنوز
# روی دیسک نیست. پس وجودش **داخلِ آرشیو** سنجیده می‌شود، این‌جا و پیش از توقف
# سرویس. گامِ صفر باید همان چیزی را تأیید کند که گامِ آخر لازم دارد، وگرنه
# تأییدش تشریفاتی است.
tar tzf "$CODE_TGZ" scripts/backup.sh >/dev/null 2>&1 || {
    echo "آرشیوِ کد scripts/backup.sh ندارد؛ پشتیبانِ بعد از استقرار اجرا نمی‌شود." >&2
    exit 1
}

# --- ۱. پشتیبان تأییدشده، قبل از هر تغییر ---------------------------------------
say "۱/۷ پشتیبان‌گیری تأییدشده"
BACKUP_DB_NAME="$DB_NAME" bash "$BACKUP_SH" "$APP_DIR/backups"
# `|| true` لازم است: با انباشته‌شدنِ ده‌ها بکاپ، `head -1` زودتر لوله را می‌بندد و
# `ls` سیگنالِ SIGPIPE (خروجِ ۱۴۱) می‌گیرد؛ زیرِ `pipefail` این کلِ استقرار را
# «شکست‌خورده» می‌کند در حالی که خروجی (اولین خط) درست گرفته شده. با تعدادِ کمِ
# بکاپ این خطا خودش را نشان نمی‌داد چون head قبل از پرشدنِ بافرِ لوله می‌خواند.
BACKUP_BEFORE="$(ls -t "$APP_DIR"/backups/*.dump | head -1 || true)"
echo "پشتیبانِ برگشت: $BACKUP_BEFORE"

# --- ۲. آرشیو کد فعلی ------------------------------------------------------------
say "۲/۷ آرشیو کد فعلی"
tar czf "$ARCHIVE" -C "$APP_DIR" app alembic alembic.ini web .env
echo "آرشیو: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# --- ۳. توقف سرویس ---------------------------------------------------------------
say "۳/۷ توقف سرویس"
systemctl stop "$SERVICE"
echo "وضعیت: $(systemctl is-active $SERVICE || true)"

# --- ۴. استقرار کد ----------------------------------------------------------------
say "۴/۷ استقرار کد بک‌اند و وب"
# به همان دلیلِ rollback: پوشه اول خالی، بعد استخراج. وگرنه ماژولی که در نسخه‌ی
# تازه حذف شده باشد روی دیسک می‌ماند و ممکن است هنوز import شود.
rm -rf "$APP_DIR/app" "$APP_DIR/alembic"
tar xzf "$CODE_TGZ" -C "$APP_DIR" app alembic alembic.ini scripts
chown -R "$OS_USER:$OS_USER" "$APP_DIR/app" "$APP_DIR/alembic"
rm -rf "$APP_DIR/web.old" && cp -a "$APP_DIR/web" "$APP_DIR/web.old"
rm -rf "$APP_DIR/web" && mkdir -p "$APP_DIR/web"
tar xzf "$WEB_TGZ" -C "$APP_DIR/web"
echo "مهاجرت‌ها روی دیسک: $(ls "$APP_DIR"/alembic/versions/*.py | wc -l)"
echo "فایل‌های وب: $(find "$APP_DIR/web" -type f | wc -l)"

# آدرس API موقع build داخل باندل می‌نشیند (Vite هر VITE_* را همان‌جا جایگزین
# می‌کند). یعنی build اشتباه یک SPA سالم می‌سازد که به بک‌اند *دیگری* وصل است —
# اگر باندل دمو به acc.cubita.ir برود، بازدیدکننده‌ی دمو روی داده‌ی واقعی کار
# می‌کند و هیچ‌چیز خطا نمی‌دهد. تنها نشانه‌اش همین رشته داخل فایل JS است.
if ! grep -rqF "$APP_URL" "$APP_DIR/web"/assets/*.js 2>/dev/null; then
    echo "باندل وب به $APP_URL اشاره نمی‌کند — احتمالاً build پروفایل دیگری است." >&2
    grep -rhoE 'https://[a-z.]*cubita[a-z.]*' "$APP_DIR/web"/assets/*.js 2>/dev/null | sort -u | head >&2
    false
fi
echo "باندل وب به $APP_URL اشاره می‌کند ✓"

# --- ۵. تنظیمات ------------------------------------------------------------------
say "۵/۷ تنظیمات"
grep -q '^APP_URL=' "$APP_DIR/.env" || echo "APP_URL=$APP_URL" >> "$APP_DIR/.env"
grep '^APP_URL=' "$APP_DIR/.env"

# --- ۶. مهاجرت --------------------------------------------------------------------
say "۶/۷ مهاجرت پایگاه‌داده"
cd "$APP_DIR"
# لاگِ کامل در فایل می‌ماند تا اگر مهاجرت شکست خورد، خطای واقعی (نه فقط خطوطِ upgrade)
# دیده شود. نسخه‌ی قبلی فقط "Running upgrade|ERROR" را grep می‌کرد و traceback گم می‌شد.
MIGRATE_LOG="/tmp/cubita_migrate_${PROFILE}.log"
sudo -u "$OS_USER" "$APP_DIR/venv/bin/python" -m alembic upgrade head > "$MIGRATE_LOG" 2>&1 || true
grep -E "Running upgrade|ERROR|Error|error:" "$MIGRATE_LOG" || true

# نسخه‌ی انتظار از خودِ مهاجرت‌ها خوانده می‌شود، نه از یک عدد هاردکدشده.
#
# نسخه‌ی اول این خط `== "0018"` بود و بعد مهاجرت ۰۰۱۹ اضافه شد. نتیجه این بود که
# مهاجرت‌ها با موفقیت تا ۰۰۱۹ اجرا شدند و بعد همین گارد استقرار را «شکست‌خورده»
# اعلام کرد و کد را برگرداند — یعنی دقیقاً همان حالت خطرناکی ساخته شد که کل
# توقف سرویس برای اجتناب از آن بود: اسکیمای تازه با کد قدیمی. هر ثابتی که باید
# همراه چیز دیگری به‌روز شود، دیر یا زود به‌روز نمی‌شود.
EXPECTED="$(sudo -u "$OS_USER" "$APP_DIR/venv/bin/python" -m alembic heads 2>/dev/null | awk '{print $1}' | head -1)"
VERSION="$(sudo -u postgres psql -d "$DB_NAME" -tAc 'select version_num from alembic_version;' | tr -d ' ')"
echo "نسخه‌ی نهایی: $VERSION (انتظار: $EXPECTED)"
[[ -n "$EXPECTED" && "$VERSION" == "$EXPECTED" ]] \
    || { echo "نسخه‌ی مهاجرت $VERSION است ولی head برابر $EXPECTED" >&2; \
         echo "── خطای واقعیِ مهاجرت (۴۰ خطِ آخرِ $MIGRATE_LOG) ──" >&2; \
         tail -n 40 "$MIGRATE_LOG" >&2; false; }

# --- ۷. راه‌اندازی و راستی‌آزمایی ---------------------------------------------------
say "۷/۷ راه‌اندازی و راستی‌آزمایی"
systemctl start "$SERVICE"
# **۱۲۰ ثانیه و نه ۳۰.** بالاآمدنِ اپ روی همین ماشین حدودِ ۳۵ ثانیه طول می‌کشد (ایمپورتِ
# SQLAlchemy و ساختِ متادیتا)، پس سقفِ ۳۰ ثانیه یک استقرارِ **سالم** را شکست‌خورده
# می‌خواند و بی‌دلیل برمی‌گرداند — دقیقاً چیزی که ۱۴۰۵/۰۶/۲۹ اتفاق افتاد.
HEALTH_WAIT=120
for i in $(seq 1 $HEALTH_WAIT); do
    sleep 1
    curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1 && { echo "سرویس بعد از ${i} ثانیه بالا آمد"; break; }
    [[ $i -eq $HEALTH_WAIT ]] && { echo "سرویس بعد از ${HEALTH_WAIT} ثانیه پاسخ نداد" >&2; false; }
done
echo "health: $(curl -s http://127.0.0.1:$PORT/api/health)"

# اندپوینت‌های تازه باید وجود داشته باشند (۴۰۱/۴۲۲ یعنی هست ولی احراز هویت لازم دارد؛
# ۴۰۴ یعنی کد قدیمی هنوز اجرا می‌شود، که یعنی استقرار در عمل انجام نشده).
for path in /api/members /api/auth/forgot-password; do
    CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$path")"
    echo "  $path → $CODE"
    [[ "$CODE" == "404" ]] && { echo "اندپوینت تازه پیدا نشد — کد قدیمی اجرا می‌شود" >&2; false; }
done

RLS="$(sudo -u postgres psql -d "$DB_NAME" -tAc "select count(*) filter (where relforcerowsecurity) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r';" | tr -d ' ')"
echo "  جدول‌های با FORCE RLS: $RLS"
[[ "$RLS" -ge 30 ]] || { echo "RLS روی تعداد کافی جدول فعال نشد" >&2; false; }

say "پشتیبان‌گیری بعد از استقرار (با RLS فعال — آزمون واقعی)"
BACKUP_DB_NAME="$DB_NAME" bash "$APP_DIR/scripts/backup.sh" "$APP_DIR/backups"

trap - ERR

# --- چرخش آرشیوهای برگشت -----------------------------------------------------------
# هر استقرار یک tgz می‌سازد و هیچ‌کس برشان نمی‌داشت: ۸۳ فایل / ۱۲۷ مگابایت روی prod
# و ۵۰ تا روی دمو جمع شده بود. آرشیوِ دو ماه پیش بی‌مصرف است — کدی که سی مهاجرت عقب
# است نقطه‌ی برگشت نیست.
#
# مثلِ چرخشِ پشتیبانِ backup.sh، این خط عمداً *بعد* از موفقیت است: استقرارِ
# شکست‌خورده از trap برمی‌گردد و هرگز اینجا نمی‌رسد، پس آرشیوِ سالم پاک نمی‌شود.
# همان ۱۴ روزِ پشتیبان، تا دو سیاستِ متفاوت نداشته باشیم.
ROLLED="$(find "$APP_DIR" -maxdepth 1 -name 'rollback_code_*.tgz' -type f -mtime +14 -print -delete | wc -l)"
echo "چرخش: $ROLLED آرشیو برگشتِ قدیمی‌تر از ۱۴ روز حذف شد."

echo
echo "════════════════════════════════════════════"
echo " استقرار موفق — پروفایل $PROFILE، نسخه $VERSION"
echo " برگشت کد: $ARCHIVE"
echo " پشتیبان قبل از استقرار: $BACKUP_BEFORE"
echo "════════════════════════════════════════════"
