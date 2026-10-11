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
  DatabaseZap,
  Users,
  Download,
  Check,
  Building2,
  MessagesSquare,
  PhoneCall,
} from 'lucide-react'
import { ContactSection } from '../concept/ContactSection'
import { FaqList } from '../concept/FaqList'
import { FinalCta } from '../concept/FinalCta'
import { PageLayout } from '../concept/PageLayout'
import { BRAND_CELLS } from '../concept/brand'
import { HOME_FAQS } from '../content/home'
import { ANDROID_APK_URL, APP_URL, DOWNLOAD_URL, ENTERPRISE_DOWNLOAD_URL, TRIAL_URL } from '../content/links'
import type { PageMeta } from '../seo/meta'
import { HOME_META } from '../seo/pages'

//: چهار واقعیتِ پایه‌ای که کنارِ متنِ هیرو می‌نشینند — جایگزینِ خوشه‌ی کارت‌های شناور، به
//: خواستِ کاربر («سایت ساده، اداری و شیک باشد»).
const FACTS = [
  { icon: DatabaseZap, value: 'داده‌ی ایزوله', label: 'جداسازیِ داده‌ی هر کسب‌وکار در سطحِ پایگاه‌داده' },
  { icon: MonitorSmartphone, value: 'وب، ویندوز، اندروید', label: 'یک حساب، سه نسخه‌ی هم‌گام' },
  { icon: Building2, value: 'سازمانیِ رایگان', label: 'سرور در خودِ شرکت، تا سه کاربر رایگان' },
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
    points: ['رایگان و همیشگی تا سه کاربر', 'سرور و کلاینت روی شبکه‌ی داخلی', 'داده‌ی کاملاً درون‌سازمانی'],
    action: { href: ENTERPRISE_DOWNLOAD_URL, label: 'دانلودِ رایگان', download: true },
    more: { href: '/enterprise', label: 'معرفی و مقایسه' },
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

//: هر کارت به صفحه‌ی امکاناتِ خودش می‌رود (`/features/...`) — پیوندِ داخلی با متنِ کلیدواژه.
const FEATURES = [
  { icon: ReceiptText, title: 'فروش و فاکتور', desc: 'صدورِ فاکتور، پیش‌فاکتور و رسید در چند ثانیه — با ثبتِ خودکارِ سندِ حسابداری.', slug: 'sales-invoice' },
  { icon: BarChart3, title: 'گزارش‌های زنده', desc: 'ترازنامه، سود و زیان و دفترِ کل، همیشه به‌روز و مستقیم از دلِ دفاتر.', slug: 'accounting' },
  { icon: Calculator, title: 'حسابداریِ دوطرفه', desc: 'دفترِ کل، سندِ دستی و خودکار، و بستنِ دوره — دقیق و استاندارد.', slug: 'accounting' },
  { icon: CreditCard, title: 'صندوق و پرداخت', desc: 'صندوقِ فروشگاهی، کارت‌خوان و مدیریتِ دریافت و پرداختِ روزانه.', slug: 'pos' },
  { icon: Landmark, title: 'چک و بانک', desc: 'دفترِ چک، مغایرت‌گیریِ بانکی و سررسیدها — بدونِ دفترچه و اکسل.', slug: 'cheque-bank' },
  { icon: BookOpen, title: 'انبار و کاردکس', desc: 'کاردکس، قیمتِ تمام‌شده و موجودیِ لحظه‌ای، گره‌خورده با حسابداری.', slug: 'inventory' },
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
            <a className="cc-btn cc-btn-on-dark" href="/download">
              <Download size={16} /> دانلودِ نسخه‌ها
            </a>
          </div>
        </div>
        {/* خانه‌های نشان در اندازه‌ی بزرگ، یکی‌یکی می‌نشینند (CSS: cc-cell-in و تأخیرِ nth-of-type)؛ آخرین،
            خانه‌ی فعالِ بنفش. تأخیر در CSS است نه `style`: CSPِ سایت `style`ِ درون‌خطی را در HTMLِ
            پیش‌رندرشده نمی‌پذیرد. */}
        <div className="cc-banner-art" aria-hidden="true">
          <svg viewBox="20 20 80 80">
            {BRAND_CELLS.map(([x, y]) => (
              <rect key={`${x}-${y}`} className="cc-cell" x={x} y={y} width="20" height="20" rx="5" />
            ))}
            <rect className="cc-cell cc-cell-active" x="76" y="24" width="20" height="20" rx="5" />
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
        <div className="cc-hero-copy cc-rise">
          <span className="cc-eyebrow">نرم‌افزارِ حسابداریِ ابری و آفلاین</span>
          <h1 className="cc-hero-title">
            نرم‌افزار حسابداری کسب‌وکار، <span className="cc-accent-text">ساده و دقیق</span>
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
        </div>

        <div className="cc-facts">
          {FACTS.map((f) => (
            <div className="cc-fact" key={f.value}>
              <span className="cc-icon">
                <f.icon size={20} />
              </span>
              <b>{f.value}</b>
              <span>{f.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function SectionHead({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <div className="cc-section-head">
      <span className="cc-eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {sub && <p>{sub}</p>}
    </div>
  )
}

function Platforms() {
  return (
    <section className="cc-section cc-section-alt" id="cc-platforms">
      <SectionHead
        eyebrow="نسخه‌ها"
        title="وب، ویندوز، اندروید — و نسخه‌ی سازمانی"
        sub="یک حسابِ ابری روی هر سه نسخه، همیشه هم‌گام؛ و برای شرکت‌هایی که داده باید در خودِ شرکت بماند، کوبیتا سازمانی — رایگان تا سه کاربر."
      />
      <div className="cc-grid cc-grid-4 cc-platform-grid">
        {PLATFORMS.map((p) => (
          <div key={p.title} className="cc-card cc-platform">
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
              {'more' in p && p.more && (
                <a className="cc-btn cc-btn-primary" href={p.more.href}>
                  {p.more.label}
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

/** نوارِ «سازمانیِ رایگان» — پیوندِ داخلیِ اصلی به `/enterprise` با همان عبارتی که جست‌وجو می‌شود. */
function EnterpriseBand() {
  return (
    <section className="cc-section cc-ent-band" aria-labelledby="cc-ent-band-title">
      <div className="cc-ent-band-in">
        <div>
          <span className="cc-eyebrow">کوبیتا سازمانی</span>
          <h2 id="cc-ent-band-title">نرم‌افزار حسابداری تحت شبکه، رایگان تا سه کاربر</h2>
          <p>
            سرور در خودِ شرکت، حسابدارها روی شبکه‌ی داخلی و داده‌ای که از شرکت بیرون نمی‌رود. فقط یک‌بار با نام و شماره‌ی همراه
            ثبت‌نام کنید؛ برای همیشه رایگان است.
          </p>
        </div>
        <div className="cc-ent-band-cta">
          <a className="cc-btn cc-btn-primary" href={ENTERPRISE_DOWNLOAD_URL} download>
            <Download size={16} /> دانلودِ رایگان
          </a>
          <a className="cc-btn cc-btn-outline" href="/enterprise">
            معرفی و مقایسه‌ی رایگان و تجاری
          </a>
        </div>
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
          <div key={f.title} className="cc-card cc-feature-card">
            <span className="cc-icon cc-icon-lg">
              <f.icon size={24} />
            </span>
            <h3>
              <a href={`/features/${f.slug}`} className="cc-stretch">
                {f.title}
              </a>
            </h3>
            <p>{f.desc}</p>
          </div>
        ))}
      </div>
      <p className="cc-center cc-section-more">
        <a className="cc-btn cc-btn-outline" href="/features">
          همه‌ی امکانات <ArrowLeft size={16} />
        </a>
      </p>
    </section>
  )
}

function Industries() {
  return (
    <section className="cc-section cc-section-alt" id="cc-industries">
      <SectionHead eyebrow="صنایع" title="از یک فروشگاه تا یک شرکتِ پخش" sub="کوبیتا با نیازِ کسب‌وکارهای مختلف هماهنگ می‌شود." />
      <div className="cc-grid cc-grid-3 cc-ind-grid">
        {INDUSTRIES.map((it) => (
          <div key={it.label} className="cc-ind">
            <span className="cc-icon">
              <it.icon size={19} />
            </span>
            <span>{it.label}</span>
          </div>
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
          <li key={s.title} className="cc-card cc-step">
            <span className="cc-step-no">{(i + 1).toLocaleString('fa-IR')}</span>
            <h3>{s.title}</h3>
            <p>{s.desc}</p>
          </li>
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
          <div key={w.title} className="cc-card cc-why-item">
            <span className="cc-icon">
              <w.icon size={20} />
            </span>
            <div>
              <h3>{w.title}</h3>
              <p>{w.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function FaqSection() {
  return (
    <section className="cc-section cc-section-alt" id="cc-faq">
      <SectionHead eyebrow="سوالاتِ متداول" title="پاسخِ پرسش‌های رایج" />
      <FaqList items={HOME_FAQS} idPrefix="home-faq" />
    </section>
  )
}

export function ConceptLanding({ meta = HOME_META }: { meta?: PageMeta }) {
  return (
    <PageLayout meta={meta}>
      <HomeBanner />
      <Hero />
      <Platforms />
      <EnterpriseBand />
      <Features />
      <Industries />
      <HowItWorks />
      <ContactSection />
      <WhySection />
      <FaqSection />
      <FinalCta contactHref="#cc-contact" />
    </PageLayout>
  )
}
