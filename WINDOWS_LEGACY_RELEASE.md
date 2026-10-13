# بستهٔ کامل سازگار ویندوز — 1.9.17

مبنا: `65533d3` (PR283). این شاخه فقط بسته‌بندی و سازگاری را توسعه می‌دهد؛ کار تعمیرگاه در درخت اصلی دست‌نخورده است. هیچ پایگاه فعال، سرویس نصب‌شده یا کانال به‌روزرسانی اصلی در آزمون‌ها تغییر نمی‌کند.

## انتخاب بسته

| ویندوز مقصد | معماری | بسته |
|---|---|---|
| 7 SP1 / 8 | 32 | Legacy x86 1.9.17 |
| 7 SP1 / 8 | 64 | Legacy x64 1.9.17 |
| 8.1 | 32 | Legacy x86 1.9.17 |
| 8.1 | 64 | بستهٔ منتشرشدهٔ Windows81 1.9.16 |
| 10 | 32 | Legacy x86 1.9.17 |
| 10 / 11 | 64 | کانال اصلی سازمانی |

هر دو نصاب Legacy دارای **سرور و کلاینت** هستند؛ انتخاب نقش داخل نصاب انجام می‌شود. Windows7 RTM، Windows11 32bit و ARM هدف این بسته نیستند. پیشنهاد مرورگر قطعی نیست و انتخاب دستی مقصد بر آن مقدم است.

## پیش‌نیاز و گزارش نصب

پیش‌نیازها پیش از تغییر فایل‌ها و سرویس‌های کوبیتا بررسی می‌شوند. VC2019 14.29.30157.0 مطابق معماری همراه نصاب است؛ نسخهٔ جدیدتر موجود دوباره نصب نمی‌شود. در Windows7 SP1 دارای PowerShell2 ابتدا .NET در صورت نیاز و سپس WMF5.1 رسمی مطابق معماری **ویندوز** نصب می‌شوند. پس از نیاز به restart، نصب پیش از تغییر کوبیتا متوقف می‌شود؛ رایانه را restart و همان نصاب را دوباره اجرا کنید. Windows8 دارای PowerShell3 و .NET4.5 است و WMF مخصوص Windows7 روی آن اجرا نمی‌شود.

فایل‌های Microsoft با SHA256 ثابت کنترل می‌شوند؛ VC و .NET علاوه بر آن امضای Microsoft دارند. موفقیت صرفاً از کد خروج حدس زده نمی‌شود؛ نسخهٔ نصب‌شده دوباره بررسی می‌شود. شکست یا نیاز به restart به‌صورت موفقیت نصب کوبیتا نمایش داده نمی‌شود.

گزارش اصلی: `C:\ProgramData\Cubita\logs\install-<PID>-<Tick>.log`؛ در صورت ناتوانی ساخت پوشه، `%TEMP%\Cubita-install-<PID>-<Tick>.log`. مرحلهٔ bootstrap، معماری، نقش، کد خروج پیش‌نیاز/guard/سرور و استثنا ثبت می‌شوند. گزارش‌های `.vc.log`، `.dotnet.log` و `.dotnet-bootstrap.log` کنار آن قرار می‌گیرند. مسیر دقیق در پیام خطا نمایش داده می‌شود. فایل `.env` و رمزهای پایگاه در گزارش dump نمی‌شوند.

## ساخت جدا و منشأ فایل‌ها

رابط: Electron22.3.27، better-sqlite3 9.4.3، serialport10.5.0 و undici5.28.5؛ کانال به‌روزرسانی مدرن برای این پروفایل غیرفعال است. هویت برنامه و محل دادهٔ کاربر حفظ می‌شوند.

سرور: Python3.8.10 رسمی، PyInstaller6.11.1، SQLAlchemy2.0.35، psycopg3.2.3 خالص و libpq17.11. منبع فعلی در یک پوشهٔ جدا با LibCST به نحو Python3.8 تبدیل می‌شود؛ هش منبع و خروجی در `legacy-source.json` ثبت است. قرارداد OpenAPI با نسخهٔ مدرن مقایسه می‌شود. بستهٔ عادی Python یا کد اصلی به نسخهٔ قدیمی تبدیل نمی‌شود.

