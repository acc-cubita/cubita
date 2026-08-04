import { Check, ExternalLink, Sparkles, Store } from 'lucide-react'
import { PLANS_URL, STOREFRONT_DEMO_URL } from '../api'

/**
 * گالریِ قالب‌های فروشگاه («مارکت‌پلیس») — بالای بخشِ اتصال فروشگاه.
 * هر قالب با یک پیش‌نمایشِ مینیاتوری، ویژگی‌ها و دو دکمه نشان داده می‌شود:
 * «پیش‌نمایشِ زنده» (دموی خوداتکا روی VPS) و «انتخاب» (یا برای آزمایشی: تهیه‌ی پلن).
 *
 * ساختار آرایه‌ای است تا افزودنِ قالبِ بعدی فقط یک ردیف باشد.
 */
interface ThemeDef {
  id: string
  name: string
  tagline: string
  features: string[]
  accent: string
  accent2: string
  demoUrl: string
}

const THEMES: ThemeDef[] = [
  {
    id: 'general',
    name: 'قالبِ عمومی (چندمنظوره)',
    tagline: 'برای هر کسب‌وکاری: دیجیتال، پوشاک، لوازم خانه، زیبایی و…',
    features: ['واکنش‌گرا و موبایل‌پسند', 'سبد و تسویه‌ی آنلاین', 'پرداختِ درگاهِ خودتان', 'بهینه برای گوگل (SEO)'],
    accent: '#6d28d9',
    accent2: '#a855f7',
    demoUrl: STOREFRONT_DEMO_URL,
  },
]

/** پیش‌نمایشِ مینیاتوریِ یک قالب — مرورگرِ کوچک با هدر و سه کارتِ کالا، با رنگِ همان قالب. */
function ThemePreview({ accent, accent2 }: { accent: string; accent2: string }) {
  return (
    <div className="sg-preview" aria-hidden style={{ ['--sg-a' as string]: accent, ['--sg-b' as string]: accent2 }}>
      <div className="sg-bar">
        <span className="sg-dot" />
        <span className="sg-dot" />
        <span className="sg-dot" />
      </div>
      <div className="sg-head">
        <span className="sg-logo" />
        <span className="sg-search" />
        <span className="sg-cart" />
      </div>
      <div className="sg-grid">
        {[0, 1, 2].map((i) => (
          <div className="sg-card" key={i}>
            <span className="sg-img" />
            <span className="sg-line" />
            <span className="sg-price" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function StorefrontGallery({
  activeThemeId,
  onSelect,
  locked = false,
  busy = false,
}: {
  activeThemeId?: string
  onSelect?: (id: string) => void
  locked?: boolean
  busy?: boolean
}) {
  return (
    <section className="storefront-gallery">
      <header className="sg-header">
        <div className="sg-title">
          <Store size={18} />
          <h2>قالب‌های آماده‌ی فروشگاه</h2>
        </div>
        <p className="sg-sub">
          قالب را زنده ببینید، انتخاب کنید و با یک کلیک بسته‌ی سایتِ خود را بسازید. کالاها، قیمت و موجودی مستقیم از همین
          برنامه‌ی حسابداری خوانده می‌شوند و پرداختِ فروش به حسابِ خودتان می‌نشیند.
        </p>
      </header>

      <div className="sg-cards">
        {THEMES.map((t) => {
          const active = activeThemeId === t.id
          return (
            <article className={`sg-item${active ? ' active' : ''}`} key={t.id}>
              <ThemePreview accent={t.accent} accent2={t.accent2} />
              <div className="sg-body">
                <div className="sg-name-row">
                  <h3>{t.name}</h3>
                  {active && (
                    <span className="sg-active-tag">
                      <Check size={13} /> فعال
                    </span>
                  )}
                </div>
                <p className="sg-tagline">{t.tagline}</p>
                <ul className="sg-features">
                  {t.features.map((f) => (
                    <li key={f}>
                      <Check size={13} /> {f}
                    </li>
                  ))}
                </ul>
                <div className="sg-price-row">
                  <span className="sg-price-badge">شاملِ پلن‌های حرفه‌ای</span>
                </div>
                <div className="sg-actions">
                  <a className="btn-ghost" href={t.demoUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink size={14} /> پیش‌نمایشِ زنده
                  </a>
                  {locked ? (
                    <a className="btn-primary" href={PLANS_URL} target="_blank" rel="noopener noreferrer">
                      <Sparkles size={14} /> تهیه‌ی پلن و فعال‌سازی
                    </a>
                  ) : active ? (
                    <button type="button" className="btn-primary" disabled>
                      <Check size={14} /> قالبِ انتخاب‌شده
                    </button>
                  ) : (
                    <button type="button" className="btn-primary" onClick={() => onSelect?.(t.id)} disabled={busy}>
                      <Check size={14} /> انتخابِ این قالب
                    </button>
                  )}
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
