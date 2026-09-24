// بیلدِ «کوبیتا سازمانی» — همان کد، محصولی جدا (ENTERPRISE_PLAN.md).
//
// پیکربندیِ electron-builder از `build`ِ package.json خوانده و فقط چیزهایی که این
// نسخه را محصولِ دیگری می‌کنند عوض می‌شوند:
// - appId و productNameِ جدا → پوشه‌ی داده (userData) و ردیفِ «برنامه‌ها»ی جدا، تا
//   کنارِ کوبیتای ابری نصب شود و هیچ‌کدام نشست یا کشِ دیگری را نبیند.
// - پوشه‌ی خروجیِ جدا و **بدونِ publish** → `npm run publish-update` فقط `release/`
//   را می‌خواند، پس نصابِ سازمانی هرگز به‌اشتباه روی فیدِ آپدیتِ مشتریانِ ابری نمی‌رود.
//
// `CUBITA_EDITION=enterprise` در main فریز می‌شود (vite.config.ts)؛ rebuild-native
// هم مثلِ `npm run dist` اول اجرا می‌شود — نصابی که better-sqlite3ِ ABIِ Node را
// دارد اصلاً بالا نمی‌آید (حادثه‌ی نسخه‌ی ۱.۴.۷).
import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))

const OUT_DIR = 'release-enterprise'

//: بسته‌ی سرور (`backend/packaging/build_server_bundle.py`): exe + PostgreSQL + WinSW.
//: بی‌آن نصاب فقط کلاینت است — با هشدار، نه خطا، تا ساختِ کلاینت به Postgres وابسته نباشد.
const SERVER_BUNDLE = path.join(root, '..', 'backend', 'dist', 'server-bundle')
const hasServer = fs.existsSync(path.join(SERVER_BUNDLE, 'cubita-server.exe'))
if (!hasServer) {
  console.warn(
    `⚠ بسته‌ی سرور در ${SERVER_BUNDLE} نیست؛ نصابِ فقط-کلاینت ساخته می‌شود.\n` +
      '  برای نصابِ کامل: cd backend && venv/Scripts/python.exe packaging/build_server_bundle.py --pg-dir …',
  )
}

//: صفحه‌ی نقش و نصبِ سرور. `CUBITA_HAS_SERVER` فقط وقتی بسته واقعاً هست تعریف می‌شود.
fs.mkdirSync(path.join(root, OUT_DIR), { recursive: true })
const nshPath = path.join(root, OUT_DIR, 'installer-enterprise.nsh')
fs.writeFileSync(
  nshPath,
  (hasServer ? '!define CUBITA_HAS_SERVER\n' : '') +
    fs.readFileSync(path.join(root, 'build', 'installer-enterprise.nsh'), 'utf8'),
  'utf8',
)

const config = {
  ...pkg.build,
  appId: 'ir.ipnetcity.cubita.enterprise',
  productName: 'Cubita Enterprise',
  directories: { output: OUT_DIR },
  //: فقط برای اینکه electron-builder `latest.yml` بسازد. هیچ‌چیز خودکار آپلود نمی‌شود؛ انتشار با
  //: `scripts/publish-enterprise.mjs` است (امضا روی سرورِ ابری، کنارِ کلیدِ خصوصی).
  //: کلاینتِ نصب‌شده این نشانی را نمی‌خواند — فیدش در زمانِ اجرا سرورِ خودِ شرکت است.
  publish: [{ provider: 'generic', url: 'https://acc.cubita.ir/updates/enterprise/' }],
  artifactName: 'Cubita-Enterprise-Setup-${version}.${ext}',
  ...(hasServer ? { extraResources: [{ from: SERVER_BUNDLE, to: 'server' }] } : {}),
  nsis: {
    ...pkg.build.nsis,
    shortcutName: 'کوبیتا سازمانی',
    //: نصبِ سرور سرویسِ ویندوز و قاعده‌ی فایروال می‌سازد — دسترسیِ مدیر لازم است؛ و برنامه
    //: برای همه‌ی کاربرانِ رایانه نصب می‌شود (رایانه‌ی مشترکِ حسابداری).
    perMachine: true,
    include: nshPath,
  },
}

const env = { ...process.env, CUBITA_EDITION: 'enterprise' }
const run = (cmd) => execSync(cmd, { cwd: root, stdio: 'inherit', env, shell: true })

const configPath = path.join(root, OUT_DIR, 'electron-builder.enterprise.json')
fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8')

run('npm run build')
run('npm run rebuild-native')
run(`npx electron-builder --config "${configPath}" ${process.argv.slice(2).join(' ')}`)
