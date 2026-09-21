#!/usr/bin/env bash
# بسته‌های استقرار را می‌سازد — و می‌آزمایدشان.
#
# اجرا از ریشه‌ی مخزن:
#   bash backend/scripts/pack.sh [مقصد]
#
# **چرا اسکریپت و نه دو خط دستور.** دو استقرار پشتِ هم شکست خوردند، هر دو
# به‌خاطرِ *شکلِ بسته* نه محتوایش:
#
#   ۱. `git archive HEAD backend` پیشوندِ `backend/` می‌گذارد، ولی `deploy.sh`
#      خطِ ۱۲۸ صریحاً `app alembic alembic.ini scripts` را از ریشه می‌خواهد.
#      نتیجه: `tar: app: Not found in archive`.
#
#   ۲. و `git archive` روی ویندوز با `core.autocrlf=true` پایان‌خط‌ها را به CRLF
#      تبدیل می‌کند — هرچند blob در مخزن LF است. نتیجه:
#      `/usr/bin/env: 'bash\r': No such file or directory`.
#
# هر دو فقط *بعد از* رسیدن به سرور دیده می‌شدند، یکی‌شان بعد از اجرای
# مهاجرت‌ها. پس ساختِ بسته باید یک مسیرِ آزموده باشد، نه دستوری که هر بار از نو
# تایپ می‌شود.
set -euo pipefail

DEST="${1:-dist}"
mkdir -p "$DEST"
CODE="$DEST/cubita_code.tgz"
WEB="$DEST/cubita_web_production.tgz"
# اپِ ستاد (admin.cubita.ir). فقط اگر `admin/dist` ساخته شده باشد بسته می‌شود؛
# استقرارِ بک‌اند بی‌نیاز از آن است و هر بار ساختنش اجباری نیست.
ADMIN="$DEST/cubita_web_admin.tgz"

say() { echo; echo "=== $* ==="; }

# --- بسته‌ی کد ---------------------------------------------------------------------
# `HEAD:backend` نه `HEAD backend` — تا ریشه‌ی آرشیو همان چیزی باشد که
# `deploy.sh` استخراج می‌کند.
#
# `core.autocrlf=false` لازم است و نه سلیقه: آرشیوِ زیردرخت `.gitattributes`ِ
# ریشه را نمی‌بیند، پس قاعده‌ی `eol=lf` اعمال نمی‌شود و تنظیمِ محلیِ ویندوز
# برنده می‌شود.
say "بسته‌ی کد"
git -c core.autocrlf=false archive --format=tar HEAD:backend | gzip > "$CODE"
echo "$CODE  ($(du -h "$CODE" | cut -f1))"

# --- بسته‌ی وب ---------------------------------------------------------------------
say "بسته‌ی وب"
[[ -f desktop/dist/index.html ]] || {
    echo "desktop/dist ساخته نشده. اول: cd desktop && npm run build" >&2
    exit 1
}

# **وجودِ `dist` کافی نیست — تازگی‌اش هم باید سنجیده شود.**
#
# ۱۴۰۵/۰۶/۲۹ بسته‌ای مستقر شد که کدِ بک‌اندش سرِ `master` بود ولی وبش بیلدی از
# چند ساعت قبل: قابلیتی که همان روز مرج شده بود روی production ناپدید شد و
# همکار فکر کرد مرج کارش را برگردانده. هیچ گامی شکست نخورده بود — `dist` فقط
# قدیمی بود و این اسکریپت بی‌صدا بسته‌بندی‌اش کرد.
#
# پس اگر هر فایلِ منبعی از `index.html`ِ بیلد تازه‌تر باشد، این‌جا **می‌ایستیم**.
# هشدار کافی نیست: هشدار در خروجیِ یک اسکریپتِ موفق دیده نمی‌شود.
NEWER=$(find desktop/src desktop/index.html desktop/vite.config.ts desktop/package.json \
            -type f -newer desktop/dist/index.html -print -quit 2>/dev/null || true)
if [[ -n "$NEWER" ]]; then
    cat >&2 <<MSG
بیلدِ وب کهنه است — دست‌کم یک فایلِ منبع از آن تازه‌تر است:
  $NEWER
  بیلد: $(date -r desktop/dist/index.html '+%Y-%m-%d %H:%M')

اول بیلد کن، بعد بسته بساز:
  cd desktop && npm run build && cd ..
  bash backend/scripts/pack.sh
MSG
    exit 1
fi
tar -czf "$WEB" -C desktop/dist .
echo "$WEB  ($(du -h "$WEB" | cut -f1))"

# --- بسته‌ی اپِ ستاد ---------------------------------------------------------------
if [[ -f admin/dist/index.html ]]; then
    say "بسته‌ی اپِ ستاد"
    # همان قاعده‌ی کهنگیِ بالا — به همان دلیل.
    NEWER_ADMIN=$(find admin/src admin/index.html admin/vite.config.ts admin/package.json                        -type f -newer admin/dist/index.html -print -quit 2>/dev/null || true)
    if [[ -n "$NEWER_ADMIN" ]]; then
        cat >&2 <<MSG
