## ساخت نصاب ویندوز (Packaging)

برای ساخت یک نصاب مستقل (`.exe`) که بدون نیاز به Node/npm روی سیستم کاربر قابل‌نصب و اجراست:

```
npm run dist
```

خروجی در پوشه‌ی `release/` قرار می‌گیرد: `release/Cubita Setup <version>.exe` (نصاب NSIS) و `release/win-unpacked/` (نسخه‌ی باز-نشده، برای تست سریع بدون نصب).

نکات:
- `npm run dist`/`npm run pack` خودشان قبل از بسته‌بندی `rebuild-native` را اجرا می‌کنند — چون `better-sqlite3` یک native addon است که باید دقیقاً با ABI نسخه‌ی Electron ساخته شود، نه Node.js سیستم؛ فراموشِ این قدم یعنی نصاب برای همه‌ی کاربران با کرشِ NODE_MODULE_VERSION در بدو اجرا بالا نمی‌آید (اتفاقی که افتاد و همین‌جا مستندش کردیم).
- روی ویندوز، اولین بار که این دستور را اجرا می‌کنید ممکن است Windows Defender در حال اسکن فایل تازه‌دانلودشده‌ی `electron.exe` باشد و مرحله‌ی بسته‌بندی با خطای `EPERM: rename ... win-unpacked.tmp` شکست بخورد؛ کافیست پوشه‌ی `release/` را پاک کنید و دوباره `npm run dist` را اجرا کنید.
- نصاب فعلاً بدون گواهی امضای کد (code signing certificate) ساخته می‌شود؛ ویندوز ممکن است در اولین اجرا هشدار SmartScreen نشان دهد («More info» → «Run anyway»). برای رفع کامل این هشدار، یک گواهی امضای کد معتبر لازم است.
- `npm run pack` فقط پوشه‌ی `win-unpacked/` را می‌سازد (بدون نصاب NSIS) — برای تست سریع‌تر در حین توسعه مناسب‌تر است.

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
