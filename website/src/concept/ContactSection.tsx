import { useEffect, useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, Mail, PhoneCall, Send } from 'lucide-react'
import { submitSalesInquiry, type SalesProduct } from '../api'

/**
 * «خرید و مشاوره» — جای پلن‌های قیمت‌دار (۱۴۰۵/۰۷/۰۳). فروشِ هر چهار محصولِ کوبیتا از راهِ گفت‌وگو با
 * کارشناس است: این فرم درخواست را به صفِ فروشِ `admin.cubita.ir` می‌فرستد و کارشناس تماس می‌گیرد.
 *
 * دکمه‌ی «درخواست مجوز»ِ کارتِ کوبیتا سازمانی فرم را با همان محصول باز می‌کند (`openContact`) — بی‌بارِ
 * دوباره‌ی صفحه، چون تغییرِ query روی همین صفحه کلِ سایت را دوباره بار می‌کرد.
 */

export const PRODUCTS: { value: SalesProduct; label: string }[] = [
  { value: 'cloud', label: 'کوبیتا ابری (وب)' },
  { value: 'desktop', label: 'نسخه‌ی ویندوز' },
  { value: 'enterprise', label: 'کوبیتا سازمانی' },
  { value: 'mobile', label: 'اپ اندروید' },
  { value: 'unsure', label: 'هنوز نمی‌دانم' },
]

const EVENT = 'cc-contact-product'

