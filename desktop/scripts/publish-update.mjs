/**
 * انتشار بسته‌ی دسکتاپ روی کانال به‌روزرسانی.
 *
 * اجرا:  node scripts/publish-update.mjs
 *
 * **چرا اسکریپت و نه دستور دستی:** انتشار سه فایل دارد و ترتیبشان مهم است.
 * latest.yml باید *آخر* برود — همان فایلی است که به کلاینت می‌گوید نسخه‌ی تازه‌ای
 * هست. اگر اول برود، اپ‌ها نسخه‌ی جدید را می‌بینند و دنبال فایلی می‌گردند که هنوز
 * آپلود نشده و خطا می‌گیرند. یک دستور دستی این ترتیب را دیر یا زود اشتباه می‌کند.
 *
 * **چرا artifactName در package.json فاصله ندارد** (`Cubita-Setup-1.0.1.exe` و نه
 * `Cubita Setup 1.0.1.exe`): نام پیش‌فرض فاصله داشت و همان فاصله‌ها سه بار شکستند —
 * یک‌بار وقتی backslash فرارِ فاصله جزئی از نام فایل روی سرور شد، یک‌بار وقتی
 * نقل‌قول همین بلا را سر نام آورد، و یک‌بار در URL که باید encode می‌شد. نامی که
 * از scp و nginx و YAML و URL رد می‌شود نباید فاصله داشته باشد؛ این ارزان‌ترین
 * جای رفع مشکل است.
 */
import { execFileSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(HERE, '..')
const RELEASE = path.join(ROOT, 'release')

const HOST = process.env.CUBITA_DEPLOY_HOST ?? 'root@62.60.129.39'
const KEY = process.env.CUBITA_DEPLOY_KEY ?? path.join(process.env.HOME ?? '', '.ssh', 'ipnet_vps')
const REMOTE = '/opt/hesabdari/updates'

const version = JSON.parse(readFileSync(path.join(ROOT, 'package.json'), 'utf8')).version
if (version === '0.0.0') {
  console.error('نسخه هنوز 0.0.0 است. بسته‌ای که نسخه ندارد قابل ردیابی نیست.')
  process.exit(1)
}

// باید با artifactName در package.json یکی باشد — عمداً بدون فاصله.
const installer = `Cubita-Setup-${version}.exe`
const files = [installer, `${installer}.blockmap`, 'latest.yml']

for (const f of files) {
  if (!existsSync(path.join(RELEASE, f))) {
    console.error(`فایل انتشار پیدا نشد: ${f}\nاول اجرا کنید: npm run dist`)
    process.exit(1)
  }
}

const ssh = (cmd) => execFileSync('ssh', ['-i', KEY, '-o', 'StrictHostKeyChecking=no', HOST, cmd], { stdio: 'inherit' })

// مسیر مقصد خام پاس داده می‌شود، بدون نقل‌قول و بدون backslash. scp مدرن روی SFTP
// کار می‌کند و مسیر را *عیناً* می‌گیرد؛ هر escape ای که اینجا اضافه شود جزئی از
// نام فایل می‌شود. با artifactName بدون فاصله، این اصلاً موضوعیت ندارد — ولی
// نوشته می‌ماند چون هر دو اشتباه (نقل‌قول و backslash) یک‌بار اتفاق افتادند.
const scp = (local, remoteName) =>
  execFileSync('scp', ['-i', KEY, '-o', 'StrictHostKeyChecking=no', local, `${HOST}:${REMOTE}/${remoteName}`], {
    stdio: 'inherit',
  })

console.log(`انتشار نسخه ${version}`)

// نصب‌کننده و blockmap اول. latest.yml آخر — تا هیچ کلاینتی نسخه‌ای را نبیند که
// فایلش هنوز نرسیده.
for (const f of [installer, `${installer}.blockmap`]) {
  console.log(`  آپلود ${f} …`)
  scp(path.join(RELEASE, f), f)
}

console.log('  آپلود latest.yml …')
scp(path.join(RELEASE, 'latest.yml'), 'latest.yml')

ssh(`chown -R hesabdari:hesabdari ${REMOTE} && ls -la ${REMOTE}`)

// راستی‌آزمایی از بیرون: نامی که در latest.yml نوشته شده باید واقعاً قابل دانلود
// باشد. بدون این، انتشارِ شکسته «موفق» گزارش می‌شود و فقط وقتی کشف می‌شود که
// اپ یک مشتری به‌روزرسانی را نصفه رها کند.
const base = 'https://acc.cubita.ir/updates'
const check = (url) =>
  execFileSync('curl', ['-s', '-o', '/dev/null', '-w', '%{http_code}', '-I', url], { encoding: 'utf8' }).trim()

const ymlCode = check(`${base}/latest.yml`)
const exeCode = check(`${base}/${installer}`)
console.log(`\nراستی‌آزمایی:  latest.yml → ${ymlCode}   نصب‌کننده → ${exeCode}`)
if (ymlCode !== '200' || exeCode !== '200') {
  console.error('انتشار ناقص است: فایل‌ها از بیرون در دسترس نیستند.')
  process.exit(1)
}

console.log(`\nمنتشر شد: https://acc.cubita.ir/updates/latest.yml`)
