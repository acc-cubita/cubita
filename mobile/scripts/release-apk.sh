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
# پیامِ آپدیت می‌دهد و کاربر را به صفحه‌ی برنامه در بازار می‌فرستد.
#
# ⚠️ **apkUrl را از latest.json برندار** — حتی با اینکه اپِ امروز آن را نمی‌خواند.
#    نسخه‌های ۷ و پیش‌تر آپدیترِ قدیمی را دارند و اگر این کلید نباشد مانیفست را
#    «نامعتبر» می‌بینند و خطا می‌دهند؛ یعنی آن کاربرها برای همیشه روی نسخه‌ی قدیمی
#    گیر می‌کنند و هیچ راهی هم برای خبردادن به آن‌ها نمی‌ماند. APK کنارِ فید بماند
#    تا آن‌ها یک‌بارِ آخر به‌صورتِ درجا به نسخه‌ی تازه بیایند و از آن پس از بازار
#    آپدیت شوند.
#
# ⚠️ دسترسیِ REQUEST_INSTALL_PACKAGES عمداً حذف شده (کافه‌بازار ردش می‌کند) و
#    SYSTEM_ALERT_WINDOW هم که بازمانده‌ی قالبِ Expo بود و هیچ‌جا استفاده نمی‌شد.
#    اگر روزی `expo prebuild` اجرا شد، `blockedPermissions` در app.json جلوی
#    برگشتنشان را می‌گیرد — ولی بعدش مانیفستِ ساخته‌شده را چک کن.
#
# ⚠️ کلیدِ امضا ثابت بماند: بیلدِ release با کلیدِ اختصاصیِ انتشار امضا می‌شود
#    (android/app/cubita-release.keystore + android/keystore.properties — هر دو خارج از گیت).
#    اندروید آپدیتِ درجا را فقط وقتی می‌پذیرد که نسخه‌ی جدید با همان کلیدِ نسخه‌ی نصب‌شده امضا
#    شده باشد. پس:
#      • از این دو فایل نسخه‌ی پشتیبانِ امن بگیر — با گم شدنشان دیگر نمی‌توان آپدیتِ همین اپ
#        را منتشر کرد (نه در فروشگاه، نه درجا) و باید با نامِ بسته‌ی جدید شروع کرد.
#      • هرگز `expo prebuild --clean` نزن — پوشه‌ی android/ را بازمی‌سازد و تنظیماتِ امضا می‌پرد.
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

# AAB فقط وقتی لازم است که برای فروشگاه بسته می‌بندیم (bundleRelease کند است).
#   bash scripts/release-apk.sh "توضیح"        → فقط APK (فیدِ آپدیت + دانلودِ مستقیم)
#   bash scripts/release-apk.sh "توضیح" --aab  → APK + AAB (برای کافه‌بازار/مایکت)
# --reinstall را فقط برای نسخه‌ای بزن که کلیدِ امضایش عوض شده: اپ آن‌وقت به کاربر
# توضیح می‌دهد که باید یک‌بار حذف/نصب کند (وگرنه نصب بی‌دلیل شکست می‌خورد).
WANT_AAB=0
REINSTALL=false
for arg in "${@:2}"; do
  [[ "$arg" == "--aab" ]] && WANT_AAB=1
  [[ "$arg" == "--reinstall" ]] && REINSTALL=true
done

echo "==> ساختِ release برای نسخه‌ی $VN (versionCode $VC)"
if [[ -f android/keystore.properties ]]; then
  echo "    امضا: کلیدِ اختصاصیِ انتشار (keystore.properties)"
else
  echo "    ⚠️ امضا: کلیدِ debug — android/keystore.properties پیدا نشد!" >&2
fi

if (( WANT_AAB )); then
  ( cd android && ./gradlew assembleRelease bundleRelease )
else
  ( cd android && ./gradlew assembleRelease )
fi

APK_SRC="android/app/build/outputs/apk/release/app-release.apk"
[[ -f "$APK_SRC" ]] || { echo "APK ساخته نشد: $APK_SRC" >&2; exit 1; }

mkdir -p release
APK_OUT="release/cubita-v${VC}.apk"
cp "$APK_SRC" "$APK_OUT"

AAB_OUT=""
if (( WANT_AAB )); then
  AAB_SRC="android/app/build/outputs/bundle/release/app-release.aab"
  if [[ -f "$AAB_SRC" ]]; then
    AAB_OUT="release/cubita-v${VC}.aab"
    cp "$AAB_SRC" "$AAB_OUT"
  else
    echo "هشدار: AAB ساخته نشد ($AAB_SRC)" >&2
  fi
fi

# latest.json — apkUrl نسبی است و اپ آن را نسبت به پوشه‌ی فید resolve می‌کند.
cat > release/latest.json <<EOF
{
  "versionCode": ${VC},
  "versionName": "${VN}",
  "apkUrl": "cubita-v${VC}.apk",
  "notes": "${NOTES}",
  "mandatory": false,
  "reinstall": ${REINSTALL}
}
EOF

SIZE="$(du -h "$APK_OUT" | cut -f1)"
echo ""
echo "==> آماده شد:"
echo "    $APK_OUT ($SIZE)"
echo "    release/latest.json"
[[ -n "$AAB_OUT" ]] && echo "    $AAB_OUT ($(du -h "$AAB_OUT" | cut -f1)) — برای کافه‌بازار/مایکت"
echo ""
echo "==> برای انتشارِ زنده روی سرور (فیدِ آپدیت):"
echo "    scp release/cubita-v${VC}.apk release/latest.json root@62.60.129.39:/opt/hesabdari/updates/android/"
echo ""
echo "    (latest.json باید آخر آپلود شود تا کاربران هرگز به APKی که هنوز نرسیده اشاره نکنند.)"
echo ""
echo "==> و به‌روزکردنِ لینکِ پایدارِ صفحه‌ی دانلودِ سایت:"
echo "    ssh root@62.60.129.39 'cd /opt/hesabdari/updates/android && cp -f cubita-v${VC}.apk cubita-latest.apk && chown hesabdari:hesabdari cubita-latest.apk'"
