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
import { createHash } from 'node:crypto'
import { execFileSync, spawn } from 'node:child_process'
import { readFileSync, existsSync, mkdtempSync, rmSync, readdirSync, statSync } from 'node:fs'
import { request as httpsRequest } from 'node:https'
import { tmpdir } from 'node:os'
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

// مسیر مقصد خام پاس داده می‌شود، بدون نقل‌قول و بدون backslash. scp مدرن روی SFTP
// کار می‌کند و مسیر را *عیناً* می‌گیرد؛ هر escape ای که اینجا اضافه شود جزئی از
// نام فایل می‌شود. با artifactName بدون فاصله، این اصلاً موضوعیت ندارد — ولی
// نوشته می‌ماند چون هر دو اشتباه (نقل‌قول و backslash) یک‌بار اتفاق افتادند.
const BASE_OPTS = ['-i', KEY, '-o', 'StrictHostKeyChecking=no', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']

// **چرا یک اتصال ماندگار (ControlMaster) و نه یک اتصال تازه به‌ازای هر تکه:**
// نصب‌کننده روی این کانال سه‌بار جور دیگری شکست خورد. اول با «Connection reset
// by peer» وسط یک انتقال پیوسته‌ی ۱۱۶ مگابایتی — پس فایل تکه‌تکه شد. بعد، با
// تکه‌های ۱۵ و ۵ مگابایتی، نه «قطع وسط راه» بلکه «Connection timed out» روی
// خودِ TCP port 22 دیدم — یعنی این‌بار مشکل انتقال داده نبود، تعداد اتصال SSH
// تازه در بازه‌ی کوتاه بود (هر تکه یک هندشیک SSH جدید، و این‌جا احتمالاً یک
// محدودیت نرخ اتصال روی خودِ VPS یا مسیر شبکه است). راه‌حل تکه‌های کوچک‌تر نبود؛
// تعداد اتصال‌ها بود. ControlMaster یک‌بار وصل می‌شود و همه‌ی تکه‌ها از همان
// کانال باز رد می‌شوند — چه رگرسیون رخ بدهد چه ندهد، این عدد اتصال جدید را از
// ده‌ها به یکی می‌رساند.
const CONTROL_PATH = path.join(tmpdir(), `cubita-ssh-ctrl-${process.pid}`)
const SCP_OPTS = [...BASE_OPTS, '-o', `ControlPath=${CONTROL_PATH}`]

function startControlMaster() {
  const master = spawn(
    'ssh',
    [...BASE_OPTS, '-M', '-N', '-o', `ControlPath=${CONTROL_PATH}`, '-o', 'ControlPersist=600', HOST],
    { stdio: 'ignore', detached: false },
  )
  master.on('error', () => {}) // اگر ماستر نساخته شد، هر scp بعدی خودش یک اتصال معمولی می‌زند
  // اتصال async است؛ به‌جای مکث کور، چک می‌کنیم که کانال واقعاً آماده شده.
  for (let i = 0; i < 20; i++) {
    try {
      execFileSync('ssh', ['-o', `ControlPath=${CONTROL_PATH}`, '-O', 'check', HOST], { stdio: 'ignore' })
      console.log('  اتصال ماندگار SSH برقرار شد')
      return master
    } catch {
      execFileSync(process.execPath, ['-e', 'setTimeout(()=>{}, 500)'], { stdio: 'ignore' })
    }
  }
  console.log('  اتصال ماندگار برقرار نشد؛ هر تکه اتصال جدای خودش را می‌زند')
  return master
}

function stopControlMaster() {
  try {
    execFileSync('ssh', ['-o', `ControlPath=${CONTROL_PATH}`, '-O', 'exit', HOST], { stdio: 'ignore' })
  } catch { /* اگر ماستر از اول برقرار نشده بود، چیزی برای بستن نیست */ }
}

const scpOnce = (local, remotePath) =>
  execFileSync('scp', [...SCP_OPTS, local, `${HOST}:${remotePath}`], { stdio: 'inherit', timeout: 5 * 60 * 1000 })
const ssh = (cmd) => execFileSync('ssh', [...SCP_OPTS, HOST, cmd], { stdio: 'inherit' })

// نصب‌کننده دوبار پشت‌سرهم با «Connection reset by peer» شکست خورد — یک قطعی
// شبکه‌ی واقعی روی انتقال ۱۱۶ مگابایتی پیوسته، نه کندی. راه‌حل تکرار همان تلاش
// نبود؛ چیزی که وسط راه قطع می‌شود باید بتواند از همان‌جا ادامه بدهد، نه از صفر.
//
// فایل به تکه‌های کوچک شکسته می‌شود؛ هر تکه با retry مستقل آپلود می‌شود و روی
// سرور با cat به هم می‌چسبد. اگر یک تکه قطع شود، فقط همان تکه دوباره می‌رود.
// اولین تلاش با تکه‌ی ۱۵ مگابایتی هم روی همان الگو شکست: چهار تکه رفت، پنجمی
// سه‌بار پشت‌سرهم «Connection reset by peer» گرفت. این یک الگوی پایدار است،
// نه بدشانسی تصادفی — تکه‌های کوچک‌تر و مکث بین تلاش‌ها فرصت می‌دهد اگر throttle
// یا قطعی موقتی شبکه است، خودش را نشان بدهد.
const CHUNK_MB = 10
const MAX_RETRIES = 5
const RETRY_DELAY_MS = 3000

// timeout.exe ویندوز با stdin غیرترمینال («redirected») صراحتاً رد می‌شود، پس
// sleep پوسته‌ای قابل اتکا نیست. اسپون کردن خودِ node برای یک setTimeout ساده
// روی هر پلتفرمی کار می‌کند چون node همین الان هم در حال اجراست.
function sleepSync(ms) {
  execFileSync(process.execPath, ['-e', `setTimeout(()=>{}, ${ms})`], { stdio: 'ignore' })
}

function scpWithRetry(local, remotePath) {
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      scpOnce(local, remotePath)
      return
    } catch (err) {
      if (attempt === MAX_RETRIES) throw err
      console.log(`  اتصال قطع شد (تلاش ${attempt}/${MAX_RETRIES}) — ${RETRY_DELAY_MS / 1000} ثانیه صبر و دوباره: ${path.basename(local)}`)
      sleepSync(RETRY_DELAY_MS)
    }
  }
}

