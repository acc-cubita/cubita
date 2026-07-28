import { Sparkles, ChevronLeft } from 'lucide-react'

/** نوارِ اعلانِ بالای صفحه (مثلِ رقبا) — به دموی زنده لینک می‌دهد. با گرادیانِ برند. */
export function PromoBar() {
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'
  return (
    <a href={demoUrl} target="_blank" rel="noreferrer" className="promo-bar">
      <Sparkles size={15} className="promo-spark" />
      <span>دموی زنده‌ی یک فروشگاهِ واقعی آماده است — بدون ثبت‌نام همین حالا امتحان کنید</span>
      <ChevronLeft size={16} className="promo-arrow" />
    </a>
  )
}