Pydantic-core2.23.4 برای هر دو معماری از منبع با Rust1.77.2 بازسازی شده است؛ نصب wheel معمولی PyPI به‌تنهایی کافی نیست، زیرا import مستقیم APIهای جدید ویندوز دارد. cryptography42.0.8 و وابستگی‌های Python3.8 در `requirements-windows-legacy.txt` مشخص‌اند؛ فهرست دقیق وابستگی‌های runtime داخل هر سرور در `runtime-dependencies.txt` قرار می‌گیرد.

PostgreSQL17.11 برای هر دو معماری از منبع رسمی با MSVC2019/Meson/Ninja و zlib1.3.1 ساخته شده است. موتور به نسخهٔ قدیمی‌تر تنزل نمی‌کند. تغییر محدود `legacy_postgres.py`، حداقل target و فراخوانی ساعت دقیق ویندوز را پوشش می‌دهد: در سیستم فاقد API دقیق، ساعت استاندارد استفاده می‌شود. فایل‌های اصیل و تغییرات هش دارند. WinSW.NET4 نسخهٔ2.12.0 با هش ثابت استفاده می‌شود؛ فایل managed AnyCPU با نام داخلی قبلی حفظ می‌شود.

`native_compatibility.py` معماری PE و چند API مستقیم ناسازگار را کنترل می‌کند. این کنترل **جای اجرای واقعی روی سیستم‌عامل مقصد نیست**. اطلاعیه‌های Python، PostgreSQL، zlib و کتابخانه‌ها همراه سرور در `third-party-notices` قرار می‌گیرند.

ساخت:

```powershell
# Builder: Python3.12 + libcst + pefile. Runtime: Python3.8 جدا با wheel بازسازی‌شده.
python backend/packaging/legacy_source.py --output <isolated-source>
python backend/packaging/build_windows_legacy.py --source <isolated-source> --python <python38.exe> --pg-dir <postgres17-prefix> --winsw <WinSW.NET4.exe> --output <fresh-output> --architecture x86 --version 1.9.17 --notices-dir <notices>
$env:CUBITA_LEGACY_ARCH='x86' # برای معماری دیگر x64
$env:CUBITA_LEGACY_SERVER_BUNDLE='<fresh-output>/server-bundle'
node desktop/scripts/dist-windows-legacy-enterprise.mjs
```

خروجی server باید مسیر تازه باشد؛ هش/نسخه/معماری آن قبل از ساخت نصاب کنترل می‌شود. تنظیمات محرمانه و پایگاه کاربر به محیط ساخت کپی نمی‌شوند.

## حدود سازگاری و ارتقا

