/**
 * پروتکلِ «پرداخت نوین آرین» (PNA) برای اتصالِ کارتخوان به صندوق.
 *
 * **این قالب حدس نیست.** از خروجیِ ابزارِ رسمیِ خودِ PNA (`PCPOS Tester`) استخراج
 * شد: نُه پیام با ورودی‌های مختلف ساخته شد و ساختار از تفاوتشان بیرون آمد.
 * `scripts/verify-pna.mjs` همان نُه نمونه را نگه می‌دارد و هر تغییری در این فایل
 * را در برابرشان می‌سنجد.
 *
 * ## شکلِ پیام
 *
 * ```
 * @@PNA@@ 01 E <LL+مقدار> × ۹
 * ```
 *
 * سرآیندِ ثابت، بعد `01`، بعد یک رقم برای نوعِ ECR، و بعد **نُه فیلد که هرکدام
 * یک طولِ دو رقمی دارند و پشتش مقدارش**. ترتیبشان همان ترتیبِ خواندنِ فرمِ ابزار
 * است: ستونِ چپ از بالا به پایین، بعد ستونِ راست.
 *
 * فیلدِ خالی یعنی `00` و هیچ مقداری — نه فاصله، نه صفرِ پرکننده. برای همین
 * طولِ پیام با ورودی عوض می‌شود و ثابت نیست.
 *
 * ## آنچه هنوز نمی‌دانیم: **قالبِ پاسخ**
 *
 * دستگاهِ آزمایشیِ ما هنوز از سمتِ PSP برای اتصال به صندوق فعال نشده، پس یک
 * پاسخِ واقعی دیده نشده است. `parseResponse` عمداً چیزی را که نمی‌فهمد
 * «تأییدشده» اعلام نمی‌کند — دلیلش در خودِ تابع نوشته شده.
 */

/** سرآیندی که هر پیام با آن شروع می‌شود. */
export const PNA_HEADER = '@@PNA@@'

/** نوعِ تراکنش، همان‌طور که در سیم می‌رود. */
export const PNA_TX = { sale: '00', bill: '01' } as const
export type PnaTxKind = keyof typeof PNA_TX

/** نسخه‌ی رسید: هم مشتری هم پذیرنده، یا فقط مشتری. */
export const PNA_RECEIPT = { both: '1', customer: '2' } as const
export type PnaReceiptKind = keyof typeof PNA_RECEIPT

export interface PnaRequest {
  /** نوعِ ECR که در تنظیماتِ دستگاه انتخاب شده — ۱ یا ۲. */
  ecrType?: 1 | 2
  billNumber?: string
  /** مبلغ به **ریال**، بدونِ جداکننده. */
  amount: string
  iban?: string
  customerName?: string
  txKind?: PnaTxKind
  additionalData?: string
  /** برای ابطال/برگشت لازم می‌شود؛ در فروشِ ساده خالی است. */
  originalAmount?: string
  /** ثانیه. خالی یعنی پیش‌فرضِ خودِ دستگاه. */
  swipeCardTimeout?: string
  receipt?: PnaReceiptKind
}

//: طول **دو رقمی** است، پس مقداری بلندتر از ۹۹ نویسه در این قالب بیان‌شدنی
//: نیست. به‌جای بریدنِ بی‌صدا — که پیامی می‌سازد که دستگاه یا رد می‌کند یا
//: بدتر، غلط می‌فهمد — صریح خطا می‌دهیم.
function lengthPrefixed(label: string, value: string): string {
  if (value.length > 99) {
    throw new Error(`«${label}» ${value.length} نویسه است؛ این پروتکل بیش از ۹۹ نویسه را بیان نمی‌کند.`)
  }
  return String(value.length).padStart(2, '0') + value
}

/**
 * پیامِ درخواست را می‌سازد — همان رشته‌ای که `PCPOS Tester` با همین ورودی‌ها
 * تولید می‌کند.
 */
