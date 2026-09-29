import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, RefreshCw, Server } from 'lucide-react'
import { checkServerUpdate, fetchServerUpdateStatus, type ServerUpdateStatus } from '../api'
import { SectionCard } from './SectionCard'
import { toFaDigits } from '../lib/jalali'
import { connectionError } from '../lib/serverConnection'
import { useServerReconnect } from '../lib/useServerConnection'

/** برنامه روی خودِ سرور باز است؟ (نشانیِ سرور این رایانه است) */
function onServerMachine(): boolean {
  const url = window.cubitaConfig?.serverUrl
  if (!url) return false
  try {
    const host = new URL(url).hostname
    return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]'
  } catch {
    return false
  }
}

/**
 * «به‌روزرسانیِ سرور» — فقط مالک، فقط کوبیتا سازمانی.
 *
 * ترتیب عمدی است (ENTERPRISE_PLAN.md، M5): اول نسخه‌ی تازه روی سرور دانلود و امضایش سنجیده
 * می‌شود، بعد روی **خودِ سرور** نصب می‌شود (نصاب پیش از مهاجرت پشتیبان می‌گیرد)، و فقط بعد از
 * آن کلاینت‌ها از سرور آپدیت می‌گیرند — کلاینت هرگز از سرورش جلو نمی‌زند.
 */
export function ServerUpdateCard({ token }: { token: string }) {
  const [st, setSt] = useState<ServerUpdateStatus | null>(null)
  const [busy, setBusy] = useState<'check' | 'install' | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const local = onServerMachine()

  const load = useCallback(async () => {
    try {
      setSt(await fetchServerUpdateStatus(token))
      setLoadError(null)
    } catch (e) {
      setLoadError(connectionError(e, 'وضعیتِ به‌روزرسانی خوانده نشد.'))
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])
  useServerReconnect(() => { void load() })

  async function check() {
    setBusy('check')
    setMsg(null)
    try {
      const next = await checkServerUpdate(token)
      setSt(next)
      setMsg(
        next.latest_available
          ? { text: `نسخه‌ی ${toFaDigits(next.latest_available)} دانلود و امضایش سنجیده شد.`, kind: 'ok' }
          : { text: 'سرور به‌روز است.', kind: 'ok' },
      )
    } catch (e) {
      setMsg({ text: connectionError(e, 'بررسیِ نسخه‌ی تازه ناموفق بود.'), kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  async function install() {
    if (!st?.installer_path) return
    if (
      !window.confirm(
        'نصبِ نسخه‌ی تازه روی سرور چند دقیقه طول می‌کشد و در این مدت کلاینت‌ها به سرور وصل نمی‌شوند. ' +
          'پیش از ارتقا از دیتابیس پشتیبان گرفته می‌شود. ادامه می‌دهید؟',
      )
    ) {
      return
    }
    setBusy('install')
    setMsg(null)
    const err = (await window.cubita.runUpdateInstaller?.(st.installer_path)) ?? 'این نسخه‌ی برنامه نصاب را اجرا نمی‌کند.'
    setBusy(null)
    if (err) setMsg({ text: err, kind: 'err' })
    else setMsg({ text: 'نصاب باز شد؛ مراحلش را روی همین رایانه دنبال کنید.', kind: 'ok' })
  }

  return (
    <SectionCard
      icon={Server}
      title="به‌روزرسانیِ سرور"
      description="نسخه‌ی تازه اول روی سرور نصب می‌شود؛ بعد رایانه‌های کلاینت خودکار از سرور به‌روز می‌شوند."
      actions={
        <button type="button" className="btn-secondary" onClick={check} disabled={busy !== null}>
          <RefreshCw size={15} className={busy === 'check' ? 'spin' : ''} />
          {busy === 'check' ? 'در حال بررسی…' : 'بررسیِ نسخه‌ی تازه'}
        </button>
      }
    >
      {loadError && <section className="fy-note fy-note--err"><AlertTriangle size={16} /><div>{loadError}</div></section>}
      {msg && (
        <section className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{msg.text}</div>
        </section>
      )}
      {!st ? (
        <p className="muted">{loadError ? 'اطلاعات پس از برقراری اتصال خودکار تازه می‌شود.' : 'در حال بارگذاری…'}</p>
      ) : (
        <dl className="lic-facts">
          <dt>نسخه‌ی سرور</dt>
          <dd dir="ltr">{toFaDigits(st.running)}</dd>
          <dt>آپدیتِ کلاینت‌ها</dt>
          <dd>
            {st.serving_clients ? (
              <span className="lic-pill lic-pill--ok">کلاینت‌ها از همین سرور به‌روز می‌شوند</span>
            ) : (
              <span className="lic-pill lic-pill--warn">نصابِ این نسخه روی سرور نیست</span>
            )}
          </dd>
          <dt>نسخه‌ی تازه</dt>
          <dd>
            {st.latest_available ? (
              <span dir="ltr">{toFaDigits(st.latest_available)}</span>
            ) : (
              '—'
            )}
          </dd>
        </dl>
      )}
      {st?.latest_available &&
        (local ? (
          <button type="button" className="btn-primary server-update-install" onClick={install} disabled={busy !== null}>
            <Download size={15} />
            {busy === 'install' ? 'در حال باز کردنِ نصاب…' : `نصبِ نسخه‌ی ${toFaDigits(st.latest_available)} روی این سرور`}
          </button>
        ) : (
          <p className="muted lic-footnote">برای نصب، برنامه را روی خودِ رایانه‌ی سرور باز کنید و همین دکمه را بزنید.</p>
        ))}
      {st && !st.serving_clients && (
        <p className="muted lic-footnote">
          «بررسیِ نسخه‌ی تازه» نصابِ همین نسخه را هم برای کلاینت‌ها می‌گیرد. سرورِ بدونِ اینترنت: رایانه‌های
          کلاینت را با همان نصابی که روی سرور اجرا کردید دستی به‌روز کنید.
        </p>
      )}
    </SectionCard>
  )
}