- Windows7 SP1 باید به‌روزرسانی‌های loader و SHA-2 لازم را داشته باشد. Python3.8 به KB2533623 یا به‌روزرسانی جایگزین آن نیاز دارد؛ .NET4.6+ به پشتیبانی امضای SHA-2 نیاز دارد. این **به‌روزرسانی‌های خود ویندوز** در این نصاب خودکار نصب نمی‌شوند؛ آماده‌سازی VC/.NET/PowerShell با به‌روزرسانی سیستم‌عامل یکسان نیست. منابع: [Python3.8](https://docs.python.org/3.8/using/windows.html)، [Microsoft SHA-2](https://support.microsoft.com/en-us/topic/security-and-quality-rollup-for-net-framework-4-8-for-windows-7-sp1-and-windows-server-2008-r2-sp1-kb4600944-0bd4b1f1-57b1-f476-1208-4a17dec856c0).
- آزمون واقعی روی Windows7/8/8.1 در دسترس نبوده است؛ انتشار با اجازهٔ صریح کاربر و عنوان **آزمایشی** انجام می‌شود. `targetOsVerified:false` در metadata باقی می‌ماند. ساخت و آزمون روی Windows11، تأیید سازگاری تمام درایورها یا patchهای ویندوز مقصد نیست.
- تغییر معماری سرور با نصب روی فایل‌های دادهٔ موجود مسدود است. انتقال 32↔64 نیازمند dump/restore در نصب جداست؛ کپی pgdata مجاز نیست.
- اتصال عادی کلاینت به IP سرور و فایروال private/domain حفظ می‌شود. ابزار پیشرفتهٔ تنظیم خودکار شبکهٔ بدون مودم از cmdletهای Windows8+ استفاده می‌کند و روی Windows7 هنوز قابل استفاده نیست.
- PostgreSQL این پروفایل zlib دارد؛ SSL، ICU، LZ4 و ZSTD در ساخت فعلی فعال نیستند. پایگاه تازه UTF8/locale C و پشتیبان custom با gzip آزموده می‌شوند. پایگاه دارای ICU یا پشتیبان با LZ4/ZSTD نباید بدون تبدیل و آزمون جدا به این پروفایل منتقل شود.
- نصاب کوبیتا Authenticode ندارد؛ امضای Microsoft مربوط به پیش‌نیازهاست. SHA256 عمومی نصاب برای صحت دانلود ارائه می‌شود.

## شواهد تحویل

- Python3.8 x64 / PostgreSQL17 مستقل: **4806 passed، 3 skipped** در858.73 ثانیه. دو فایل جانبی سایت/دسکتاپ در محیط جدا اضافه شدند؛ خطای واقعی مرز زمان محدودکننده با آزمون ساعت ثابت اصلاح شد.
- پس از اصلاح نهایی PowerShell3 و افزودن آزمون مرز زمان: **84 passed** برای rate-limit، بازیابی سرویس و شبکه.
- Python3.8 x86 / PostgreSQL17 x86 مستقل: **32 passed** برای ثبت انبار، جداسازی فاکتور، برگشت بچ، گردکردن تخفیف و رقابت موجودی. پایگاه‌های آزمایشی پس از اجرا متوقف شدند.
- تبدیل منبع:6 آزمون مستقل موفق؛ OpenAPI مدرن/Legacy:679 مسیر و823 schema برابر.
- هر دو frozen server: selftest با880 route و190 فایل migration؛ نصب تازه و setup مجدد، حفظ هش `.env`/`secrets.json`، head0192،252 جدول FORCE RLS، API سالم با edition enterprise/version1.9.17، gzip dump/restore با مقدار Decimal دقیق موفق. خطای آدرس health در harness از `/health` به مسیر واقعی `/api/health` اصلاح و آزمون دوباره اجرا شد.
- Electron22 واقعی هر دو معماری: SQLite در حافظه، بارگذاری serialport و undici موفق؛ این آزمون راننده/پورت فیزیکی نیست.
- bootstrap:13 سناریو؛ پیش‌نیازها:17؛ guard:40 assertion؛ lifecycle NSIS:19 سناریو در هر یک از چهار پروفایل modern/8.1/legacy-x86/legacy-x64. همهٔ تغییرات سیستم در این آزمون‌ها mock هستند؛ نصب سراسری روی میزبان اجرا نشد.
- سایت: build و TypeScript موفق، lint بدون خطا با دو هشدار قبلی ContactSection،34 کنترل مرورگر در390/1440 موفق و تصاویر در `_deploy/windows-legacy-download-qa`. آزمون مرورگر روی Chromium میزبان است.

| فایل نهایی | اندازه | SHA256 |
|---|---:|---|
| Cubita-Enterprise-Legacy-x86-Setup-1.9.17.exe | 363493920 | `cf53e5366740504ce6353c092ac3365e00c65300d939183c85ca1ea8abbbc282` |
| Cubita-Enterprise-Legacy-x64-Setup-1.9.17.exe | 381947388 | `9743fc423e3be2c651c3d0e411563ea99a360b89b6b542ac3b598465bf8a8587` |

انتشار عمومی آزمایشی با مجوز کاربر انجام شد. هر دو فایل پس از کنترل هش کامل روی سرور در `/updates/enterprise/legacy/` قرار گرفتند و انتخابگر [سایت](https://cubita.ir/download/#windows-download) فعال شد. source در [PR284](https://github.com/acc-cubita/cubita/pull/284) است. metadata عمومی `release.json` وضعیت آزمایشی و `targetOsVerified:false` را نگه می‌دارد.

backup سایت: `/opt/cubita-marketing/dist.before-legacy-20261012T215426Z`؛ SHA256 آرشیو سایت `57c3274db981e39ab04cb0cb9353163307c32e5ec45bceebcd8574b597fcaa2d`. SHA256 نصاب اصلی و `latest.yml` پیش/پس از انتشار ثابت ماندند؛ نسخهٔ Windows81 1.9.16 بازنویسی نشد.34 کنترل مرورگر روی سایت زنده نیز موفق شدند؛ تصاویر در `_deploy/windows-legacy-download-live-qa` هستند. نتیجهٔ آخرین CI از PR قابل مشاهده است؛ کنترل HTTP کامل، جدا از کنترل هش سرور، در `_deploy/windows-legacy-public-http-verification.json` ثبت می‌شود.
