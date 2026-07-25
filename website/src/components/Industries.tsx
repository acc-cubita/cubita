import { Coffee, Gem, ShoppingCart, Shirt, Smartphone, Sofa, Store, Truck, Wrench } from 'lucide-react'

const INDUSTRIES = [
  { icon: Store, label: 'فروشگاه و سوپرمارکت' },
  { icon: Shirt, label: 'پوشاک و بوتیک' },
  { icon: Smartphone, label: 'موبایل و لوازم دیجیتال' },
  { icon: Truck, label: 'پخش و بنکداری' },
  { icon: Sofa, label: 'لوازم خانگی و دکوراسیون' },
  { icon: Gem, label: 'طلا و جواهر' },
  { icon: Coffee, label: 'کافه و رستوران' },
  { icon: Wrench, label: 'خدمات و پیمانکاری' },
  { icon: ShoppingCart, label: 'فروشگاه اینترنتی' },
]

export function Industries() {
  return (
    <section id="industries">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">مناسبِ کسب‌وکارِ شما</span>
          <h2>از یک مغازه تا یک شرکت پخش</h2>
          <p>کوبیتا با نیاز کسب‌وکارهای مختلف جور می‌شود؛ کافی است رشته‌ی کارتان را پیدا کنید.</p>
        </div>
        <div className="industries-grid">
          {INDUSTRIES.map((it) => (
            <div className="industry-tile" key={it.label}>
              <span className="industry-icon">
                <it.icon size={19} />
              </span>
              <span className="industry-label">{it.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
