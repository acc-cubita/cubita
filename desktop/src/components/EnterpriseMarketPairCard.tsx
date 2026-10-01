import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Cloud, Link2, RotateCw } from 'lucide-react'
import {
  claimEnterpriseMarketPair, completeEnterpriseMarketPair, fetchEnterpriseMarketState,
  fetchMe, startEnterpriseMarketPair, type EnterpriseMarketState, type MeResponse,
} from '../api'
import { SectionCard } from './SectionCard'
import { formatJalali } from '../lib/jalali'

export function EnterpriseMarketPairCard({ token, onMeUpdated }: {
  token: string
  onMeUpdated: (me: MeResponse) => void
}) {
  const [state, setState] = useState<EnterpriseMarketState | null>(null)
  const [code, setCode] = useState('')
  const [expires, setExpires] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try { setState(await fetchEnterpriseMarketState(token)); setError('') }
    catch (e) { setError(e instanceof Error ? e.message : 'وضعیت بازار خوانده نشد.') }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  async function start() {
    setBusy(true); setError('')
    try {
      const result = await startEnterpriseMarketPair(token)
      setCode(result.pair_code)
      setExpires(result.expires_at)
      await refresh()
    } catch (e) { setError(e instanceof Error ? e.message : 'کد پیوند ساخته نشد.') }
    finally { setBusy(false) }
  }

  async function complete() {
    setBusy(true); setError('')
    try {
      const result = await completeEnterpriseMarketPair(token)
      await refresh()
      if (result.status === 'active') onMeUpdated(await fetchMe(token))
      else setError('مالک حساب ابری هنوز این کد را تأیید نکرده است.')
    } catch (e) { setError(e instanceof Error ? e.message : 'پیوند کامل نشد.') }
    finally { setBusy(false) }
  }

  return <SectionCard icon={Link2} title="پیوند بازار خرید و پخش من" description="فقط اطلاعات لازم برای معامله به بازار ابری می‌رود؛ دفتر حسابداری و انبار روی همین سرور می‌ماند.">
    {error && <p className="error" role="alert">{error}</p>}
    {state?.status === 'active' ? <>
      <p className="fy-note fy-note--ok"><CheckCircle2 size={16} /> حساب بازار به این سرور پیوند دارد.</p>
      <p className="muted">آخرین همگام‌سازی: {state.last_sync_at ? formatJalali(state.last_sync_at) : 'هنوز انجام نشده'}</p>
      {state.last_error_code && <p className="error">همگام‌سازی نیازمند بررسی است: {state.last_error_code}</p>}
      {!state.catalog_approved && <p className="muted">کاتالوگ قدیمی تا تأیید نگاشت کالاها منتشر نمی‌شود.</p>}
    </> : <>
      <p className="muted">در هر دو حساب باید مالک تأیید کند: ابتدا اینجا کد بسازید، سپس مالک حساب ابری آن را در «پروفایل من» وارد کند.</p>
      {code && <p><strong>کد پیوند:</strong> <code dir="ltr">{code}</code>{expires && <span className="muted"> — اعتبار تا {formatJalali(expires)}</span>}</p>}
      <div className="check-actions">
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void start()}><Link2 size={14} /> {state?.status === 'pending' ? 'ساخت کد تازه' : 'ساخت کد پیوند'}</button>
        {state?.status === 'pending' && <button type="button" className="btn-secondary" disabled={busy} onClick={() => void complete()}><RotateCw size={14} /> بررسی تأیید حساب ابری</button>}
      </div>
    </>}
  </SectionCard>
}

export function EnterpriseMarketClaimCard({ token }: { token: string }) {
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function claim() {
    setBusy(true); setError(''); setMessage('')
    try {
      await claimEnterpriseMarketPair(token, code.trim().toUpperCase())
      setCode('')
      setMessage('این حساب به نصب سازمانی پیوند خورد. برای دریافت تأیید، روی سرور «بررسی تأیید» را بزنید.')
    } catch (e) { setError(e instanceof Error ? e.message : 'پیوند تأیید نشد.') }
    finally { setBusy(false) }
  }

  return <SectionCard icon={Cloud} title="پیوند حساب ابری به کوبیتا سازمانی" description="فقط مالک حساب ابری می‌تواند کد کوتاهِ ساخته‌شده روی سرور سازمانی را تأیید کند.">
    <p className="muted">پس از پیوند، معامله‌های تازه از پنل سازمانی انجام می‌شوند. سفارش یا مرجوعی ناتمام باید ابتدا تعیین تکلیف شود؛ سوابق قبلی به سرور منتقل نمی‌شوند.</p>
    <input dir="ltr" value={code} onChange={e => setCode(e.target.value)} maxLength={16} aria-label="کد پیوند بازار سازمانی" placeholder="کد ۱۲ نویسه‌ای" />
    <button type="button" className="btn-primary" disabled={busy || code.replace(/[-\s]/g, '').length !== 12} onClick={() => void claim()}><Link2 size={14} /> تأیید پیوند</button>
    {error && <p className="error" role="alert">{error}</p>}
    {message && <p className="fy-note fy-note--ok">{message}</p>}
  </SectionCard>
}