بیلدِ اپِ ستاد کهنه است — دست‌کم یک فایلِ منبع از آن تازه‌تر است:
  $NEWER_ADMIN
  بیلد: $(date -r admin/dist/index.html '+%Y-%m-%d %H:%M')

  cd admin && VITE_API_URL=https://admin.cubita.ir npm run build && cd ..
MSG
        exit 1
    fi
    tar -czf "$ADMIN" -C admin/dist .
    echo "$ADMIN  ($(du -h "$ADMIN" | cut -f1))"
else
    echo
    echo "(admin/dist نیست — بسته‌ی اپِ ستاد ساخته نشد)"
fi

# --- آزمون ------------------------------------------------------------------------
# آنچه روی سرور اتفاق می‌افتد، همین‌جا یک بار انجام می‌شود. هر شکستی که این‌جا
# دیده شود، شکستی است که پیش از توقفِ سرویس دیده شده.
say "آزمون"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ۱) همان استخراجی که `deploy.sh` خطِ ۱۲۸ می‌زند
tar xzf "$CODE" -C "$TMP" app alembic alembic.ini scripts
echo "  استخراجِ app/alembic/alembic.ini/scripts  ✓"

# ۲) هر اسکریپتِ پوسته باید LF و قابلِ تفسیر باشد
for f in "$TMP"/scripts/*.sh; do
    cr="$(tr -dc '\r' < "$f" | wc -c)"
    [[ "$cr" -eq 0 ]] || { echo "  ✗ $(basename "$f"): $cr بایتِ CR — روی لینوکس اجرا نمی‌شود" >&2; exit 1; }
    bash -n "$f" || { echo "  ✗ $(basename "$f"): نحو" >&2; exit 1; }
    echo "  $(basename "$f"): LF، نحو سالم، مود $(stat -c %a "$f")  ✓"
done

# ۳) چیزی که `deploy.sh` گامِ آخر لازم دارد
tar tzf "$CODE" scripts/backup.sh >/dev/null
echo "  scripts/backup.sh در آرشیو  ✓"

# ۴) راز نباید بیرون برود
if tar tzf "$CODE" | grep -Eq '(^|/)\.env$|\.pem$|\.key$'; then
    echo "  ✗ آرشیو فایلِ راز دارد" >&2
    exit 1
fi
echo "  بدونِ فایلِ راز  ✓"

# ۵) **آدرسِ APIِ بیک‌شده** — گاردی که جابه‌جاییِ دو باندل را پیش از آپلود می‌گیرد.
#
# `deploy.sh` گامِ ۴ فقط می‌سنجد که باندل آدرسِ *درست* را دارد؛ نمی‌سنجد که
# آدرسِ *غلط* را ندارد. با دو باندلِ هم‌شکل این کافی نیست: باندلِ ستاد اگر با
# acc.cubita.ir بیلد شود، گاردِ production هم قبولش می‌کند و دو اپ بی‌صدا
# جابه‌جا می‌شوند. پس هر بسته باید مبدأِ خودش را داشته باشد و مبدأِ آن یکی را نه.
#
# با `https://` کامل سنجیده می‌شود، نه نامِ میزبانِ خالی: متنِ راهنمای اپِ ستاد
# عمداً رشته‌ی «acc.cubita.ir» را دارد («برای ورود به نرم‌افزار به acc… بروید»).
assert_origin() {
    local tgz="$1" want="$2" avoid="$3" dir
    dir="$(mktemp -d)"
    tar xzf "$tgz" -C "$dir"
    if ! grep -rqF "$want" "$dir"/assets/*.js 2>/dev/null; then
        echo "  ✗ $(basename "$tgz") به $want اشاره نمی‌کند" >&2
        grep -rhoE 'https://[a-z.]*cubita[a-z.]*' "$dir"/assets/*.js 2>/dev/null | sort -u | head >&2
        rm -rf "$dir"; return 1
    fi
    if grep -rqF "$avoid" "$dir"/assets/*.js 2>/dev/null; then
        echo "  ✗ $(basename "$tgz") آدرسِ $avoid را هم دارد — باندلِ اشتباه؟" >&2
        rm -rf "$dir"; return 1
    fi
    rm -rf "$dir"
    echo "  $(basename "$tgz") → $want  ✓"
}
assert_origin "$WEB" "https://acc.cubita.ir" "https://admin.cubita.ir"
[[ -f "$ADMIN" ]] && assert_origin "$ADMIN" "https://admin.cubita.ir" "https://acc.cubita.ir"

# ۶) مهاجرت‌ها و باندل
echo "  مهاجرت‌ها: $(ls "$TMP"/alembic/versions/*.py | wc -l) (آخرین: $(ls "$TMP"/alembic/versions/*.py | sort | tail -1 | xargs basename))"
echo "  فایل‌های وب: $(tar tzf "$WEB" | grep -c '[^/]$')"

say "checksum"
if [[ -f "$ADMIN" ]]; then
    sha256sum "$CODE" "$WEB" "$ADMIN"
else
    sha256sum "$CODE" "$WEB"
fi
