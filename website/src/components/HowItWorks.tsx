import { CreditCard, MousePointerClick, Rocket, Settings2 } from 'lucide-react'

const STEPS = [
  {
    icon: MousePointerClick,
    title: 'پلن مناسب را انتخاب کنید',
    desc: 'بر اساس تعداد کاربران و نیازتان، یکی از پلن‌های پایه، حرفه‌ای یا سازمانی را انتخاب کنید.',
  },
  {
    icon: CreditCard,
    title: 'پرداخت امن با زرین‌پال',
    desc: 'مبلغ پلن را از طریق درگاه معتبر زرین‌پال پرداخت کنید — کاملاً امن و آنی.',
  },
  {
    icon: Settings2,
    title: 'راه‌اندازی نسخه‌ی اختصاصی',
    desc: 'تیم کوبیتا طی چند ساعت نسخه‌ی اختصاصی و ایزوله‌ی شما را راه‌اندازی و اطلاعات ورود را ارسال می‌کند.',
  },
  {
    icon: Rocket,
    title: 'شروع به کار',
    desc: 'وارد اپ دسکتاپ یا نسخه‌ی وب شوید، چارت حساب و انبار را تنظیم کنید و اولین فاکتور را ثبت کنید.',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">شروع کار</span>
          <h2>در چهار قدم ساده شروع کنید</h2>
          <p>از انتخاب پلن تا ثبت اولین فاکتور، معمولاً کمتر از یک روز طول می‌کشد.</p>
        </div>
        <div className="steps-row">
          {STEPS.map((s, idx) => (
            <div className="step-card" key={s.title}>
              <span className="step-number">{String(idx + 1).padStart(2, '0')}</span>
              <span className="step-icon">
                <s.icon size={20} />
              </span>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
