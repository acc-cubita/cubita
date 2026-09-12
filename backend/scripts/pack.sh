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
tar -czf "$WEB" -C desktop/dist .
echo "$WEB  ($(du -h "$WEB" | cut -f1))"

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

# ۵) مهاجرت‌ها و باندل
echo "  مهاجرت‌ها: $(ls "$TMP"/alembic/versions/*.py | wc -l) (آخرین: $(ls "$TMP"/alembic/versions/*.py | sort | tail -1 | xargs basename))"
echo "  فایل‌های وب: $(tar tzf "$WEB" | grep -c '[^/]$')"

say "checksum"
sha256sum "$CODE" "$WEB"
