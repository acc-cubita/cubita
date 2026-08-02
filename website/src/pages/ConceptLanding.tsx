import { Suspense, lazy, useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import {
  BarChart3,
  ReceiptText,
  Calculator,
  CreditCard,
  Landmark,
  BookOpen,
  Sparkles,
  ArrowLeft,
  ShieldCheck,
  Zap,
  Layers,
} from 'lucide-react'
import '../concept/concept.css'

const HeroScene = lazy(() => import('../concept/HeroScene'))

const TRIAL_URL = 'https://demo.cubita.ir'

const FEATURES = [
  { icon: ReceiptText, title: 'فروش و فاکتور', desc: 'صدور فاکتور، پیش‌فاکتور و رسید در چند ثانیه — با ثبتِ خودکارِ سند حسابداری.' },
  { icon: BarChart3, title: 'گزارش‌های زنده', desc: 'ترازنامه، سود و زیان و دفتر کل، همیشه به‌روز و مستقیم از دل دفاتر.' },
  { icon: Calculator, title: 'حسابداری دوطرفه', desc: 'دفتر کل، سند دستی و خودکار، و بستنِ دوره — دقیق و استاندارد.' },
  { icon: CreditCard, title: 'صندوق و پرداخت', desc: 'صندوق فروشگاهی، کارت‌خوان و مدیریتِ دریافت و پرداختِ روزانه.' },
  { icon: Landmark, title: 'چک و بانک', desc: 'دفترِ چک، مغایرت‌گیریِ بانکی و سررسیدها — بدونِ دفترچه و اکسل.' },
  { icon: BookOpen, title: 'انبار و دفتر کل', desc: 'کاردکس، قیمت تمام‌شده و موجودیِ لحظه‌ای، گره‌خورده با حسابداری.' },
]

const WHY = [
  { icon: Zap, title: 'راه‌اندازیِ چنددقیقه‌ای', desc: 'ثبت‌نام کن و همان لحظه شروع کن؛ بدونِ نصب، بدونِ کارتِ بانکی.' },
  { icon: Layers, title: 'دسکتاپ و آنلاین', desc: 'یک حساب، هم روی مرورگر هم اپِ آفلاینِ دسکتاپ — همیشه هم‌گام.' },
  { icon: ShieldCheck, title: 'داده‌ی ایزوله و امن', desc: 'اطلاعاتِ هر کسب‌وکار در سطحِ پایگاه‌داده جدا و محافظت‌شده است.' },
]

function Hero() {
  return (
    <section className="cc-hero">
      <div className="cc-hero-canvas">
        <Suspense fallback={<div className="cc-hero-canvas-fallback" />}>
          <HeroScene />
        </Suspense>
      </div>
      <div className="cc-hero-scrim" aria-hidden="true" />
      <motion.div
        className="cc-hero-content"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      >
        <span className="cc-eyebrow">
          <Sparkles size={15} /> نسلِ تازه‌ی حسابداریِ ابری
        </span>
        <h1 className="cc-hero-title">
          حسابداریِ کسب‌وکارت،
          <br />
          <span className="cc-grad">سه‌بعدی و زنده</span>
        </h1>
        <p className="cc-hero-sub">
          فروش، انبار، حسابداری، چک و بانک و صندوق — همه در یک سامانه‌ی یکپارچه‌ی فارسی.
          بچرخانش، اسکرول کن، و ببین چطور همه‌چیز کنارِ هم کار می‌کند.
        </p>
        <div className="cc-hero-cta">
          <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
            <Sparkles size={17} /> شروعِ ۱۴ روز رایگان
          </a>
          <a className="cc-btn cc-btn-ghost" href="#cc-features">
            امکانات را ببین <ArrowLeft size={16} />
          </a>
        </div>
      </motion.div>
      <div className="cc-scroll-hint" aria-hidden="true">
        <span />
      </div>
    </section>
  )
}

function Features() {
  return (
    <section className="cc-section" id="cc-features">
      <motion.div
        className="cc-section-head"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
      >
        <span className="cc-eyebrow cc-eyebrow-center">همه‌چیز، یک‌جا</span>
        <h2>یک سامانه برای کلِ دفترِ کسب‌وکار</h2>
        <p>هر ماژول به‌جای جزیره‌ی جدا، بخشی از یک کلِ به‌هم‌پیوسته است.</p>
      </motion.div>

      <div className="cc-grid">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            className="cc-card"
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5, delay: (i % 3) * 0.08 }}
          >
            <div className="cc-card-icon">
              <f.icon size={26} />
            </div>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

function WhySection() {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] })
  const y = useTransform(scrollYProgress, [0, 1], [60, -60])

  return (
    <section className="cc-section cc-why" ref={ref}>
      <motion.div className="cc-why-glow" style={{ y }} aria-hidden="true" />
      <motion.div
        className="cc-section-head"
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
      >
        <span className="cc-eyebrow cc-eyebrow-center">چرا کوبیتا</span>
        <h2>ساخته‌شده برای کسب‌وکارهای ایرانی</h2>
      </motion.div>

      <div className="cc-why-grid">
        {WHY.map((w, i) => (
          <motion.div
            key={w.title}
            className="cc-why-item"
            initial={{ opacity: 0, y: 36 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            <div className="cc-why-icon">
              <w.icon size={24} />
            </div>
            <div>
              <h3>{w.title}</h3>
              <p>{w.desc}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.div
        className="cc-final-cta"
        initial={{ opacity: 0, scale: 0.96 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.6 }}
      >
        <h2>همین امروز، رایگان شروع کن</h2>
        <p>۱۴ روز کاملِ رایگان — بدونِ کارتِ بانکی. اگر پسندیدی، اطلاعاتت حفظ می‌شود.</p>
        <a className="cc-btn cc-btn-primary cc-btn-lg" href={TRIAL_URL}>
          <Sparkles size={18} /> شروعِ ۱۴ روز رایگان
        </a>
      </motion.div>
    </section>
  )
}

export function ConceptLanding() {
  return (
    <div className="cc-root" dir="rtl">
      <Hero />
      <Features />
      <WhySection />
      <footer className="cc-footer">
        <span>کوبیتا — نمونه‌ی طراحیِ کانسپت</span>
      </footer>
    </div>
  )
}
