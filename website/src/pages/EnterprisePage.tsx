import { Check, DatabaseBackup, Download, Minus, Network, RefreshCw, Server, ShieldCheck } from 'lucide-react'
import { ContactSection } from '../concept/ContactSection'
import { FaqList } from '../concept/FaqList'
import { FinalCta } from '../concept/FinalCta'
import { PageLayout } from '../concept/PageLayout'
import { COMPARE, ENTERPRISE_FAQS, FREE_SEATS, INSTALL_STEPS } from '../content/enterprise'
import { ENTERPRISE_DOWNLOAD_URL } from '../content/links'
import { ENTERPRISE_META } from '../seo/pages'

const fa = (n: number) => n.toLocaleString('fa-IR')

const FACTS = [
  { icon: Server, title: 'سرور در خودِ شرکت', desc: 'یک رایانه‌ی شرکت سرور می‌شود؛ پایگاه‌داده همراهِ نصاب نصب می‌شود.' },
  { icon: Network, title: 'کلاینت روی شبکه‌ی داخلی', desc: 'حسابدارها از رایانه‌های خودشان به همان سرور وصل می‌شوند.' },
  { icon: DatabaseBackup, title: 'پشتیبانِ خودکارِ شبانه', desc: 'هر شب پشتیبانِ کامل؛ پشتیبانِ کهنه به مدیر هشدار می‌دهد.' },
  { icon: RefreshCw, title: 'به‌روزرسانی از سرور', desc: 'سرور نسخه‌ی تازه را می‌گیرد و کلاینت‌ها از همان سرور به‌روز می‌شوند.' },
]

function Cell({ value }: { value: string | boolean }) {
  if (value === true) return <Check size={18} className="cc-yes" aria-label="دارد" />
  if (value === false) return <Minus size={18} className="cc-no" aria-label="ندارد" />
  return <>{value}</>
}

export function EnterprisePage() {
  return (
    <PageLayout meta={ENTERPRISE_META}>
      <section className="cc-page-hero">
        <div className="cc-page-hero-in cc-page-hero-split">
          <div>
            <span className="cc-eyebrow">رایگان تا {fa(FREE_SEATS)} کاربر، برای همیشه</span>
            <h1>کوبیتا سازمانی؛ نرم‌افزار حسابداری تحت شبکه، رایگان</h1>
            <p className="cc-lead">
              حسابداری، فروش، خرید، انبار، چک و بانک و حقوق روی سرورِ خودِ شرکت؛ حسابدارها از شبکه‌ی داخلی کار می‌کنند و
              داده از شرکت بیرون نمی‌رود. با یک ثبت‌نامِ ساده — نامِ سازمان و شماره‌ی همراه — تا سه کاربر رایگان است.
            </p>
            <div className="cc-hero-cta">
              <a className="cc-btn cc-btn-primary" href={ENTERPRISE_DOWNLOAD_URL} download>
                <Download size={16} /> دانلودِ رایگان
              </a>
              <a className="cc-btn cc-btn-outline" href="#pricing">
                مقایسه‌ی رایگان و تجاری
              </a>
            </div>
            <ul className="cc-hero-trust">
              <li>
                <Check size={15} /> بی‌انقضا
              </li>
              <li>
                <Check size={15} /> ویندوز ۱۰ و ۱۱ (۶۴ بیتی)
              </li>
              <li>
                <Check size={15} /> اینترنت فقط برای ثبت‌نام
              </li>
            </ul>
          </div>
          <ul className="cc-facts cc-facts-list">
            {FACTS.map((f) => (
              <li className="cc-fact" key={f.title}>
                <span className="cc-icon">
                  <f.icon size={20} />
                </span>
                <b>{f.title}</b>
                <span>{f.desc}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="cc-section cc-section-alt" id="pricing">
        <div className="cc-section-head">
          <span className="cc-eyebrow">رایگان و تجاری</span>
          <h2>چه چیزی رایگان است؟</h2>
          <p>
            همه‌ی دفترِ حسابداری رایگان است. مجوزِ تجاری فقط وقتی لازم است که کاربرِ بیشتر، سامانه‌ی مؤدیان یا پشتیبانیِ
            کارشناس بخواهید — و روی همان نصب و همان داده‌ها اضافه می‌شود.
          </p>
        </div>
        <div className="cc-compare-wrap">
          <table className="cc-compare">
            <caption className="cc-sr">مقایسه‌ی نسخه‌ی رایگان و مجوزِ تجاریِ کوبیتا سازمانی</caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="cc-sr">قابلیت</span>
                </th>
                <th scope="col">رایگان</th>
                <th scope="col">تجاری</th>
              </tr>
            </thead>
            <tbody>
              {COMPARE.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  <td>
                    <Cell value={row.free} />
                  </td>
                  <td>
                    <Cell value={row.paid} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td />
                <td>
                  <a className="cc-btn cc-btn-primary cc-btn-sm" href={ENTERPRISE_DOWNLOAD_URL} download>
                    دانلودِ رایگان
                  </a>
                </td>
                <td>
                  <a className="cc-btn cc-btn-outline cc-btn-sm" href="#cc-contact">
                    درخواستِ مجوزِ تجاری
                  </a>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section className="cc-section" id="install">
        <div className="cc-section-head">
          <span className="cc-eyebrow">راه‌اندازی</span>
          <h2>نصب در چهار قدم</h2>
          <p>یک نصاب برای سرور و کلاینت؛ نقشِ هر رایانه را هنگامِ نصب انتخاب می‌کنید.</p>
        </div>
        <ol className="cc-grid cc-grid-4 cc-steps">
          {INSTALL_STEPS.map((s, i) => (
            <li key={s.title} className="cc-card cc-step">
              <span className="cc-step-no">{fa(i + 1)}</span>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </li>
          ))}
        </ol>
        <div className="cc-note">
          <ShieldCheck size={18} />
          <p>
            <b>نیازمندی‌ها:</b> ویندوز ۱۰ یا ۱۱ ۶۴ بیتی برای سرور و کلاینت‌ها، و شبکه‌ی داخلی (کابل، مودم یا Wi‑Fi). ویندوز
            ۷، ۸ و ۸٫۱ پشتیبانی نمی‌شوند. سرورِ بی‌اینترنت هم فعال می‌شود: «کدِ درخواست» را برای پشتیبانی بفرستید.
          </p>
        </div>
      </section>

      <section className="cc-section cc-section-alt" id="faq">
        <div className="cc-section-head">
          <span className="cc-eyebrow">سوالاتِ متداول</span>
          <h2>پرسش‌های رایج درباره‌ی کوبیتا سازمانی</h2>
        </div>
        <FaqList items={ENTERPRISE_FAQS} idPrefix="ent-faq" />
      </section>

      <ContactSection defaultProduct="enterprise" />
      <FinalCta
        title="کوبیتا سازمانی را همین امروز نصب کنید"
        text="دانلود رایگان است و ثبت‌نام یک دقیقه طول می‌کشد. برای کاربرِ بیشتر یا سامانه‌ی مؤدیان با کارشناسِ فروش صحبت کنید."
        contactHref="#cc-contact"
      />
    </PageLayout>
  )
}
