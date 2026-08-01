import { Clock, Sparkles } from 'lucide-react'
import { PLANS_URL, type MeResponse } from '../api'

/**
 * نوارِ بالای اپ برای حسابِ آزمایشیِ فعال — «X روز مانده، برای حفظِ اطلاعات پلن بخر».
 *
 * وقتی به انقضا نزدیک می‌شود (طبقِ reminder threshold) لحنِ نوار فوری‌تر می‌شود، چون
 * پیامِ اصلیِ محصول همین‌جاست: اگر نخری، دیتایی که وارد کرده‌ای از دست می‌رود.
 *
 * فقط برای آزمایشیِ فعال رندر می‌شود؛ آزمایشیِ منقضی صفحه‌ی قفلِ کامل را می‌بیند نه نوار را.
 */
const URGENT_AT_DAYS = 3

export function TrialBanner({ me }: { me: MeResponse }) {
  if (!me.is_trial || me.trial_expired) return null

  const days = me.trial_days_left ?? 0
  const urgent = days <= URGENT_AT_DAYS

  return (
    <div className={`trial-banner ${urgent ? 'trial-banner--urgent' : ''}`} role="status">
      <span className="trial-banner__text">
        <Clock size={15} />
        {days > 0 ? (
          <>
            <strong>{toFa(days)} روز</strong> از نسخه‌ی آزمایشیِ رایگان باقی مانده —
            {urgent ? ' برای اینکه اطلاعاتتان حذف نشود همین حالا پلن تهیه کنید.' : ' برای حفظِ اطلاعات، پلن تهیه کنید.'}
          </>
        ) : (
          <>امروز آخرین روزِ نسخه‌ی آزمایشیِ رایگان است — برای حفظِ اطلاعات پلن تهیه کنید.</>
        )}
      </span>
      <a className="trial-banner__cta" href={PLANS_URL} target="_blank" rel="noopener noreferrer">
        <Sparkles size={14} /> ارتقا به پلن کامل
      </a>
    </div>
  )
}

function toFa(n: number): string {
  return n.toLocaleString('fa-IR')
}
