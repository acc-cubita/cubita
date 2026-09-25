import { useEffect, useState } from 'react'
import { DatabaseBackup } from 'lucide-react'
import { fetchServerBackupStatus, type ServerBackupStatus } from '../api'
import { backupAge } from '../lib/backupAge'

/** دوباره‌پرسیدن هر ۳۰ دقیقه — کهنگی کُند عوض می‌شود و این برنامه روزها باز می‌ماند. */
const POLL_MS = 30 * 60 * 1000

/**
 * نوارِ قرمزِ «پشتیبانِ سرور کهنه است» — فقط مالکِ کوبیتا سازمانی.
 *
 * روی ابر پشتیبان کارِ ماست؛ روی سرورِ شرکت، اگر زمان‌بند شکست بخورد (دیسکِ پر، سرویسِ
 * متوقف) هیچ‌کس جز مالک نمی‌فهمد، و آن هم فقط اگر جلوی چشمش باشد. پس به‌جای یک خط در
 * صفحه‌ای که کسی باز نمی‌کند، نوار روی همه‌ی صفحه‌هاست تا وقتی درست شود.
 */
export function ServerBackupBanner({ token, onOpen }: { token: string; onOpen: () => void }) {
  const [st, setSt] = useState<ServerBackupStatus | null>(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      fetchServerBackupStatus(token)
        .then((s) => alive && setSt(s))
        .catch(() => {})
    void load()
    const id = window.setInterval(load, POLL_MS)
    return () => {
      alive = false
      window.clearInterval(id)
    }
  }, [token])

  //: سرورِ بدونِ زمان‌بند (توسعه) نوار نمی‌گیرد؛ هشدارِ همیشگی که کاری از دستِ کاربر برنمی‌آید نویز است.
  if (!st || !st.automatic || !st.stale) return null
  const text = st.last_error
    ? `پشتیبانِ خودکارِ سرور شکست خورده است — آخرین پشتیبانِ سالم: ${backupAge(st.age_hours)}.`
    : st.age_hours == null
      ? 'سرور هنوز هیچ پشتیبانی نگرفته است.'
      : `آخرین پشتیبانِ سرور: ${backupAge(st.age_hours)}.`

  return (
    <div className="license-banner license-banner--err" role="alert">
      <DatabaseBackup size={16} />
      <span className="license-banner__text">{text}</span>
      <button type="button" className="license-banner__cta" onClick={onOpen}>
        بررسیِ پشتیبان
      </button>
    </div>
  )
}
