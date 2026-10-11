import { ArrowLeft } from 'lucide-react'
import { FinalCta } from '../concept/FinalCta'
import { PageLayout } from '../concept/PageLayout'
import { FEATURES, OTHER_MODULES } from '../content/features'
import { FEATURES_META } from '../seo/pages'

export function FeaturesPage() {
  return (
    <PageLayout meta={FEATURES_META}>
      <section className="cc-page-hero">
        <div className="cc-page-hero-in">
          <span className="cc-eyebrow">امکانات</span>
          <h1>امکانات نرم‌افزار حسابداری کوبیتا</h1>
          <p className="cc-lead">
            هر بخشِ کوبیتا با بقیه یکپارچه است: فاکتور موجودی را کم می‌کند، چک حسابِ بانک را به‌روز می‌کند و فیشِ حقوق سندِ
            خودش را می‌زند — شما فقط بازبینی می‌کنید.
          </p>
        </div>
      </section>

      <section className="cc-section">
        <ul className="cc-grid cc-grid-3">
          {FEATURES.map((f) => (
            <li key={f.slug} className="cc-card cc-feature-card">
              <span className="cc-icon cc-icon-lg">
                <f.icon size={24} />
              </span>
              <h2 className="cc-card-title">
                <a href={`/features/${f.slug}`} className="cc-stretch">
                  {f.h1}
                </a>
              </h2>
              <p>{f.lead}</p>
              <span className="cc-more">
                بیشتر بخوانید <ArrowLeft size={15} />
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="cc-section cc-section-alt">
        <div className="cc-section-head">
          <span className="cc-eyebrow">و همچنین</span>
          <h2>ماژول‌های دیگر</h2>
          <p>این‌ها هم در همان برنامه‌اند و با حسابداری یکپارچه کار می‌کنند.</p>
        </div>
        <ul className="cc-tags">
          {OTHER_MODULES.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </section>

      <FinalCta />
    </PageLayout>
  )
}
