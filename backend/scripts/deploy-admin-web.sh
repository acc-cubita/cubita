#!/usr/bin/env bash
# استقرارِ اپِ ستاد (admin.cubita.ir) — فقط فایلِ ایستا.
#
# اجرا روی سرور:
#   bash /opt/cubita-admin/deploy-admin-web.sh
# ورودی: /tmp/cubita_web_admin.tgz (خروجیِ backend/scripts/pack.sh)
#
# **چرا اسکریپتِ جدا و نه پروفایلِ سومِ `deploy.sh`.** آن اسکریپت هفت گام دارد
# که پنج‌تایشان اینجا بی‌معنا هستند: آرشیوِ `app alembic alembic.ini web .env`،
# توقفِ سرویس، مهاجرتِ alembic، و شمارشِ جدول‌های FORCE RLS. اپِ ستاد نه کدِ
# پایتون دارد، نه دیتابیس، نه سرویسِ systemd — فقط چند فایلِ ایستا که منبعِ
# حقیقتشان git است و برگشتشان یک `mv`.
#
# **یک تفاوتِ عمدی با `deploy.sh`:** آنجا اول استخراج می‌شود و بعد آدرسِ باندل
# grep می‌شود، پس باندلِ اشتباه تا لحظه‌ی rollback روی ریشه‌ی زنده می‌نشیند.
# اینجا برعکس است: اول در `web.new` باز می‌شود، سنجیده می‌شود، و فقط بعد جابه‌جا
# می‌شود. ریشه‌ی زنده هرگز حتی یک لحظه باندلِ نادرست را نمی‌بیند.
set -euo pipefail

ADMIN_DIR="${ADMIN_DIR:-/opt/cubita-admin}"
WEB_TGZ="${WEB_TGZ:-/tmp/cubita_web_admin.tgz}"
APP_URL="${APP_URL:-https://admin.cubita.ir}"

say() { echo; echo "=== $* ==="; }

# --- ۰. ورودی --------------------------------------------------------------------
say "۰/۴ بررسیِ ورودی"
[[ -f "$WEB_TGZ" ]] || { echo "بسته نیست: $WEB_TGZ" >&2; exit 1; }
[[ -d "$ADMIN_DIR" ]] || { echo "پوشه نیست: $ADMIN_DIR — اول vhost و پوشه را بساز" >&2; exit 1; }
tar tzf "$WEB_TGZ" ./index.html >/dev/null 2>&1 || tar tzf "$WEB_TGZ" index.html >/dev/null
echo "بسته: $(du -h "$WEB_TGZ" | cut -f1)، $(tar tzf "$WEB_TGZ" | grep -c '[^/]$') فایل"

# --- ۱. استخراج و سنجش، پیش از لمسِ ریشه‌ی زنده ------------------------------------
say "۱/۴ استخراج در web.new"
rm -rf "$ADMIN_DIR/web.new"
mkdir -p "$ADMIN_DIR/web.new"
tar xzf "$WEB_TGZ" -C "$ADMIN_DIR/web.new"

if ! grep -rqF "$APP_URL" "$ADMIN_DIR/web.new"/assets/*.js 2>/dev/null; then
    echo "باندل به $APP_URL اشاره نمی‌کند — احتمالاً باندلِ اپِ مشتری است." >&2
    grep -rhoE 'https://[a-z.]*cubita[a-z.]*' "$ADMIN_DIR/web.new"/assets/*.js 2>/dev/null | sort -u | head >&2
    rm -rf "$ADMIN_DIR/web.new"
    exit 1
fi
echo "باندل به $APP_URL اشاره می‌کند ✓"

# --- ۲. جابه‌جایی ------------------------------------------------------------------
say "۲/۴ جابه‌جایی"
rm -rf "$ADMIN_DIR/web.old"
[[ -d "$ADMIN_DIR/web" ]] && mv "$ADMIN_DIR/web" "$ADMIN_DIR/web.old"
mv "$ADMIN_DIR/web.new" "$ADMIN_DIR/web"
echo "web.old نقطه‌ی برگشت است"

rollback() {
    echo; echo "!!! شکست — برگرداندن" >&2
    if [[ -d "$ADMIN_DIR/web.old" ]]; then
        rm -rf "$ADMIN_DIR/web"
        mv "$ADMIN_DIR/web.old" "$ADMIN_DIR/web"
        echo "باندلِ قبلی برگشت" >&2
    fi
    exit 1
}

# --- ۳. کاوش ----------------------------------------------------------------------
# هر سه لازم‌اند و هرکدام چیزِ متفاوتی را می‌سنجند.
say "۳/۴ کاوش"
code=$(curl -fsS -o /dev/null -w '%{http_code}' "$APP_URL/" || echo 000)
[[ "$code" == 200 ]] || { echo "صفحه: $code" >&2; rollback; }
echo "GET /  → ۲۰۰ ✓"

code=$(curl -fsS -o /dev/null -w '%{http_code}' "$APP_URL/api/health" || echo 000)
[[ "$code" == 200 ]] || { echo "/api/health: $code — vhost مسیرِ /api/ را پراکسی نمی‌کند" >&2; rollback; }
echo "GET /api/health → ۲۰۰ ✓"

# **کاوشِ تعیین‌کننده.** ۴۰۴ یعنی nginx به‌جای پراکسی، fallbackِ SPA را برگردانده
# — دقیقاً شکلِ خرابیِ دمو: اپ سالم به‌نظر می‌رسد و بی‌صدا به بک‌اندِ اشتباه (یا
# به هیچ بک‌اندی) وصل است. ۴۰۱ یعنی درخواست واقعاً به FastAPI رسیده.
code=$(curl -sS -o /dev/null -w '%{http_code}' "$APP_URL/api/admin/auth/me" || echo 000)
[[ "$code" == 401 ]] || { echo "/api/admin/auth/me: $code (باید ۴۰۱ باشد)" >&2; rollback; }
echo "GET /api/admin/auth/me → ۴۰۱ ✓"

# --- ۴. پایان ---------------------------------------------------------------------
say "۴/۴ تمام"
echo "اپِ ستاد مستقر شد: $APP_URL"
echo "برگشت در صورتِ نیاز:  rm -rf $ADMIN_DIR/web && mv $ADMIN_DIR/web.old $ADMIN_DIR/web"
echo
echo "کاوشِ آخر دستِ آدم است: یک بار وارد شو و ببین دیتابیس همانی است که انتظار"
echo "داری — /api/admin/diagnostics نامِ دیتابیس و نسخه‌ی مهاجرت را می‌گوید."
