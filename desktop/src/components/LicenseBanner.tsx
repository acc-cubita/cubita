import { AlertTriangle, BadgeCheck } from 'lucide-react'
import type { LicenseInfo } from '../api'
import { licenseNeedsAttention, licenseTone } from '../lib/license'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * نوارِ مجوزِ کوبیتا سازمانی — جایِ نوارِ آزمایشی/اشتراکِ ابری.
 *
 * فقط وقتی دیده می‌شود که کاری از کاربر برمی‌آید (آزمایشی، نزدیکِ انقضا، ثبتِ بسته). دکمه
 * به صفحه‌ی «مجوز نرم‌افزار» می‌برد، نه یک پنجره‌ی جدا — یک جا برای یک داده.
 */
export function LicenseBanner({ license, onOpen }: { license: LicenseInfo; onOpen: () => void }) {
  if (!licenseNeedsAttention(license)) return null
  const tone = licenseTone(license)

  const text =
    license.message ??
    (license.mode === 'trial'
      ? `نسخه‌ی آزمایشیِ کوبیتا سازمانی — ${fa(license.days_left ?? 0)} روز مانده.`
      : `مجوزِ کوبیتا سازمانی ${fa(license.days_left ?? 0)} روزِ دیگر منقضی می‌شود.`)

  return (
    <div className={`license-banner license-banner--${tone}`} role={tone === 'err' ? 'alert' : 'status'}>
      {tone === 'err' ? <AlertTriangle size={16} /> : <BadgeCheck size={16} />}
      <span className="license-banner__text">{text}</span>
      <button type="button" className="license-banner__cta" onClick={onOpen}>
        {license.mode === 'trial' || license.mode === 'trial_expired' ? 'فعال‌سازی' : 'مجوز نرم‌افزار'}
      </button>
    </div>
  )
}
