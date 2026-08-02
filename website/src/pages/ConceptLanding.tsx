import { useEffect, useRef, useState } from 'react'
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
  Menu,
  X,
  Globe,
  MonitorSmartphone,
  Store,
  Shirt,
  Smartphone,
  Truck,
  Sofa,
  Gem,
  Coffee,
  Wrench,
  ShoppingCart,
  MousePointerClick,
  Settings2,
  Rocket,
  ChevronDown,
  DatabaseZap,
  Wallet,
  Users,
} from 'lucide-react'
import HeroVisual from '../concept/HeroVisual'
import { ConceptPricing } from '../concept/ConceptPricing'
import '../concept/concept.css'

const TRIAL_URL = 'https://demo.cubita.ir'
const APP_URL = 'https://acc.cubita.ir'

const NAV = [
  { href: '#cc-features', label: 'امکانات' },
  { href: '#cc-industries', label: 'صنایع' },
  { href: '#cc-pricing', label: 'پلن‌ها' },
  { href: '#cc-faq', label: 'سوالات' },
]

const STATS = [
  { icon: DatabaseZap, value: 'ایزوله', label: 'داده‌ی هر کسب‌وکار در دیتابیسِ جدا' },
  { icon: MonitorSmartphone, value: 'وب + دسکتاپ', label: 'یک حساب، دو نسخه‌ی هم‌گام' },
  { icon: Wallet, value: 'زرین‌پال', label: 'پرداختِ امن و آنی' },
  { icon: Users, value: 'چندکاربره', label: 'نقش‌های مدیر، حسابدار، فروشنده…' },
]

const PLATFORMS = [
  {
    icon: Globe,
    title: 'نسخه‌ی وب',
    desc: 'بدونِ نصب، از هر مرورگری وارد شو و کار کن — همه‌چیز روی ابر و همیشه به‌روز.',
    points: ['بدونِ نصب و نگهداری', 'دسترسی از هر دستگاه', 'پشتیبان‌گیریِ خودکار'],
  },
  {
    icon: MonitorSmartphone,
    title: 'اپِ دسکتاپِ آفلاین',
    desc: 'اینترنت قطع شد؟ اپِ دسکتاپ آفلاین کار می‌کند و با اتصالِ مجدد خودکار هم‌گام می‌شود.',
    points: ['کارِ کاملاً آفلاین', 'هم‌گام‌سازیِ خودکار', 'سرعتِ بالای محلی'],
  },
]

const INDUSTRIES = [
  { icon: Store, label: 'فروشگاه و سوپرمارکت' },
  { icon: Shirt, label: 'پوشاک و بوتیک' },
  { icon: Smartphone, label: 'موبایل و دیجیتال' },
  { icon: Truck, label: 'پخش و بنکداری' },
  { icon: Sofa, label: 'لوازم خانگی و دکور' },
  { icon: Gem, label: 'طلا و جواهر' },
  { icon: Coffee, label: 'کافه و رستوران' },
  { icon: Wrench, label: 'خدمات و پیمانکاری' },
  { icon: ShoppingCart, label: 'فروشگاه اینترنتی' },
]

const FEATURES = [
  { icon: ReceiptText, title: 'فروش و فاکتور', desc: 'صدور فاکتور، پیش‌فاکتور و رسید در چند ثانیه — با ثبتِ خودکارِ سند حسابداری.' },
  { icon: BarChart3, title: 'گزارش‌های زنده', desc: 'ترازنامه، سود و زیان و دفتر کل، همیشه به‌روز و مستقیم از دل دفاتر.' },
  { icon: Calculator, title: 'حسابداری دوطرفه', desc: 'دفتر کل، سند دستی و خودکار، و بستنِ دوره — دقیق و استاندارد.' },
  { icon: CreditCard, title: 'صندوق و پرداخت', desc: 'صندوق فروشگاهی، کارت‌خوان و مدیریتِ دریافت و پرداختِ روزانه.' },
  { icon: Landmark, title: 'چک و بانک', desc: 'دفترِ چک، مغایرت‌گیریِ بانکی و سررسیدها — بدونِ دفترچه و اکسل.' },
  { icon: BookOpen, title: 'انبار و کاردکس', desc: 'کاردکس، قیمت تمام‌شده و موجودیِ لحظه‌ای، گره‌خورده با حسابداری.' },
]

