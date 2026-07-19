#!/usr/bin/env bash
# استقرار کوبیتا روی VPS — با برگشت خودکار اگر چیزی بشکند.
#
# اجرا روی سرور، به‌عنوان root:
#   /opt/hesabdari/deploy.sh
#
# پیش‌نیاز: /tmp/cubita_code.tgz و /tmp/cubita_web.tgz آپلود شده باشند.
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

APP_DIR=/opt/hesabdari
SERVICE=hesabdari-backend
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="$APP_DIR/rollback_code_$STAMP.tgz"
BACKUP_BEFORE=""

say() { echo; echo "=== $* ==="; }

rollback() {
    echo
    echo "!!! استقرار شکست خورد — برگشت به وضعیت قبل" >&2
    if [[ -f "$ARCHIVE" ]]; then
        tar xzf "$ARCHIVE" -C "$APP_DIR"
        chown -R hesabdari:hesabdari "$APP_DIR/app" "$APP_DIR/alembic" 2>/dev/null || true
        echo "کد برگردانده شد از: $ARCHIVE" >&2
    fi
    systemctl start "$SERVICE" 2>/dev/null || true
    sleep 3
    echo "وضعیت سرویس: $(systemctl is-active $SERVICE)" >&2
    if [[ -n "$BACKUP_BEFORE" ]]; then
        cat >&2 <<MSG

اگر اسکیمای پایگاه‌داده هم عوض شده و باید برگردد، دستی اجرا کنید:
  sudo -u postgres pg_restore -d hesabdari --clean --if-exists "$BACKUP_BEFORE"
MSG
    fi
    exit 1
}
trap rollback ERR

# --- ۱. پشتیبان تأییدشده، قبل از هر تغییر ---------------------------------------
say "۱/۷ پشتیبان‌گیری تأییدشده"
"$APP_DIR/backup.sh" "$APP_DIR/backups"
BACKUP_BEFORE="$(ls -t "$APP_DIR"/backups/*.dump | head -1)"
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
tar xzf /tmp/cubita_code.tgz -C "$APP_DIR" app alembic alembic.ini scripts
chown -R hesabdari:hesabdari "$APP_DIR/app" "$APP_DIR/alembic"
rm -rf "$APP_DIR/web.old" && cp -a "$APP_DIR/web" "$APP_DIR/web.old"
rm -rf "$APP_DIR/web" && mkdir -p "$APP_DIR/web"
tar xzf /tmp/cubita_web.tgz -C "$APP_DIR/web"
echo "مهاجرت‌ها روی دیسک: $(ls "$APP_DIR"/alembic/versions/*.py | wc -l)"
echo "فایل‌های وب: $(find "$APP_DIR/web" -type f | wc -l)"

# --- ۵. تنظیمات ------------------------------------------------------------------
say "۵/۷ تنظیمات"
grep -q '^APP_URL=' "$APP_DIR/.env" || echo 'APP_URL=https://acc.cubita.ir' >> "$APP_DIR/.env"
grep '^APP_URL=' "$APP_DIR/.env"

# --- ۶. مهاجرت --------------------------------------------------------------------
say "۶/۷ مهاجرت پایگاه‌داده"
cd "$APP_DIR"
sudo -u hesabdari "$APP_DIR/venv/bin/python" -m alembic upgrade head 2>&1 | grep -E "Running upgrade|ERROR" || true
VERSION="$(sudo -u postgres psql -d hesabdari -tAc 'select version_num from alembic_version;' | tr -d ' ')"
echo "نسخه‌ی نهایی: $VERSION"
[[ "$VERSION" == "0018" ]] || { echo "نسخه‌ی مهاجرت انتظار ۰۰۱۸ بود ولی $VERSION است" >&2; false; }

# --- ۷. راه‌اندازی و راستی‌آزمایی ---------------------------------------------------
say "۷/۷ راه‌اندازی و راستی‌آزمایی"
systemctl start "$SERVICE"
for i in $(seq 1 30); do
    sleep 1
    curl -sf http://127.0.0.1:8001/api/health >/dev/null 2>&1 && break
    [[ $i -eq 30 ]] && { echo "سرویس بعد از ۳۰ ثانیه پاسخ نداد" >&2; false; }
done
echo "health: $(curl -s http://127.0.0.1:8001/api/health)"

# اندپوینت‌های تازه باید وجود داشته باشند (۴۰۱/۴۲۲ یعنی هست ولی احراز هویت لازم دارد؛
# ۴۰۴ یعنی کد قدیمی هنوز اجرا می‌شود، که یعنی استقرار در عمل انجام نشده).
for path in /api/members /api/auth/forgot-password; do
    CODE="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001$path)"
    echo "  $path → $CODE"
    [[ "$CODE" == "404" ]] && { echo "اندپوینت تازه پیدا نشد — کد قدیمی اجرا می‌شود" >&2; false; }
done

RLS="$(sudo -u postgres psql -d hesabdari -tAc "select count(*) filter (where relforcerowsecurity) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r';" | tr -d ' ')"
echo "  جدول‌های با FORCE RLS: $RLS"
[[ "$RLS" -ge 30 ]] || { echo "RLS روی تعداد کافی جدول فعال نشد" >&2; false; }

say "پشتیبان‌گیری بعد از استقرار (با RLS فعال — آزمون واقعی)"
"$APP_DIR/backup.sh" "$APP_DIR/backups"

trap - ERR
echo
echo "════════════════════════════════════════════"
echo " استقرار موفق. نسخه: $VERSION"
echo " برگشت کد: $ARCHIVE"
echo " پشتیبان قبل از استقرار: $BACKUP_BEFORE"
echo "════════════════════════════════════════════"
