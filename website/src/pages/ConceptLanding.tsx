import { useState } from 'react'
import { MotionConfig, motion } from 'framer-motion'
import {
  BarChart3,
  ReceiptText,
  Calculator,
  CreditCard,
  Landmark,
  BookOpen,
  ArrowLeft,
  ShieldCheck,
  Zap,
  Layers,
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
  Users,
  Download,
  Check,
  Building2,
  MessagesSquare,
  PhoneCall,
} from 'lucide-react'
import { ContactSection, openContact } from '../concept/ContactSection'
import {
  ANDROID_APK_URL,
  APP_URL,
  DOWNLOAD_URL,
  ENTERPRISE_DOWNLOAD_URL,
  SiteFooter,
  SiteHeader,
  TRIAL_URL,
} from '../concept/SiteChrome'
import '../concept/concept.css'

//: چهار واقعیتِ پایه‌ای که کنارِ متنِ هیرو می‌نشینند — جایگزینِ خوشه‌ی کارت‌های شناور، به
//: خواستِ کاربر («سایت ساده، اداری و شیک باشد»).
const FACTS = [
  { icon: DatabaseZap, value: 'داده‌ی ایزوله', label: 'اطلاعاتِ هر کسب‌وکار در پایگاه‌داده‌ی جدا' },
  { icon: MonitorSmartphone, value: 'وب، ویندوز، اندروید', label: 'یک حساب، سه نسخه‌ی هم‌گام' },
  { icon: Building2, value: 'نسخه‌ی سازمانی', label: 'سرور در خودِ شرکت، حسابدارها روی شبکه‌ی داخلی' },
  { icon: Users, value: 'چندکاربره', label: 'نقش‌های مدیر، حسابدار، فروشنده، انباردار' },
]