/** رفتن به فرم با محصولِ از پیش انتخاب‌شده. */
export function openContact(product: SalesProduct) {
  window.dispatchEvent(new CustomEvent<SalesProduct>(EVENT, { detail: product }))
  document.getElementById('cc-contact')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const reveal = {
  initial: { opacity: 0, y: 14 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.45, ease: 'easeOut' },
} as const

const EMPTY = { name: '', company: '', phone: '', email: '', seats: '', message: '', website: '' }

export function ContactSection() {
  const [form, setForm] = useState(EMPTY)
  const [product, setProduct] = useState<SalesProduct>('cloud')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  useEffect(() => {
    const onPick = (e: Event) => {
      setProduct((e as CustomEvent<SalesProduct>).detail)
      setSent(false)
    }
    window.addEventListener(EVENT, onPick)
    return () => window.removeEventListener(EVENT, onPick)
  }, [])

  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!form.name.trim()) return setError('نامِ خود را بنویسید.')
    if (!form.phone.trim() && !form.email.trim()) return setError('شماره‌ی تماس یا ایمیل لازم است تا با شما تماس بگیریم.')
    const seats = Number(form.seats.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d))))
    setBusy(true)
    try {
      await submitSalesInquiry({
        name: form.name,
        company: form.company,
        phone: form.phone,
        email: form.email,
        product,
        seats: seats > 0 ? Math.trunc(seats) : null,
        message: form.message,
        website: form.website,
      })
      setSent(true)
      setForm(EMPTY)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'ارسال نشد؛ دوباره تلاش کنید.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="cc-section" id="cc-contact">
      <motion.div className="cc-section-head" {...reveal}>
        <span className="cc-eyebrow">خرید و مشاوره</span>
        <h2>برای خرید با ما در تماس باشید</h2>
        <p>
          بگویید کدام نسخه را می‌خواهید و چند نفر با آن کار می‌کنند؛ کارشناسِ فروش در ساعاتِ کاری با شما تماس می‌گیرد،
          نسخه‌ی مناسب را پیشنهاد می‌کند و قیمت را می‌گوید.
        </p>
      </motion.div>

      <motion.div className="cc-contact" {...reveal}>
        <aside className="cc-contact-side">
          <h3>چه چیزی را پیشنهاد می‌کنیم؟</h3>
          <ul className="cc-checklist">
            <li>
              <b>کوبیتا ابری</b> — برای کسب‌وکارهای کوچک و متوسط؛ روی وب، ویندوز و اندروید.
            </li>
            <li>
              <b>کوبیتا سازمانی</b> — برای شرکت‌ها و سازمان‌ها؛ سرور در خودِ شرکت و حسابدارها روی شبکه‌ی داخلی.
            </li>
          </ul>
          <p className="cc-contact-alt">
            <Mail size={16} /> یا ایمیل بزنید:{' '}
            <a href="mailto:acc.cubita@gmail.com" dir="ltr">
              acc.cubita@gmail.com
            </a>
          </p>
        </aside>

        {sent ? (
          <div className="cc-contact-done" role="status">
            <CheckCircle2 size={40} />
            <h3>درخواستتان رسید</h3>
            <p>کارشناسِ فروش به‌زودی با شما تماس می‌گیرد. اگر عجله دارید، همین حالا نسخه‌ی رایگان را امتحان کنید.</p>
            <button type="button" className="cc-btn cc-btn-outline" onClick={() => setSent(false)}>
              فرستادنِ درخواستِ دیگر
            </button>
          </div>
        ) : (
          <form className="cc-contact-form" noValidate onSubmit={(e) => void submit(e)}>
            <fieldset className="cc-contact-products">
              <legend>کدام نسخه؟</legend>
              {PRODUCTS.map((p) => (
                <label key={p.value} className={`cc-chip${product === p.value ? ' cc-chip-on' : ''}`}>
                  <input
                    type="radio"
                    name="product"
                    value={p.value}
                    checked={product === p.value}
                    onChange={() => setProduct(p.value)}
                  />
                  {p.label}
                </label>
              ))}
            </fieldset>
            <div className="cc-contact-grid">
              <label className="cc-field">
                <span>
                  نام و نام خانوادگی <i aria-hidden="true">*</i>
                </span>
                <input value={form.name} onChange={set('name')} autoComplete="name" required />
              </label>
              <label className="cc-field">
                <span>نامِ شرکت یا کسب‌وکار</span>
                <input value={form.company} onChange={set('company')} autoComplete="organization" />
              </label>
              <label className="cc-field">
                <span>شماره‌ی تماس</span>
                <input value={form.phone} onChange={set('phone')} inputMode="tel" autoComplete="tel" dir="ltr" />
              </label>
              <label className="cc-field">
                <span>ایمیل</span>
                <input value={form.email} onChange={set('email')} type="email" autoComplete="email" dir="ltr" />
              </label>
              <label className="cc-field">
                <span>تعدادِ کاربر</span>
                <input value={form.seats} onChange={set('seats')} inputMode="numeric" dir="ltr" />
              </label>
              <label className="cc-field cc-field-wide">
                <span>توضیح</span>
                <textarea rows={4} value={form.message} onChange={set('message')} placeholder="نیازتان را کوتاه بنویسید؛ مثلاً تعدادِ شعبه‌ها یا ارسال به سامانه‌ی مؤدیان." />
              </label>
              {/* تله‌ی ربات: از دیدِ آدم و صفحه‌خوان پنهان؛ ربات پرش می‌کند و درخواستش دور ریخته می‌شود. */}
              <label className="cc-hp" aria-hidden="true">
                وب‌سایت
                <input tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
              </label>
            </div>
            <p className="cc-contact-hint">شماره‌ی تماس یا ایمیل کافی است — یکی از دو تا را بنویسید.</p>
            {error && (
              <p className="cc-contact-error" role="alert">
                {error}
              </p>
            )}
            <button type="submit" className="cc-btn cc-btn-primary" disabled={busy}>
              {busy ? 'در حال ارسال…' : (
                <>
                  <Send size={16} /> ارسالِ درخواست
                </>
              )}
            </button>
            <p className="cc-contact-privacy">
              <PhoneCall size={14} /> اطلاعاتتان فقط برای تماسِ فروش استفاده می‌شود.
            </p>
          </form>
        )}
      </motion.div>
    </section>
  )
}
