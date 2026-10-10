import { ArrowLeft, Check, Lock } from 'lucide-react'
import { FaqList } from '../concept/FaqList'
import { FinalCta } from '../concept/FinalCta'
import { PageLayout } from '../concept/PageLayout'
import { featureBySlug, type FeaturePage as Feature } from '../content/features'
import { TRIAL_URL } from '../content/links'
import { FEATURE_METAS } from '../seo/pages'

/** یک صفحه‌ی امکانات — همه از یک الگو، محتوا از `content/features.ts`. */
export function FeaturePage({ feature }: { feature: Feature }) {
  const meta = FEATURE_METAS.find((m) => m.path === `/features/${feature.slug}`)!
  const related = feature.related.map(featureBySlug).filter((f): f is Feature => !!f)
  return (
    <PageLayout meta={meta}>
      <section className="cc-page-hero">
        <div className="cc-page-hero-in">
          <span className="cc-icon cc-icon-lg cc-page-hero-icon">
            <feature.icon size={24} />
          </span>
          <h1>{feature.h1}</h1>
          <p className="cc-lead">{feature.lead}</p>
          <div className="cc-hero-cta">
            <a className="cc-btn cc-btn-primary" href={TRIAL_URL}>
              شروعِ ۱۴ روز رایگان
            </a>
            <a className="cc-btn cc-btn-outline" href="/enterprise">
              {feature.premium ? 'کوبیتا سازمانی' : 'کوبیتا سازمانیِ رایگان'}
            </a>
          </div>
          {feature.premium && (
            <p className="cc-note cc-note-inline">
              <Lock size={16} />
              <span>
                این قابلیت در پلن‌های کاملِ نسخه‌ی ابری و مجوزِ تجاریِ کوبیتا سازمانی است؛ در نسخه‌ی آزمایشی و نسخه‌ی رایگانِ
                سازمانی نیست.
              </span>
            </p>
          )}
        </div>
      </section>

      <section className="cc-section">
        <div className="cc-grid cc-grid-3">
          {feature.sections.map((s) => (
            <div key={s.title} className="cc-card">
              <h2 className="cc-card-title">{s.title}</h2>
              <ul className="cc-checklist cc-checklist-top">
                {s.points.map((p) => (
                  <li key={p}>
                    <Check size={15} /> {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section className="cc-section cc-section-alt" id="faq">
        <div className="cc-section-head">
          <span className="cc-eyebrow">سوالاتِ متداول</span>
          <h2>پرسش‌های رایج درباره‌ی {feature.name}</h2>
        </div>
        <FaqList items={feature.faqs} idPrefix={`${feature.slug}-faq`} />
      </section>

      {related.length > 0 && (
        <section className="cc-section">
          <div className="cc-section-head">
            <span className="cc-eyebrow">یکپارچه با</span>
            <h2>بخش‌های مرتبط</h2>
          </div>
          <ul className="cc-grid cc-grid-3">
            {related.map((r) => (
              <li key={r.slug} className="cc-card cc-feature-card">
                <span className="cc-icon">
                  <r.icon size={20} />
                </span>
                <h3>
                  <a href={`/features/${r.slug}`} className="cc-stretch">
                    {r.h1}
                  </a>
                </h3>
                <p>{r.lead}</p>
                <span className="cc-more">
                  بیشتر بخوانید <ArrowLeft size={15} />
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <FinalCta />
    </PageLayout>
  )
}
