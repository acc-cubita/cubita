/**
 * نُه نمونه‌ی طلاییِ پروتکلِ PNA — گرفته از خروجیِ ابزارِ رسمیِ خودِ PNA.
 *
 * اجرا:  node scripts/verify-pna.mjs
 *
 * **چرا این فایل هست.** قالبِ پیامِ کارتخوان از مستندات نیامده؛ از مشاهده‌ی
 * خروجیِ `PCPOS Tester` با ورودی‌های مختلف استخراج شد. یعنی تنها چیزی که
 * درستی‌اش را تضمین می‌کند، همین نمونه‌هاست. اگر `pna.ts` عوض شود و این‌ها
 * نخوانند، پیامی ساخته می‌شود که **به یک دستگاهِ بانکی می‌رود** — جایی که
 * اشتباه گران است.
 *
 * هر ردیف: ورودی‌هایی که در فرمِ ابزار گذاشته شد، و رشته‌ای که ساخت.
 */
import { buildPnaMessage } from '../electron/pos/pna.ts'

const CASES = [
  ['مبلغ ۱',
   { amount: '1' },
   '@@PNA@@0110001100000200000000011'],

  ['مبلغ ۱۰ — طولِ فیلد با مقدار بزرگ می‌شود',
   { amount: '10' },
   '@@PNA@@01100021000000200000000011'],

  ['مبلغ ۱۰۰۰۰۰',
   { amount: '100000' },
   '@@PNA@@011000610000000000200000000011'],

  ['شماره قبض ۵۵ — فیلدِ پیش از مبلغ هم طول‌دار است',
   { billNumber: '55', amount: '1221' },
   '@@PNA@@011025504122100000200000000011'],

  ['نوع تراکنش: قبض',
   { billNumber: '55', amount: '1221', txKind: 'bill' },
   '@@PNA@@011025504122100000201000000011'],

  ['رسید: فقط مشتری',
   { billNumber: '55', amount: '1221', txKind: 'bill', receipt: 'customer' },
   '@@PNA@@011025504122100000201000000012'],

  ['ECR نوعِ ۲',
   { ecrType: 2, billNumber: '55', amount: '1221', txKind: 'bill', receipt: 'customer' },
   '@@PNA@@012025504122100000201000000012'],

  ['مهلتِ کشیدن کارت ۳۰ ثانیه',
   { ecrType: 2, billNumber: '55', amount: '1221', txKind: 'bill', swipeCardTimeout: '30', receipt: 'customer' },
   '@@PNA@@01202550412210000020100000230012'],

  ['داده‌ی اضافیِ غیرعددی — تنها نمونه‌ای که ثابت می‌کند مقدار خامِ متن است',
   { ecrType: 2, billNumber: '55', amount: '1221', txKind: 'bill', additionalData: 'ab', swipeCardTimeout: '30', receipt: 'customer' },
   '@@PNA@@01202550412210000020102ab000230012'],
]

let failed = 0
for (const [name, input, expected] of CASES) {
  let got
  try {
    got = buildPnaMessage(input)
  } catch (err) {
    got = `*** خطا: ${err.message} ***`
  }
  const ok = got === expected
  if (!ok) failed++
  console.log(`${ok ? '  OK  ' : '  XX  '}${name}`)
  if (!ok) {
    console.log(`        انتظار: ${expected}`)
    console.log(`        ساخته : ${got}`)
    for (let i = 0; i <= Math.max(got.length, expected.length); i++) {
      if (got[i] !== expected[i]) {
        console.log(`        ${' '.repeat(16 + i)}^ اولین اختلاف، نویسه‌ی ${i}`)
        break
      }
    }
  }
}

//: مبلغِ بدشکل نباید بی‌صدا رد شود — سرِ صندوق فهمیدنش خیلی گران‌تر است.
for (const bad of ['1,000', '1000.00', '', 'abc', '۱۲۳']) {
  let threw = false
  try { buildPnaMessage({ amount: bad }) } catch { threw = true }
  if (!threw) { failed++; console.log(`  XX  مبلغِ نامعتبر «${bad}» پذیرفته شد`) }
  else console.log(`  OK  مبلغِ نامعتبر «${bad}» رد شد`)
}

console.log(failed ? `\n*** ${failed} مورد نخواند ***` : '\nهمه‌ی نمونه‌ها بایت‌به‌بایت خواندند')
process.exit(failed ? 1 : 0)
