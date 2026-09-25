import { useState } from 'react'
import { Check, Copy, KeyRound } from 'lucide-react'
import { SectionCard } from './SectionCard'

/** کدی که مالکِ کوبیتا سازمانی به کارمند می‌دهد — سرورِ شرکت ایمیل ندارد. */
export interface IssuedCode {
  kind: 'invite' | 'reset'
  name: string
  code: string
  /** اعتبار به ساعت؛ دعوت ۷ روز است. */
  hours: number
}

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * نمایشِ یک‌باره‌ی کدِ دعوت/بازنشانی. سرور فقط hashِ کد را نگه می‌دارد؛ پس از بستنِ این
 * کارت، کد دیگر پیدا نمی‌شود و باید دوباره ساخته شود — همین را صریح می‌گوییم.
 *
 * مالک **رمز** نمی‌بیند، **کد** می‌بیند: کارمند با کد رمزِ خودش را می‌گذارد، و مالک
 * هیچ‌وقت رمزِ کسی را نمی‌داند.
 */
export function AccessCodeCard({ issued, onClose }: { issued: IssuedCode; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const invite = issued.kind === 'invite'
  const validity = issued.hours >= 48 ? `${fa(Math.round(issued.hours / 24))} روز` : `${fa(issued.hours)} ساعت`

  async function copy() {
    try {
      await navigator.clipboard.writeText(issued.code)
      setCopied(true)
    } catch {
      // کلیپ‌بورد در دسترس نبود؛ کد روی صفحه هست و دستی هم خوانده می‌شود.
    }
  }

  return (
    <SectionCard
      icon={KeyRound}
      title={invite ? `کدِ دعوتِ ${issued.name}` : `کدِ بازنشانیِ رمزِ ${issued.name}`}
      description="این کد را حضوری یا با پیام‌رسانِ داخلی به خودِ او بدهید. کد فقط همین یک بار نشان داده می‌شود."
      actions={
        <button type="button" onClick={onClose}>
          بستن
        </button>
      }
    >
      <section className="access-code">
        <div className="access-code__value" dir="ltr">
          {issued.code}
        </div>
        <button type="button" className="btn-primary" onClick={() => void copy()}>
          {copied ? <Check size={15} /> : <Copy size={15} />}
          {copied ? 'کپی شد' : 'کپیِ کد'}
        </button>
      </section>
      <ol className="access-code__steps">
        <li>در برنامه‌ی کوبیتا روی رایانه‌ی خودش، صفحه‌ی ورود ← «کدِ دعوت یا بازنشانی دارم».</li>
        <li>کد را وارد کند و {invite ? 'رمزِ عبورِ خودش را بسازد' : 'رمزِ تازه‌اش را بگذارد'}.</li>
        <li>
          کد {validity} و فقط یک‌بار اعتبار دارد؛ اگر گم شد، {invite ? '«ارسالِ دوباره»' : 'کدِ تازه'} بسازید.
        </li>
      </ol>
    </SectionCard>
  )
}