function scpLargeFile(local, remoteName) {
  const remotePath = `${REMOTE}/${remoteName}`
  const size = statSync(local).size
  if (size < CHUNK_MB * 1024 * 1024 * 2) {
    scpWithRetry(local, remotePath)
    return
  }

  const chunkDir = mkdtempSync(path.join(tmpdir(), 'cubita-chunks-'))
  try {
    execFileSync('split', ['-b', `${CHUNK_MB}m`, '-d', '-a', '3', local, path.join(chunkDir, 'part_')])
    const parts = readdirSync(chunkDir).sort()
    console.log(`  ${parts.length} تکه‌ی ${CHUNK_MB} مگابایتی`)

    ssh(`mkdir -p ${REMOTE}/.chunks && rm -f ${REMOTE}/.chunks/*`)
    for (const [i, part] of parts.entries()) {
      process.stdout.write(`\r  آپلود تکه ${i + 1}/${parts.length}...`)
      scpWithRetry(path.join(chunkDir, part), `${REMOTE}/.chunks/${part}`)
    }
    console.log()

    ssh(`cd ${REMOTE}/.chunks && cat ${parts.join(' ')} > "${remotePath}" && rm -rf ${REMOTE}/.chunks`)

    // چسباندنِ تکه‌ها به ترتیب غلط، یا افتادن یک تکه، فایلی می‌سازد که اندازه‌اش
    // هم می‌تواند تصادفاً نزدیک باشد و HTTP 200 هم بدهد — فقط sha256 دروغ را لو
    // می‌دهد. اینجا سنجیده می‌شود، نه بعداً که یک مشتری واقعی دانلودش کند و
    // electron-updater بی‌صدا ردش کند.
    const localHash = createHash('sha256').update(readFileSync(local)).digest('hex')
    const remoteHash = execFileSync(
      'ssh', [...SCP_OPTS, HOST, `sha256sum "${remotePath}" | cut -d' ' -f1`], { encoding: 'utf8' },
    ).trim()
    if (localHash !== remoteHash) {
      throw new Error(
        `sha256 بعد از چسباندنِ تکه‌ها مطابقت ندارد — فایل روی سرور خراب است.\n` +
        `  محلی:  ${localHash}\n  سرور:  ${remoteHash}`,
      )
    }
    console.log(`  sha256 تأیید شد: ${localHash.slice(0, 16)}…`)
  } finally {
    rmSync(chunkDir, { recursive: true, force: true })
  }
}

console.log(`انتشار نسخه ${version}`)

const master = startControlMaster()
try {
  // نصب‌کننده و blockmap اول. latest.yml آخر — تا هیچ کلاینتی نسخه‌ای را نبیند
  // که فایلش هنوز نرسیده.
  console.log(`  آپلود ${installer} …`)
  scpLargeFile(path.join(RELEASE, installer), installer)

  console.log(`  آپلود ${installer}.blockmap …`)
  scpWithRetry(path.join(RELEASE, `${installer}.blockmap`), `${REMOTE}/${installer}.blockmap`)

  console.log('  آپلود latest.yml …')
  scpWithRetry(path.join(RELEASE, 'latest.yml'), `${REMOTE}/latest.yml`)

  ssh(`chown -R hesabdari:hesabdari ${REMOTE} && ls -la ${REMOTE}`)
} finally {
  stopControlMaster()
  if (!master.killed) master.kill()
}

// راستی‌آزمایی از بیرون: نامی که در latest.yml نوشته شده باید واقعاً قابل دانلود
// باشد. بدون این، انتشارِ شکسته «موفق» گزارش می‌شود و فقط وقتی کشف می‌شود که
// اپ یک مشتری به‌روزرسانی را نصفه رها کند.
//
// با ماژول https خودِ node، نه با اسپون کردن curl: کدام curl از PATH resolve
// می‌شود قابل پیش‌بینی نیست — روی این ماشین curl.exe بومی ویندوز `/dev/null` را
// نمی‌فهمد و با کد ۲۳ (خطای نوشتن) شکست می‌خورد، در حالی که خودِ درخواست HTTP
// (که این تابع واقعاً باید بسنجد) کامل و با ۲۰۰ موفق بود.
function headStatus(url) {
  return new Promise((resolve, reject) => {
    const req = httpsRequest(url, { method: 'HEAD' }, (res) => {
      res.resume()
      resolve(res.statusCode)
    })
    req.on('error', reject)
    req.end()
  })
}

const base = 'https://acc.cubita.ir/updates'
const [ymlCode, exeCode] = await Promise.all([
  headStatus(`${base}/latest.yml`),
  headStatus(`${base}/${installer}`),
])
console.log(`\nراستی‌آزمایی:  latest.yml → ${ymlCode}   نصب‌کننده → ${exeCode}`)
if (ymlCode !== 200 || exeCode !== 200) {
  console.error('انتشار ناقص است: فایل‌ها از بیرون در دسترس نیستند.')
  process.exit(1)
}

console.log(`\nمنتشر شد: https://acc.cubita.ir/updates/latest.yml`)