const PLATFORMS = [
  {
    icon: Globe,
    title: 'نسخه‌ی وب',
    desc: 'بدونِ نصب، از هر مرورگری وارد شوید و کار کنید — همه‌چیز روی ابر و همیشه به‌روز.',
    points: ['بدونِ نصب و نگهداری', 'دسترسی از هر دستگاه', 'پشتیبان‌گیریِ خودکار'],
    action: { href: APP_URL, label: 'ورود به نسخه‌ی وب', external: true },
  },
  {
    icon: MonitorSmartphone,
    title: 'نسخه‌ی ویندوز',
    desc: 'اینترنت قطع شد؟ نسخه‌ی دسکتاپ آفلاین کار می‌کند و با اتصالِ دوباره خودکار هم‌گام می‌شود.',
    points: ['کارِ کاملاً آفلاین', 'هم‌گام‌سازیِ خودکار', 'سرعتِ بالای محلی'],
    action: { href: DOWNLOAD_URL, label: 'دانلود برای ویندوز', download: true },
  },
  {
    icon: Smartphone,
    title: 'اپ اندروید',
    desc: 'داشبورد و گزارش، ثبتِ فاکتور و دریافت و پرداخت، و هشدارها به‌صورتِ اعلانِ زنده.',
    points: ['ثبتِ فاکتور و دریافت در حرکت', 'اعلانِ زنده‌ی هشدارها', 'به‌روزرسانیِ خودکار'],
    action: { href: ANDROID_APK_URL, label: 'دانلودِ اپ اندروید' },
  },
  {
    icon: Building2,
    title: 'کوبیتا سازمانی',
    desc: 'برای شرکت‌ها و سازمان‌ها: یک رایانه‌ی شرکت سرور می‌شود و حسابدارها از شبکه‌ی داخلی وصل می‌شوند — داده از شرکت بیرون نمی‌رود.',
    points: ['سرور و کلاینت روی شبکه‌ی داخلی', 'داده‌ی کاملاً درون‌سازمانی', 'فعال‌سازی با کدِ مجوز'],
    action: { href: ENTERPRISE_DOWNLOAD_URL, label: 'دانلودِ نصاب', download: true },
    //: نصاب ۳۰ روز آزمایشی کار می‌کند؛ برای کارِ واقعی کدِ مجوز لازم است — از همان فرمِ خرید.
    contact: 'enterprise' as const,
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
  { icon: ReceiptText, title: 'فروش و فاکتور', desc: 'صدورِ فاکتور، پیش‌فاکتور و رسید در چند ثانیه — با ثبتِ خودکارِ سندِ حسابداری.' },
  { icon: BarChart3, title: 'گزارش‌های زنده', desc: 'ترازنامه، سود و زیان و دفترِ کل، همیشه به‌روز و مستقیم از دلِ دفاتر.' },
  { icon: Calculator, title: 'حسابداریِ دوطرفه', desc: 'دفترِ کل، سندِ دستی و خودکار، و بستنِ دوره — دقیق و استاندارد.' },
  { icon: CreditCard, title: 'صندوق و پرداخت', desc: 'صندوقِ فروشگاهی، کارت‌خوان و مدیریتِ دریافت و پرداختِ روزانه.' },
  { icon: Landmark, title: 'چک و بانک', desc: 'دفترِ چک، مغایرت‌گیریِ بانکی و سررسیدها — بدونِ دفترچه و اکسل.' },
  { icon: BookOpen, title: 'انبار و کاردکس', desc: 'کاردکس، قیمتِ تمام‌شده و موجودیِ لحظه‌ای، گره‌خورده با حسابداری.' },
]

const STEPS = [
  { icon: MousePointerClick, title: 'امتحانِ رایگان', desc: 'ثبت‌نام کنید و ۱۴ روز با همه‌ی امکاناتِ اصلی کار کنید — بدونِ پرداخت.' },
  { icon: MessagesSquare, title: 'گفت‌وگو با کارشناس', desc: 'فرمِ «خرید و مشاوره» را پر کنید؛ کارشناسِ فروش تماس می‌گیرد و نسخه و قیمتِ مناسبِ شما را می‌گوید.' },
  { icon: Settings2, title: 'راه‌اندازی', desc: 'حسابتان تمدید و ارتقا می‌شود، یا برای کوبیتا سازمانی کدِ مجوز صادر می‌شود — داده‌ی دوره‌ی آزمایشی می‌ماند.' },
  { icon: Rocket, title: 'شروعِ کار', desc: 'وارد نسخه‌ی وب یا ویندوز شوید و اولین فاکتور را ثبت کنید.' },
]

const WHY = [
  { icon: Zap, title: 'راه‌اندازیِ چنددقیقه‌ای', desc: 'ثبت‌نام کنید و همان لحظه شروع کنید؛ بدونِ نصب و بدونِ پیچیدگی.' },
  { icon: Layers, title: 'آنلاین و آفلاین', desc: 'یک حساب، هم روی مرورگر و هم روی نسخه‌ی آفلاینِ ویندوز — همیشه هم‌گام.' },
  { icon: ShieldCheck, title: 'داده‌ی ایزوله و امن', desc: 'اطلاعاتِ هر کسب‌وکار در سطحِ پایگاه‌داده جدا و محافظت‌شده است.' },
]

const FAQS = [
  { q: 'آیا داده‌های کسب‌وکار من امن است؟', a: 'بله. هر مشتری روی یک نسخه‌ی کاملاً ایزوله (دیتابیس، سرویس و آدرس اختصاصی) اجرا می‌شود؛ داده‌ی هیچ کسب‌وکاری با دیگری در یک دیتابیس مشترک نیست. اتصال هم همیشه از طریق HTTPS رمزنگاری‌شده است.' },
  { q: 'نسخه‌ی آزمایشیِ رایگان چطور کار می‌کند؟', a: 'ثبت‌نام می‌کنید و ۱۴ روز کاملِ رایگان همه‌ی امکاناتِ اصلی را دارید. اگر خرید کنید، همه‌ی اطلاعاتِ دوره‌ی آزمایشی حفظ می‌شود.' },
  { q: 'اگر اینترنت قطع شود چه اتفاقی می‌افتد؟', a: 'نسخه‌ی ویندوز کاملاً آفلاین کار می‌کند: فاکتور، سندِ حسابداری و بقیه‌ی عملیات محلی ذخیره می‌شوند و با اتصالِ دوباره، خودکار با سرورِ مرکزی هم‌گام می‌شوند.' },
  { q: 'چند نفر می‌توانند هم‌زمان استفاده کنند؟', a: 'به اندازه‌ی نیازتان — هر کاربر با نقشِ مشخص (مدیر، حسابدار، فروشنده، انباردار، مسئولِ حقوق) و دسترسیِ محدود به همان بخش. تعدادِ کاربر را در فرمِ «خرید و مشاوره» بنویسید.' },
  { q: 'چطور بخرم؟', a: 'فرمِ «خرید و مشاوره» پایینِ همین صفحه را پر کنید. کارشناسِ فروش در ساعاتِ کاری تماس می‌گیرد، بر اساسِ کسب‌وکار و تعدادِ کاربرتان نسخه‌ی مناسب را پیشنهاد می‌کند و قیمت را می‌گوید.' },
  { q: 'کوبیتا سازمانی چه فرقی دارد؟', a: 'کوبیتا سازمانی روی سرورِ خودِ شرکت نصب می‌شود و حسابدارها از رایانه‌های شبکه‌ی داخلی وصل می‌شوند؛ داده هیچ‌وقت از شرکت بیرون نمی‌رود و به اینترنت هم نیازی نیست. نصاب را دانلود کنید — ۳۰ روز آزمایشی کار می‌کند — و برای کدِ مجوز با ما تماس بگیرید.' },
  { q: 'امکانِ اتصال به سامانه‌ی مؤدیان هست؟', a: 'بله. صورتحساب‌های الکترونیکی مطابق با الزاماتِ سازمانِ امورِ مالیاتی ارسال می‌شوند؛ شرایطش را کارشناسِ فروش برای نسخه‌ی شما می‌گوید.' },
]

//: ورودِ آرام و کوتاه — سایتِ اداری جای حرکتِ نمایشی نیست. `MotionConfig` بالای صفحه
//: همین را برای کاربری که «کاهشِ حرکت» را روشن کرده کاملاً خاموش می‌کند.
const reveal = {
  initial: { opacity: 0, y: 14 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.45, ease: 'easeOut' },
} as const

/**
 * بنرِ تمام‌عرضِ زیرِ منو — به خواستِ کاربر. پیامِ کوتاهِ دعوت است، نه تکرارِ هیرو: هیرو
 * می‌گوید کوبیتا چیست، بنر می‌گوید از کجا و چطور شروع کنید.
 */
function HomeBanner() {
  return (
    <section className="cc-banner" aria-labelledby="cc-banner-title">
      <div className="cc-banner-in">
        <div className="cc-banner-copy">
          <span className="cc-banner-tag">۱۴ روز رایگان، با همه‌ی امکاناتِ اصلی</span>
          <h2 id="cc-banner-title" className="cc-banner-title">
            کوبیتا؛ حسابداریِ کسب‌وکار روی وب، ویندوز و اندروید
          </h2>
          <p>یک حساب برای هر سه نسخه، با داده‌ی همیشه هم‌گام. همین امروز ثبت‌نام کنید و اولین فاکتور را صادر کنید.</p>
          <div className="cc-banner-cta">
            <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
              شروعِ رایگان <ArrowLeft size={16} />
            </a>
            <a className="cc-btn cc-btn-on-dark" href="#cc-platforms">
              <Download size={16} /> دانلودِ نسخه‌ها
            </a>
          </div>
        </div>
        <div className="cc-banner-art" aria-hidden="true">
          <svg viewBox="0 0 240 240" fill="none">
            <circle cx="120" cy="120" r="118" stroke="#fff" strokeOpacity="0.16" strokeWidth="2" />
            <circle cx="120" cy="120" r="86" stroke="#fff" strokeOpacity="0.12" strokeWidth="2" />
            <rect x="62" y="124" width="26" height="54" rx="13" fill="#fff" fillOpacity="0.55" />
            <rect x="107" y="96" width="26" height="82" rx="13" fill="#fff" fillOpacity="0.75" />
            <rect x="152" y="70" width="26" height="108" rx="13" fill="#fff" />
            <circle cx="165" cy="44" r="12" fill="#06B6D4" />
          </svg>
        </div>
      </div>
    </section>
  )
}

function Hero() {
  return (
    <section className="cc-hero">
      <div className="cc-hero-inner">
        <motion.div
          className="cc-hero-copy"
          initial={reveal.initial}
          animate={{ opacity: 1, y: 0 }}
          transition={reveal.transition}
        >
          <span className="cc-eyebrow">نرم‌افزارِ حسابداریِ ابری و آفلاین</span>
          <h1 className="cc-hero-title">
            حسابداریِ کسب‌وکار، <span className="cc-accent-text">ساده و دقیق</span>
          </h1>
          <p className="cc-hero-sub">
            فروش، خرید و انبار، حسابداریِ دوطرفه، چک و بانک و حقوق و دستمزد — همه در یک سامانه‌ی یکپارچه که سندِ
            هر عملیات را خودش ثبت می‌کند؛ روی وب، ویندوز و موبایل، حتی بدونِ اینترنت.
          </p>
          <div className="cc-hero-cta">
            <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
              شروعِ ۱۴ روز رایگان
            </a>
            <a className="cc-btn cc-btn-outline" href="#cc-contact">
              <PhoneCall size={16} /> خرید و مشاوره
            </a>
          </div>
          <ul className="cc-hero-trust">
            <li>
              <Check size={15} /> بدونِ نصب روی نسخه‌ی وب
            </li>
            <li>
              <Check size={15} /> کارِ آفلاین روی ویندوز
            </li>
            <li>
              <Check size={15} /> ارسال به سامانه‌ی مؤدیان
            </li>
          </ul>
        </motion.div>

        <div className="cc-facts">
          {FACTS.map((f, i) => (
            <motion.div className="cc-fact" key={f.value} {...reveal} transition={{ ...reveal.transition, delay: i * 0.05 }}>
              <span className="cc-icon">
                <f.icon size={20} />
              </span>
              <b>{f.value}</b>
              <span>{f.label}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

function SectionHead({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <motion.div className="cc-section-head" {...reveal}>
      <span className="cc-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {sub && <p>{sub}</p>}
    </motion.div>
  )
}

function Platforms() {
  return (
    <section className="cc-section cc-section-alt" id="cc-platforms">
      <SectionHead
        eyebrow="نسخه‌ها"
        title="وب، ویندوز، اندروید — و نسخه‌ی سازمانی"
        sub="یک حسابِ ابری روی هر سه نسخه، همیشه هم‌گام؛ و برای شرکت‌هایی که داده باید در خودِ شرکت بماند، کوبیتا سازمانی."
      />
      <div className="cc-grid cc-grid-4 cc-platform-grid">
        {PLATFORMS.map((p) => (
          <motion.div key={p.title} className="cc-card cc-platform" {...reveal}>
            <span className="cc-icon cc-icon-lg">
              <p.icon size={24} />
            </span>
            <h3>{p.title}</h3>
            <p>{p.desc}</p>
            <ul className="cc-checklist">
              {p.points.map((pt) => (
                <li key={pt}>
                  <Check size={15} /> {pt}
                </li>
              ))}
            </ul>
            <div className="cc-card-action cc-card-actions">
              <a
                className="cc-btn cc-btn-outline"
                href={p.action.href}
                {...('external' in p.action ? { target: '_blank', rel: 'noreferrer' } : {})}
                {...('download' in p.action ? { download: true } : {})}
              >
                {p.action.label}
              </a>
              {'contact' in p && p.contact && (
                <button type="button" className="cc-btn cc-btn-primary" onClick={() => openContact(p.contact)}>
                  درخواستِ مجوز
                </button>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

function Features() {
  return (
    <section className="cc-section" id="cc-features">
      <SectionHead eyebrow="امکانات" title="همه‌ی ابزارِ حسابداری، در یک نرم‌افزار" sub="از فروش و انبار تا چک و بانک و گزارش‌ها — هر بخش با بخش‌های دیگر یکپارچه است و سندِ خودش را خودکار ثبت می‌کند." />
      <div className="cc-grid cc-grid-3">
        {FEATURES.map((f) => (
          <motion.div key={f.title} className="cc-card" {...reveal}>
            <span className="cc-icon cc-icon-lg">
              <f.icon size={24} />
            </span>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

function Industries() {
  return (
    <section className="cc-section cc-section-alt" id="cc-industries">
      <SectionHead eyebrow="صنایع" title="از یک فروشگاه تا یک شرکتِ پخش" sub="کوبیتا با نیازِ کسب‌وکارهای مختلف هماهنگ می‌شود." />
      <div className="cc-grid cc-grid-3 cc-ind-grid">
        {INDUSTRIES.map((it) => (
          <motion.div key={it.label} className="cc-ind" {...reveal}>
            <span className="cc-icon">
              <it.icon size={19} />
            </span>
            <span>{it.label}</span>
          </motion.div>
        ))}
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section className="cc-section" id="cc-how">
      <SectionHead eyebrow="شروعِ کار" title="در چهار قدم شروع کنید" sub="از اولین امتحان تا ثبتِ اولین فاکتور — بی‌آنکه چیزی را از دست بدهید." />
      <ol className="cc-grid cc-grid-4 cc-steps">
        {STEPS.map((s, i) => (
          <motion.li key={s.title} className="cc-card cc-step" {...reveal}>
            <span className="cc-step-no">{(i + 1).toLocaleString('fa-IR')}</span>
            <h3>{s.title}</h3>
            <p>{s.desc}</p>
          </motion.li>
        ))}
      </ol>
    </section>
  )
}

function WhySection() {
  return (
    <section className="cc-section" id="cc-why">
      <SectionHead eyebrow="چرا کوبیتا" title="ساخته‌شده برای کسب‌وکارهای ایرانی" sub="فارسی، ابری و آفلاین، با پشتیبانی و قیمتِ داخلی — بدونِ پیچیدگیِ نرم‌افزارهای بزرگ." />
      <div className="cc-grid cc-grid-3">
        {WHY.map((w) => (
          <motion.div key={w.title} className="cc-card cc-why-item" {...reveal}>
            <span className="cc-icon">
              <w.icon size={20} />
            </span>
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
    <section className="cc-section cc-section-alt" id="cc-faq">
      <SectionHead eyebrow="سوالاتِ متداول" title="پاسخِ پرسش‌های رایج" />
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
    <section className="cc-final-cta">
      <div className="cc-final-cta-in">
        <div>
          <h2>همین امروز، رایگان شروع کنید</h2>
          <p>۱۴ روز کاملِ رایگان. اگر پسندیدید، با کارشناسِ فروش تماس بگیرید — همه‌ی اطلاعاتتان حفظ می‌شود.</p>
        </div>
        <div className="cc-final-cta-btns">
          <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
            شروعِ ۱۴ روز رایگان
          </a>
          <a className="cc-btn cc-btn-on-dark" href="#cc-contact">
            <PhoneCall size={16} /> تماس برای خرید
          </a>
        </div>
      </div>
    </section>
  )
}

export function ConceptLanding() {
  return (
    <MotionConfig reducedMotion="user">
      <div className="cc-root" dir="rtl">
        <SiteHeader />
        <main>
          <HomeBanner />
          <Hero />
          <Platforms />
          <Features />
          <Industries />
          <HowItWorks />
          <ContactSection />
          <WhySection />
          <FaqSection />
          <FinalCta />
        </main>
        <SiteFooter />
      </div>
    </MotionConfig>
  )
}