const STEPS = [
  { icon: MousePointerClick, title: 'پلن مناسب را انتخاب کن', desc: 'بر اساس تعداد کاربران و نیازت، یکی از پلن‌های پایه، حرفه‌ای یا سازمانی را بردار.' },
  { icon: CreditCard, title: 'پرداختِ امن با زرین‌پال', desc: 'مبلغِ پلن را از درگاهِ معتبرِ زرین‌پال پرداخت کن — کاملاً امن و آنی.' },
  { icon: Settings2, title: 'نسخه‌ات همان لحظه ساخته می‌شود', desc: 'بعد از تأییدِ پرداخت، نسخه‌ی اختصاصی و ایزوله‌ات ساخته و لینکِ رمز به ایمیلت می‌رسد.' },
  { icon: Rocket, title: 'شروع به کار', desc: 'رمزت را تعیین کن، وارد اپِ دسکتاپ یا وب شو و اولین فاکتور را ثبت کن.' },
]

const WHY = [
  { icon: Zap, title: 'راه‌اندازیِ چنددقیقه‌ای', desc: 'ثبت‌نام کن و همان لحظه شروع کن؛ بدونِ نصب، بدونِ کارتِ بانکی.' },
  { icon: Layers, title: 'دسکتاپ و آنلاین', desc: 'یک حساب، هم روی مرورگر هم اپِ آفلاینِ دسکتاپ — همیشه هم‌گام.' },
  { icon: ShieldCheck, title: 'داده‌ی ایزوله و امن', desc: 'اطلاعاتِ هر کسب‌وکار در سطحِ پایگاه‌داده جدا و محافظت‌شده است.' },
]

const FAQS = [
  { q: 'آیا داده‌های کسب‌وکار من امن است؟', a: 'بله. هر مشتری روی یک نسخه‌ی کاملاً ایزوله (دیتابیس، سرویس و آدرس اختصاصی) اجرا می‌شود؛ داده‌ی هیچ کسب‌وکاری با دیگری در یک دیتابیس مشترک نیست. اتصال هم همیشه از طریق HTTPS رمزنگاری‌شده است.' },
  { q: 'نسخه‌ی آزمایشیِ رایگان چطور کار می‌کند؟', a: 'ثبت‌نام می‌کنی و ۱۴ روز کاملِ رایگان — بدونِ کارتِ بانکی — همه‌ی امکاناتِ اصلی را داری. اگر پیش از پایان پلن بخری، همه‌ی اطلاعاتت حفظ می‌شود.' },
  { q: 'اگر اینترنت قطع شود چه اتفاقی می‌افتد؟', a: 'نسخه‌ی دسکتاپ کاملاً آفلاین کار می‌کند: فاکتور، سند حسابداری و بقیه‌ی عملیات محلی ذخیره می‌شوند و با اتصالِ مجدد، خودکار با سرور مرکزی هم‌گام می‌شوند.' },
  { q: 'چند نفر می‌توانند هم‌زمان استفاده کنند؟', a: 'بسته به پلن، از یک تا چند کاربرِ هم‌زمان — هرکدام با نقشِ مشخص (مدیر، حسابدار، فروشنده، انباردار، مسئول حقوق) و دسترسیِ محدود به همان بخش.' },
  { q: 'بعد از پرداخت، چقدر طول می‌کشد؟', a: 'بلافاصله. بعد از پرداختِ موفق، نسخه‌ی اختصاصی و ایزوله‌ات همان لحظه ساخته می‌شود و لینکِ تعیینِ رمز عبور به ایمیلت می‌رسد.' },
  { q: 'امکانِ اتصال به سامانه‌ی مؤدیان هست؟', a: 'بله، در پلنِ سازمانی. صورتحساب‌های الکترونیکی مطابق با الزاماتِ سازمانِ امور مالیاتی ارسال می‌شوند.' },
]

function BrandMark({ id = 'm' }: { id?: string }) {
  const g = `cc-brandgrad-${id}`
  return (
    <svg className="cc-brand-svg" width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill={`url(#${g})`} />
      <rect x="7.5" y="17" width="4" height="7.5" rx="2" fill="#fff" fillOpacity="0.82" />
      <rect x="14" y="13" width="4" height="11.5" rx="2" fill="#fff" fillOpacity="0.92" />
      <rect x="20.5" y="9.5" width="4" height="15" rx="2" fill="#fff" />
      <circle cx="22.5" cy="6.4" r="2.6" fill="#f5c542" />
      <defs>
        <linearGradient id={g} x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#5b86ff" />
          <stop offset="1" stopColor="#2ad4e6" />
        </linearGradient>
      </defs>
    </svg>
  )
}

