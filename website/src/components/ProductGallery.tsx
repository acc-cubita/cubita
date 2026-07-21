const SHOTS = [
  {
    file: 'sales',
    alt: 'صفحه‌ی ثبت فاکتور فروش با فهرست فاکتورهای قبلی و وضعیت هرکدام',
    title: 'ثبت فاکتور در چند ثانیه',
    desc: 'کالا، تعداد و قیمت را وارد کنید؛ سند حسابداری و کسر انبار خودکار انجام می‌شود.',
  },
  {
    file: 'accounting',
    alt: 'صفحه‌ی حسابداری با فرم ثبت سند دستی و چارت حساب‌های درختی',
    title: 'دفاتر حسابداری واقعی',
    desc: 'سند دستی، چارت حساب کامل، و هر رویداد مالی با ردی که تا ریشه‌اش قابل پیگیری است.',
  },
  {
    file: 'dashboard',
    alt: 'داشبورد کوبیتا با خلاصه‌ی فروش، موجودی انبار، سود دوره و مانده‌ی نقد و بانک',
    title: 'وضعیت مالی، یک نگاه',
    desc: 'فروش امروز، ارزش انبار، سود دوره و مانده‌ی نقد و بانک — همه در یک داشبورد زنده.',
  },
]

export function ProductGallery() {
  return (
    <section id="screenshots">
      <div className="container">
        <div className="section-head">
          <span className="eyebrow">محصول واقعی</span>
          <h2>این شبیه‌سازی نیست — خودِ نرم‌افزار است</h2>
          <p>هر تصویر مستقیم از نسخه‌ی دموی زنده گرفته شده، نه طراحی گرافیکی.</p>
        </div>
        <div className="gallery-grid">
          {SHOTS.map((s) => (
            <figure className="gallery-item" key={s.file}>
              <picture>
                <source srcSet={`/screenshots/${s.file}.webp`} type="image/webp" />
                <img
                  src={`/screenshots/${s.file}.png`}
                  alt={s.alt}
                  loading="lazy"
                  width={1600}
                  height={1000}
                />
              </picture>
              <figcaption>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  )
}
