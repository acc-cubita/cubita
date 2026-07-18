// better-sqlite3 یک native addon است و باید دقیقاً با نسخه‌ی ABI الکترون (نه Node.js) ساخته شود.
// این اسکریپت به‌جای کامپایل از سورس (که به Visual Studio Build Tools نیاز دارد)،
// باینری از‌پیش‌ساخته‌شده‌ی متناظر با نسخه‌ی الکترون نصب‌شده را از prebuild-install دانلود می‌کند.
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const electronVersion = execFileSync(
  'node',
  ['-p', "require('electron/package.json').version"],
  { encoding: 'utf8' },
).trim()

const betterSqlite3Dir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  'node_modules',
  'better-sqlite3',
)

console.log(`در حال دریافت باینری better-sqlite3 برای Electron ${electronVersion}...`)
execFileSync(
  'npx',
  ['prebuild-install', '--runtime=electron', `--target=${electronVersion}`, '--arch=x64', '--platform=win32'],
  { cwd: betterSqlite3Dir, stdio: 'inherit', shell: true },
)
console.log('انجام شد.')