function Header() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className={`cc-header${scrolled ? ' cc-header-solid' : ''}`}>
      <div className="cc-header-in">
        <a href="#" className="cc-brand">
          <BrandMark id="hdr" /> کوبیتا
        </a>
        <nav className="cc-nav" aria-label="منوی اصلی">
          {NAV.map((l) => (
            <a href={l.href} key={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
        <div className="cc-header-actions">
          <a href={APP_URL} target="_blank" rel="noreferrer" className="cc-btn cc-btn-ghost cc-btn-sm">
            ورود به برنامه
          </a>
          <a href={TRIAL_URL} className="cc-btn cc-btn-primary cc-btn-sm">
            ۱۴ روز رایگان
          </a>
        </div>
        <button
          type="button"
          className="cc-nav-toggle"
          aria-label={open ? 'بستن منو' : 'باز کردن منو'}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      {open && (
        <nav className="cc-nav-mobile" aria-label="منوی موبایل" onClick={() => setOpen(false)}>
          {NAV.map((l) => (
            <a href={l.href} key={l.href}>
              {l.label}
            </a>
          ))}
          <a href={APP_URL} target="_blank" rel="noreferrer" className="cc-btn cc-btn-ghost">
            ورود به برنامه
          </a>
          <a href={TRIAL_URL} className="cc-btn cc-btn-primary">
            شروعِ ۱۴ روز رایگان
          </a>
        </nav>
      )}
    </header>
  )
}

function Hero() {
  return (
    <section className="cc-hero">
      <div className="cc-hero-canvas">
        <HeroVisual />
      </div>
      <div className="cc-hero-scrim" aria-hidden="true" />
      <motion.div
        className="cc-hero-content"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      >
        <span className="cc-eyebrow">
          <Sparkles size={15} /> حسابداریِ ابری و آفلاین، مخصوصِ ایران
        </span>
        <h1 className="cc-hero-title">
          کلِ حساب‌وکتابِ کسب‌وکارت،
          <br />
          <span className="cc-grad">یک‌جا و ساده</span>
        </h1>
        <p className="cc-hero-sub">
          فروش و فاکتور، انبار، حسابداریِ دوطرفه، چک و بانک و صندوق — همه در یک نرم‌افزارِ فارسی
          که هم روی مرورگر و هم آفلاین روی دسکتاپ کار می‌کند.
        </p>
        <div className="cc-hero-cta">
          <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
            <Sparkles size={17} /> شروعِ ۱۴ روز رایگان
          </a>
          <a className="cc-btn cc-btn-ghost" href="#cc-features">
            امکانات را ببین <ArrowLeft size={16} />
          </a>
        </div>
        <div className="cc-hero-trust">بدونِ کارتِ بانکی · راه‌اندازیِ چنددقیقه‌ای · وب و دسکتاپ</div>
      </motion.div>
      <div className="cc-scroll-hint" aria-hidden="true">
        <span />
      </div>
    </section>
  )
}

function StatsStrip() {
  return (
    <div className="cc-stats">
      <div className="cc-stats-in">
        {STATS.map((s) => (
          <div className="cc-stat" key={s.value}>
            <span className="cc-stat-ico">
              <s.icon size={20} />
            </span>
            <div>
              <b>{s.value}</b>
              <span>{s.label}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SectionHead({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <motion.div
      className="cc-section-head"
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.6 }}
    >
      <span className="cc-eyebrow cc-eyebrow-center">{eyebrow}</span>
      <h2>{title}</h2>
      {sub && <p>{sub}</p>}
    </motion.div>
  )
}

function Platforms() {
  return (
    <section className="cc-section" id="cc-platforms">
      <SectionHead eyebrow="همه‌جا در دسترس" title="یک حساب، روی وب و دسکتاپ" sub="هرجا راحت‌تری کار کن؛ داده‌ات همیشه بینِ هر دو نسخه هم‌گام است." />
      <div className="cc-platforms">
        {PLATFORMS.map((p, i) => (
          <motion.div
            key={p.title}
            className="cc-platform"
            initial={{ opacity: 0, y: 36 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
          >
            <span className="cc-platform-ico">
              <p.icon size={26} />
            </span>
            <h3>{p.title}</h3>
            <p>{p.desc}</p>
            <ul className="cc-platform-points">
              {p.points.map((pt) => (
                <li key={pt}>{pt}</li>
              ))}
            </ul>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

function Industries() {
  return (
    <section className="cc-section" id="cc-industries">
      <SectionHead eyebrow="مناسبِ کسب‌وکارِ تو" title="از یک مغازه تا یک شرکتِ پخش" sub="کوبیتا با نیازِ کسب‌وکارهای مختلف جور می‌شود؛ رشته‌ی کارت را پیدا کن." />
      <div className="cc-ind-grid">
        {INDUSTRIES.map((it, i) => (
          <motion.div
            key={it.label}
            className="cc-ind"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-40px' }}
            transition={{ duration: 0.4, delay: (i % 3) * 0.06 }}
          >
            <span className="cc-ind-ico">
              <it.icon size={19} />
            </span>
            <span>{it.label}</span>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

function Features() {
  return (
    <section className="cc-section" id="cc-features">
      <SectionHead eyebrow="همه‌چیز، یک‌جا" title="همه‌ی ابزارِ حسابداری، در یک نرم‌افزار" sub="از فروش و انبار تا چک و بانک و گزارش‌ها — هر بخش با بخش‌های دیگر یکپارچه است و سند خودش را خودکار می‌زند." />
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

function HowItWorks() {
  return (
    <section className="cc-section" id="cc-how">
      <SectionHead eyebrow="شروعِ کار" title="در چهار قدمِ ساده شروع کن" sub="از انتخابِ پلن تا ثبتِ اولین فاکتور، چند دقیقه بیشتر طول نمی‌کشد." />
      <div className="cc-steps">
        {STEPS.map((s, i) => (
          <motion.div
            key={s.title}
            className="cc-step"
            initial={{ opacity: 0, y: 36 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
          >
            <span className="cc-step-no">{String(i + 1).padStart(2, '0')}</span>
            <span className="cc-step-ico">
              <s.icon size={20} />
            </span>
            <h3>{s.title}</h3>
            <p>{s.desc}</p>
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
      <SectionHead eyebrow="چرا کوبیتا" title="ساخته‌شده برای کسب‌وکارهای ایرانی" sub="فارسی، ابری و آفلاین، با پشتیبانی و قیمتِ داخلی — بی‌دردسر و بدونِ پیچیدگیِ نرم‌افزارهای بزرگ." />
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
    </section>
  )
}

function FaqSection() {
  const [open, setOpen] = useState<number | null>(0)
  return (
    <section className="cc-section cc-faq-sec" id="cc-faq">
      <SectionHead eyebrow="سوالاتِ متداول" title="هرچه لازم است بدانی" />
      <div className="cc-faq-list">
        {FAQS.map((item, idx) => {
          const isOpen = open === idx
          return (
            <div className={`cc-faq${isOpen ? ' cc-faq-open' : ''}`} key={item.q}>
              <button
                type="button"
                className="cc-faq-q"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : idx)}
              >
                {item.q}
                <ChevronDown size={18} className="cc-faq-chev" />
              </button>
              {isOpen && <p className="cc-faq-a">{item.a}</p>}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function FinalCta() {
  return (
    <section className="cc-section">
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

function Footer() {
  return (
    <footer className="cc-site-footer">
      <div className="cc-footer-grid">
        <div className="cc-footer-brand">
          <a href="#" className="cc-brand">
            <BrandMark id="ftr" /> کوبیتا
          </a>
          <p>نرم‌افزارِ حسابداریِ ابری و آفلاین برای کسب‌وکارهای ایرانی.</p>
          <a
            className="cc-enamad"
            referrerPolicy="origin"
            target="_blank"
            rel="noopener"
            href="https://trustseal.enamad.ir/?id=623640&Code=tfCgeyzE0htaTRGDcOopEIvMsEIdYuOR"
          >
            <img
              referrerPolicy="origin"
              src="https://trustseal.enamad.ir/logo.aspx?id=623640&Code=tfCgeyzE0htaTRGDcOopEIvMsEIdYuOR"
              alt="نماد اعتماد الکترونیکی"
              {...({ code: 'tfCgeyzE0htaTRGDcOopEIvMsEIdYuOR' } as Record<string, string>)}
            />
          </a>
        </div>
        <div className="cc-footer-col">
          <h4>محصول</h4>
          <a href="#cc-features">امکانات</a>
          <a href="#cc-how">شروعِ کار</a>
          <a href="#cc-pricing">پلن‌ها و قیمت‌ها</a>
          <a href={TRIAL_URL}>دموی رایگان</a>
        </div>
        <div className="cc-footer-col">
          <h4>پشتیبانی</h4>
          <a href="#cc-faq">سوالاتِ متداول</a>
          <a href="mailto:ipnetcity@gmail.com">ipnetcity@gmail.com</a>
        </div>
        <div className="cc-footer-col">
          <h4>قانونی</h4>
          <a href="/terms">شرایطِ استفاده از خدمات</a>
          <a href="/privacy">حریمِ خصوصی</a>
        </div>
      </div>
      <div className="cc-footer-bottom">
        © {new Intl.DateTimeFormat('fa-IR', { year: 'numeric' }).format(new Date())} کوبیتا — تمامِ حقوق محفوظ است.
      </div>
    </footer>
  )
}

export function ConceptLanding() {
  return (
    <div className="cc-root" dir="rtl">
      <Header />
      <Hero />
      <StatsStrip />
      <Platforms />
      <Industries />
      <Features />
      <HowItWorks />
      <ConceptPricing />
      <WhySection />
      <FaqSection />
      <FinalCta />
      <Footer />
    </div>
  )
}
