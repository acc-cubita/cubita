import { useEffect, useRef, useState } from 'react'
import { DatabaseBackup, Download, FolderOpen, HardDriveDownload, Upload } from 'lucide-react'
import { SectionCard } from './SectionCard'
import { fetchBackupExport, importBackup } from '../api'
import { isElectron } from '../platform'
import type { LocalBackup } from '../electron.d'

/**
 * پشتیبان‌گیری و بازیابیِ کاملِ داده‌ی کسب‌وکار — فقط برای مالک.
 *
 * دسکتاپ: علاوه بر ذخیره روی کامپیوتر، پس از هر همگام‌سازی یک نسخه‌ی خودکار در
 * پوشه‌ی محلی می‌ماند (این کارت آن‌ها را فهرست می‌کند). وب: دانلودِ فایلِ پشتیبان و
 * بازیابی با انتخابِ فایل. بازیابی داده‌ی فعلی را *جایگزین* می‌کند، پس با تأییدِ صریح.
 */
export function BackupCard({ token }: { token: string }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const [locals, setLocals] = useState<LocalBackup[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  const refreshLocals = () => {
    if (isElectron) void window.cubita.backupListLocal().then(setLocals).catch(() => {})
  }
  useEffect(refreshLocals, [])

  const fmtSize = (n: number) => (n < 1024 * 1024 ? `${Math.round(n / 1024).toLocaleString('fa-IR')} کیلوبایت` : `${(n / 1048576).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} مگابایت`)
  const fmtTime = (ms: number) => new Date(ms).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })

  // ── ذخیره‌ی نسخه‌ی پشتیبان ─────────────────────────────────────────────────
  async function handleSave() {
    setMsg(null)
    setBusy('save')
    try {
      if (isElectron) {
        const r = await window.cubita.backupSaveToFile()
        if (r.saved) setMsg({ text: `نسخه‌ی پشتیبان ذخیره شد:\n${r.path}`, kind: 'ok' })
        refreshLocals()
      } else {
        // وب: دانلودِ فایل در مرورگر
        const data = await fetchBackupExport(token)
        const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
        a.href = url
        a.download = `cubita-backup-${ts}.json`
        a.click()
        URL.revokeObjectURL(url)
        setMsg({ text: 'فایلِ پشتیبان دانلود شد.', kind: 'ok' })
      }
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطا در پشتیبان‌گیری', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  // ── بازیابی ───────────────────────────────────────────────────────────────
  const CONFIRM =
    'هشدار: بازیابی همه‌ی داده‌ی فعلیِ این کسب‌وکار را پاک می‌کند و نسخه‌ی داخلِ فایلِ پشتیبان را جایگزین می‌کند. این کار برگشت‌ناپذیر است.\n\nمطمئن هستید؟'

  async function handleRestoreDesktop() {
    if (!window.confirm(CONFIRM)) return
    setMsg(null)
    setBusy('restore')
    try {
      const r = await window.cubita.backupRestoreFromFile()
      if (r.canceled) return
      setMsg({ text: r.message, kind: r.restored ? 'ok' : 'err' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطا در بازیابی', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  async function handleRestoreWeb(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = '' // تا انتخابِ همان فایل بارِ بعد هم رویداد بدهد
    if (!file) return
    if (!window.confirm(CONFIRM)) return
    setMsg(null)
    setBusy('restore')
    try {
      const data = JSON.parse(await file.text())
      const out = await importBackup(token, data)
      setMsg({ text: `بازیابی کامل شد — ${(out.total_rows ?? 0).toLocaleString('fa-IR')} ردیف بازگردانده شد.`, kind: 'ok' })
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'فایلِ پشتیبان معتبر نیست.', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  return (
    <SectionCard
      icon={DatabaseBackup}
      title="پشتیبان‌گیری و بازیابی"
      description={
        isElectron
          ? 'یک نسخه از داده‌های شما به‌صورت خودکار روی همین کامپیوتر ذخیره می‌شود. می‌توانید هر زمان یک نسخه‌ی پشتیبان روی درایو/حافظه‌ی خود بگیرید یا از یک فایلِ پشتیبان بازیابی کنید.'
          : 'یک فایلِ پشتیبان از کلِ داده‌های کسب‌وکار دانلود کنید و در جای امنی نگه دارید، یا از یک فایلِ پشتیبان بازیابی کنید.'
      }
    >
      <div className="backup-actions">
        <button type="button" className="btn-primary" onClick={handleSave} disabled={busy !== null}>
          {isElectron ? <HardDriveDownload size={15} /> : <Download size={15} />}
          {busy === 'save' ? 'در حال آماده‌سازی…' : isElectron ? 'ذخیره‌ی پشتیبان روی کامپیوتر' : 'دانلودِ فایلِ پشتیبان'}
        </button>

        {isElectron && (
          <button type="button" className="btn-ghost" onClick={() => void window.cubita.backupOpenFolder()} disabled={busy !== null}>
            <FolderOpen size={15} /> پوشه‌ی پشتیبان‌ها
          </button>
        )}

        {isElectron ? (
          <button type="button" className="btn-ghost btn-danger-ghost" onClick={handleRestoreDesktop} disabled={busy !== null}>
            <Upload size={15} /> {busy === 'restore' ? 'در حال بازیابی…' : 'بازیابی از فایل'}
          </button>
        ) : (
          <>
            <button type="button" className="btn-ghost btn-danger-ghost" onClick={() => fileRef.current?.click()} disabled={busy !== null}>
              <Upload size={15} /> {busy === 'restore' ? 'در حال بازیابی…' : 'بازیابی از فایل'}
            </button>
            <input ref={fileRef} type="file" accept="application/json,.json" onChange={handleRestoreWeb} hidden />
          </>
        )}
      </div>

      {msg && <div className={`backup-msg ${msg.kind}`}>{msg.text}</div>}

      {isElectron && locals.length > 0 && (
        <div className="backup-locals">
          <div className="backup-locals-head">نسخه‌های محلیِ اخیر ({locals.length.toLocaleString('fa-IR')})</div>
          <ul>
            {locals.slice(0, 5).map((b) => (
              <li key={b.file}>
                <span className="backup-local-time">{fmtTime(b.mtime)}</span>
                <span className="backup-local-size">{fmtSize(b.size)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionCard>
  )
}
