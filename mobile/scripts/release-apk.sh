#!/usr/bin/env bash
# ساختِ نسخه‌ی release و آماده‌سازیِ فیدِ آپدیتِ درون‌برنامه‌ای.
#
# روالِ انتشارِ هر توسعه‌ی تازه‌ی اپ اندروید:
#   1) در android/app/build.gradle مقدارِ versionCode را +۱ و versionName را به‌روز کن
#      (و همان‌ها را در app.json: version + android.versionCode). versionCode باید همیشه
#      بزرگ‌تر شود وگرنه اندروید آپدیت را «تازه‌تر» نمی‌بیند.
#   2) این اسکریپت را اجرا کن:  bash scripts/release-apk.sh "توضیحِ این نسخه"
#   3) دو فایلِ خروجی در release/ را به سرور بفرست (فرمانِ scp را خودِ اسکریپت چاپ می‌کند).
#
# اپ روی هر دستگاه، هنگامِ باز شدن latest.json را می‌خواند؛ اگر versionCode تازه‌تر بود
# پیامِ آپدیت می‌دهد و APK را دانلود و نصب می‌کند. دیگر لازم نیست فایل دستی جابه‌جا شود.
#
# ⚠️ کلیدِ امضا ثابت بماند: بیلدِ release با android/app/debug.keystore امضا می‌شود. اندروید
#    آپدیتِ درجا را فقط وقتی می‌پذیرد که نسخه‌ی جدید با همان کلیدِ نسخه‌ی نصب‌شده امضا شده باشد.
#    پس هرگز `expo prebuild --clean` نزن — آن، پوشه‌ی android/ (و debug.keystore) را بازمی‌سازد،
#    امضا عوض می‌شود، و کاربران دیگر نمی‌توانند از داخلِ اپ آپدیت شوند (باید دستی حذف/نصب کنند).
set -euo pipefail

cd "$(dirname "$0")/.."
NOTES="${1:-به‌روزرسانیِ کوبیتا}"

GRADLE="android/app/build.gradle"
VC="$(grep -oE 'versionCode[[:space:]]+[0-9]+' "$GRADLE" | head -1 | grep -oE '[0-9]+')"
VN="$(grep -oE 'versionName[[:space:]]+"[^"]+"' "$GRADLE" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')"

if [[ -z "$VC" || -z "$VN" ]]; then
  echo "نتوانستم versionCode/versionName را از $GRADLE بخوانم" >&2
  exit 1
fi

echo "==> ساختِ release برای نسخه‌ی $VN (versionCode $VC)"
( cd android && ./gradlew assembleRelease )

APK_SRC="android/app/build/outputs/apk/release/app-release.apk"
[[ -f "$APK_SRC" ]] || { echo "APK ساخته نشد: $APK_SRC" >&2; exit 1; }

mkdir -p release
APK_OUT="release/cubita-v${VC}.apk"
cp "$APK_SRC" "$APK_OUT"

# latest.json — apkUrl نسبی است و اپ آن را نسبت به پوشه‌ی فید resolve می‌کند.
cat > release/latest.json <<EOF
{
  "versionCode": ${VC},
  "versionName": "${VN}",
  "apkUrl": "cubita-v${VC}.apk",
  "notes": "${NOTES}",
  "mandatory": false
}
EOF

SIZE="$(du -h "$APK_OUT" | cut -f1)"
echo ""
echo "==> آماده شد:"
echo "    $APK_OUT ($SIZE)"
echo "    release/latest.json"
echo ""
echo "==> برای انتشارِ زنده روی سرور (فیدِ آپدیت):"
echo "    scp release/cubita-v${VC}.apk release/latest.json root@62.60.129.39:/opt/hesabdari/updates/android/"
echo ""
echo "    (latest.json باید آخر آپلود شود تا کاربران هرگز به APKی که هنوز نرسیده اشاره نکنند.)"
