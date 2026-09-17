/**
 * شبیه‌سازِ کارتخوانِ PNA — یک سرورِ TCP که مثلِ ترمینال گوش می‌دهد.
 *
 * اجرا:  node scripts/pna-simulator.mjs [پورت]
 *
 * **برای چه هست.** ترمینالِ واقعیِ ما هنوز از سمتِ PSP برای اتصال به صندوق فعال
 * نشده. این شبیه‌ساز اجازه می‌دهد کلِ مسیر — ساختِ پیام، ارسال روی TCP، دریافتِ
 * پاسخ، و آنچه رابط به کاربر نشان می‌دهد — بدونِ دستگاه آزموده شود.
 *
 * **و برای چه *نیست*.** پاسخی که این برمی‌گرداند **ساختگی** است. قالبِ واقعیِ
 * پاسخِ PNA هنوز دیده نشده، پس این شبیه‌ساز نمی‌تواند یادش بدهد. هر کدی که
 * «چون با شبیه‌ساز کار کرد پس درست است» فرض کند، اشتباه می‌کند — به همین دلیل
 * درایور هر پاسخی را `unknown` می‌گیرد تا وقتی یک تراکنشِ واقعی دیده شود.
 *
 * آنچه *واقعاً* می‌سنجد: پیامی که می‌رسد را با همان قاعده‌ی «طولِ دو رقمی +
 * مقدار» باز می‌کند و چاپ می‌کند. اگر رمزگذارِ ما خراب باشد، این‌جا به‌هم می‌ریزد.
 */
import net from 'node:net'

const PORT = Number(process.argv[2]) || 1362
const HEADER = '@@PNA@@'

const FIELD_NAMES = [
  'شماره قبض', 'مبلغ', 'شبا', 'نام مشتری', 'نوع تراکنش',
  'داده‌ی اضافی', 'مبلغ اصلی', 'مهلتِ کشیدن کارت', 'نوع رسید',
]

function decode(text) {
  if (!text.startsWith(HEADER)) return { error: 'سرآیندِ PNA ندارد' }
  const body = text.slice(HEADER.length)
  const prefix = body.slice(0, 2)
  const ecr = body.slice(2, 3)
  let i = 3
  const fields = []
  while (i + 2 <= body.length) {
    const len = Number(body.slice(i, i + 2))
    if (!Number.isInteger(len)) return { error: `طولِ نامعتبر در نویسه‌ی ${i}` }
    const value = body.slice(i + 2, i + 2 + len)
    if (value.length < len) return { error: `فیلدِ ناقص در نویسه‌ی ${i} (طول ${len}، موجود ${value.length})` }
    fields.push(value)
    i += 2 + len
  }
  const leftover = body.slice(i)
  return { prefix, ecr, fields, leftover }
}

const server = net.createServer((socket) => {
  const who = `${socket.remoteAddress}:${socket.remotePort}`
  console.log(`\n── اتصال از ${who} ──`)

  socket.on('data', (buf) => {
    const text = buf.toString('utf8').trim()
    console.log(`دریافت (${text.length} نویسه): ${text}`)

    const d = decode(text)
    if (d.error) {
      console.log(`  ✗ ${d.error}`)
      socket.write(`${HEADER}00`)
      return
    }
    console.log(`  پیشوند=${d.prefix}  ECR=${d.ecr}`)
    d.fields.forEach((v, n) => {
      const label = FIELD_NAMES[n] ?? `فیلدِ ${n + 1}`
      console.log(`  ${label.padEnd(20)} = ${v === '' ? '(خالی)' : v}`)
    })
    if (d.leftover) console.log(`  ⚠ ${d.leftover.length} نویسه‌ی بی‌تفسیر: ${d.leftover}`)
    if (d.fields.length !== FIELD_NAMES.length) {
      console.log(`  ⚠ ${d.fields.length} فیلد جدا شد، انتظار ${FIELD_NAMES.length}`)
    }

    //: پاسخِ **ساختگی**. قالبِ واقعی معلوم نیست؛ این فقط چیزی است که روی سیم
    //: برگردد تا مسیرِ دریافت آزموده شود.
    const fake = `${HEADER}SIMULATED-RESPONSE-NOT-REAL-FORMAT`
    console.log(`ارسالِ پاسخِ ساختگی: ${fake}`)
    socket.write(fake)
  })

  socket.on('error', (e) => console.log(`خطای سوکت: ${e.message}`))
  socket.on('close', () => console.log(`── ${who} بسته شد ──`))
})

server.listen(PORT, () => {
  console.log(`شبیه‌سازِ کارتخوانِ PNA روی پورتِ ${PORT} گوش می‌دهد.`)
  console.log('در کوبیتا: نوعِ اتصال «تحت شبکه» · آدرس 127.0.0.1 · همین پورت.')
  console.log('توجه: پاسخِ این شبیه‌ساز ساختگی است و قالبِ واقعیِ PNA نیست.\n')
})