export function buildPnaMessage(req: PnaRequest): string {
  const {
    ecrType = 1, billNumber = '', amount, iban = '', customerName = '',
    txKind = 'sale', additionalData = '', originalAmount = '',
    swipeCardTimeout = '', receipt = 'both',
  } = req

  //: مبلغ تنها فیلدِ اجباری است و باید رقمِ خالص باشد. `1,000` یا `1000.00` را
  //: دستگاه نمی‌فهمد و این‌جا گرفتنش ارزان‌تر از فهمیدنش سرِ صندوق است.
  if (!/^\d+$/.test(amount)) {
    throw new Error(`مبلغ باید فقط رقم باشد (ریال، بدونِ جداکننده) — دریافت شد: «${amount}»`)
  }

  return PNA_HEADER + '01' + String(ecrType)
    + lengthPrefixed('شماره قبض', billNumber)
    + lengthPrefixed('مبلغ', amount)
    + lengthPrefixed('شبا', iban)
    + lengthPrefixed('نام مشتری', customerName)
    + lengthPrefixed('نوع تراکنش', PNA_TX[txKind])
    + lengthPrefixed('داده‌ی اضافی', additionalData)
    + lengthPrefixed('مبلغ اصلی', originalAmount)
    + lengthPrefixed('مهلتِ کشیدن کارت', swipeCardTimeout)
    + lengthPrefixed('نوع رسید', PNA_RECEIPT[receipt])
}

export interface PnaParsedResponse {
  /** `true`/`false` تنها وقتی که پاسخ واقعاً فهمیده شده باشد. */
  outcome: 'approved' | 'declined' | 'unknown'
  message: string
  fields?: string[]
  raw: string
}

/**
 * پاسخِ دستگاه را می‌خوانَد — **و اگر نفهمید، وانمود نمی‌کند که فهمیده**.
 *
 * **چرا حالتِ سوم لازم است و `approved: false` کافی نیست.** اگر دستگاه کارت را
 * بکشد و پول را بگیرد ولی ما پاسخش را نفهمیم و «رد شد» گزارش کنیم، کاربر دوباره
 * می‌کشد و مشتری **دوبار** پول می‌دهد. آن از پشتیبانی‌نکردن بدتر است. پس پاسخِ
 * ناشناخته `unknown` است، و لایه‌ی بالاتر باید به کاربر بگوید رسیدِ دستگاه را
 * ببیند نه اینکه دوباره بزند.
 *
 * فیلدها با همان قاعده‌ی «طولِ دو رقمی + مقدار» جدا می‌شوند، چون سمتِ درخواست
 * همین است. ولی **معنای هر فیلد هنوز معلوم نیست** — تا وقتی یک تراکنشِ واقعی
 * دیده شود، چیزی به‌عنوانِ RRN یا وضعیت برداشت نمی‌شود.
 */
export function parsePnaResponse(raw: string): PnaParsedResponse {
  const text = raw.trim()
  if (!text) {
    return { outcome: 'unknown', message: 'دستگاه پاسخی نداد.', raw }
  }
  if (!text.startsWith(PNA_HEADER)) {
    return { outcome: 'unknown', message: 'پاسخ با سرآیندِ PNA شروع نمی‌شود.', raw }
  }

  const body = text.slice(PNA_HEADER.length)
  const fields: string[] = []
  let i = 0
  while (i + 2 <= body.length) {
    const len = Number(body.slice(i, i + 2))
    if (!Number.isInteger(len)) break
    const value = body.slice(i + 2, i + 2 + len)
    if (value.length < len) break //: پیامِ ناقص — بیش از این جدا نمی‌کنیم
    fields.push(value)
    i += 2 + len
  }

  return {
    outcome: 'unknown',
    message:
      'پاسخِ دستگاه دریافت شد ولی قالبش هنوز شناخته‌شده نیست. '
      + '**پیش از تکرارِ تراکنش، رسیدِ خودِ دستگاه را ببینید** — ممکن است پول کسر شده باشد.',
    fields,
    raw,
  }
}
