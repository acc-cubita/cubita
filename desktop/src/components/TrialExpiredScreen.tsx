import { Lock, Sparkles, LogOut } from 'lucide-react'
import { PLANS_URL } from '../api'

/**
 * صفحه‌ی قفلِ کاملِ پایانِ آزمایشی — جای کلِ اپ می‌نشیند وقتی دوره‌ی ۱۴روزه تمام شده.
 *
 * عمداً فقط یک راهِ رو به جلو دارد (خرید) و یک راهِ خروج (خروج از حساب). هشدارِ حذفِ
 * دیتا صریح است، چون همان چیزی است که کاربر را به تصمیم می‌رساند — و صادقانه بهش
 * می‌گوییم که با خرید، همین اطلاعات حفظ می‌شود.
 */
export function TrialExpiredScreen({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="trial-lock-shell">
      <div className="trial-lock-card">
        <div className="trial-lock-icon">
          <Lock size={30} />
        </div>
        <h1>دوره‌ی آزمایشیِ رایگان تمام شد</h1>
        <p>
          ۱۴ روزِ آزمایشیِ شما به پایان رسید. برای ادامه‌ی کار و <strong>حفظِ همه‌ی اطلاعاتی که وارد کرده‌اید</strong>،
          یک پلن تهیه کنید — حسابتان دقیقاً با همین داده‌ها فعال می‌شود.
        </p>
        <p className="trial-lock-warn">
          توجه: اگر پلن تهیه نکنید، اطلاعاتِ این حساب پس از مدتِ کوتاهی برای همیشه حذف می‌شود.
        </p>
        <a className="btn-primary trial-lock-cta" href={PLANS_URL} target="_blank" rel="noopener noreferrer">
          <Sparkles size={16} /> مشاهده پلن‌ها و خرید
        </a>
        <button type="button" className="link-button trial-lock-logout" onClick={onLogout}>
          <LogOut size={14} /> خروج از حساب
        </button>
      </div>
    </div>
  )
}
