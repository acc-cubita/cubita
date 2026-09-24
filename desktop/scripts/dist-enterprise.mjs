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

const config = {
  ...pkg.build,
  appId: 'ir.ipnetcity.cubita.enterprise',
  productName: 'Cubita Enterprise',
  directories: { output: OUT_DIR },
  publish: null,
  artifactName: 'Cubita-Enterprise-Setup-${version}.${ext}',
  nsis: { ...pkg.build.nsis, shortcutName: 'کوبیتا سازمانی' },
}

const env = { ...process.env, CUBITA_EDITION: 'enterprise' }
const run = (cmd) => execSync(cmd, { cwd: root, stdio: 'inherit', env, shell: true })

fs.mkdirSync(path.join(root, OUT_DIR), { recursive: true })
const configPath = path.join(root, OUT_DIR, 'electron-builder.enterprise.json')
fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8')

run('npm run build')
run('npm run rebuild-native')
run(`npx electron-builder --config "${configPath}" ${process.argv.slice(2).join(' ')}`)
