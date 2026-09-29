import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, DatabaseBackup, FileArchive, RefreshCw } from 'lucide-react'
import {
  downloadDiagnostics,
  fetchServerBackupStatus,
  runServerBackup,
  type ServerBackupStatus,
} from '../api'
import { SectionCard } from './SectionCard'
import { backupAge } from '../lib/backupAge'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { connectionError } from '../lib/serverConnection'
import { useServerReconnect } from '../lib/useServerConnection'

function formatSize(bytes: number): string {
  const mb = bytes / 1024 / 1024
  return mb >= 1024 ? `${(mb / 1024).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} گیگابایت`
    : `${mb.toLocaleString('fa-IR', { maximumFractionDigits: 1 })} مگابایت`
}

/**
 * «پشتیبان و عیب‌یابیِ سرور» — فقط مالک، فقط کوبیتا سازمانی (ENTERPRISE_PLAN.md، M6).
 *
 * سرور هر ۲۴ ساعت خودش پشتیبان می‌گیرد؛ این کارت نشان می‌دهد آخرینش کِی بوده، دلیلِ شکست
 * را اگر شکست خورده، و دو دکمه: پشتیبانِ همین حالا، و زیپِ عیب‌یابی برای پشتیبانی.
 */
export function ServerBackupCard({ token }: { token: string }) {
  const [st, setSt] = useState<ServerBackupStatus | null>(null)
  const [busy, setBusy] = useState<'backup' | 'diag' | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setSt(await fetchServerBackupStatus(token))
      setLoadError(null)
    } catch (e) {
      setLoadError(connectionError(e, 'وضعیتِ پشتیبان خوانده نشد.'))
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])
  useServerReconnect(() => { void load() })

  async function backupNow() {
    setBusy('backup')
    setMsg(null)
    try {
      setSt(await runServerBackup(token))
      setMsg({ text: 'پشتیبانِ کامل روی سرور ساخته شد.', kind: 'ok' })
    } catch (e) {
      setMsg({ text: connectionError(e, 'پشتیبان‌گیری ناموفق بود.'), kind: 'err' })
      void load()
    } finally {
      setBusy(null)
    }
  }

  async function diagnostics() {
    setBusy('diag')
    setMsg(null)
    try {
      const { filename, blob } = await downloadDiagnostics(token)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      setMsg({ text: 'زیپِ عیب‌یابی ذخیره شد؛ همان فایل را برای پشتیبانیِ کوبیتا بفرستید.', kind: 'ok' })
    } catch (e) {
      setMsg({ text: connectionError(e, 'ساختِ زیپِ عیب‌یابی ناموفق بود.'), kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  const tone = !st ? null : st.last_error ? 'err' : st.stale ? 'warn' : 'ok'

  return (
    <SectionCard
      icon={DatabaseBackup}
      title="پشتیبان و عیب‌یابیِ سرور"
      description="سرور هر ۲۴ ساعت خودش یک پشتیبانِ کامل می‌گیرد و ۱۴ تای آخر را نگه می‌دارد."
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
          <dt>آخرین پشتیبان</dt>
          <dd>
            <span className={`lic-pill lic-pill--${tone}`}>{backupAge(st.age_hours)}</span>
            {st.last_at && <span className="muted"> — {formatJalali(st.last_at)}</span>}
          </dd>
          {st.last_error && (
            <>
              <dt>خطای آخرین تلاش</dt>
              <dd className="lic-mono">{st.last_error}</dd>
            </>
          )}
          <dt>نسخه‌های نگه‌داشته</dt>
          <dd>
            {toFaDigits(st.count)} پشتیبان{st.count > 0 && ` — ${formatSize(st.total_bytes)}`}
          </dd>
          <dt>پوشه روی سرور</dt>
          <dd dir="ltr" className="lic-mono">
            {st.folder}
          </dd>
        </dl>
      )}
      {st && !st.automatic && (
        <p className="muted lic-footnote">این سرور با نصابِ کوبیتا سازمانی نصب نشده و پشتیبانِ خودکار ندارد.</p>
      )}
      <div className="srv-backup-actions">
        <button
          type="button"
          className="btn-primary"
          onClick={() => void backupNow()}
          disabled={busy !== null || !st?.automatic}
        >
          <RefreshCw size={15} className={busy === 'backup' ? 'spin' : ''} />
          {busy === 'backup' ? 'در حال پشتیبان‌گیری…' : 'پشتیبانِ همین حالا'}
        </button>
        <button type="button" className="btn-secondary" onClick={() => void diagnostics()} disabled={busy !== null}>
          <FileArchive size={15} />
          {busy === 'diag' ? 'در حال ساخت…' : 'دریافتِ زیپِ عیب‌یابی'}
        </button>
      </div>
      <p className="muted lic-footnote">
        این پشتیبان‌ها روی دیسکِ خودِ سرورند و از خرابیِ آن دیسک نجات نمی‌دهند. هر چند وقت یک‌بار از
        «پشتیبان‌گیری خودکار» (در تنظیمات) یک نسخه روی رایانه‌ی دیگر یا فلش نگه دارید. زیپِ عیب‌یابی رمز و کلیدی ندارد.
      </p>
    </SectionCard>
  )
}
