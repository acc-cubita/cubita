import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  DatabaseBackup,
  Download,
  FolderOpen,
  HardDriveDownload,
  RotateCcw,
  Save,
  ShieldCheck,
  Trash2,
  Upload,
} from 'lucide-react'
import { fetchBackupExport, importBackup, type MeResponse } from '../api'
import { isElectron } from '../platform'
import type { BackupSettings, BackupStatus, LocalBackup } from '../electron.d'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'

/**
 * تنظیماتِ تهیه‌ی پشتیبانِ خودکار.
 *
 * پیش‌تر این کار یک کارتِ کوچک در «پروفایل من» بود که فقط دکمه داشت: پشتیبانِ خودکار
 * وجود داشت ولی **هیچ تنظیمی نداشت** — نه روشن/خاموش، نه فاصله‌ی زمانی، نه تعدادِ
 * نسخه‌های نگه‌داشته‌شده، نه انتخابِ پوشه — و فقط پس از همگام‌سازی اجرا می‌شد.
 *
 * حالا همه‌ی آن تصمیم‌ها این‌جاست و یک زمان‌بندِ ساعتی در پروسه‌ی اصلی هم اجرایشان
 * می‌کند. نسخه‌ها هم دیگر فقط فهرست نمی‌شوند: از داخلِ همین صفحه قابلِ بازیابی و
 * حذف‌اند.
 *
 * نسخه‌ی وب پوشه‌ی محلی ندارد، پس آن‌جا صریح گفته می‌شود که خودکارسازی مالِ دسکتاپ
 * است و فقط پشتیبانِ دستی در دسترس می‌ماند — به‌جای نشان‌دادنِ تنظیماتی که کار نمی‌کند.
 */

const HOUR_OPTIONS = [
  { value: 0, label: 'پس از هر همگام‌سازی' },
  { value: 6, label: 'هر ۶ ساعت' },
  { value: 12, label: 'هر ۱۲ ساعت' },
  { value: 24, label: 'روزی یک بار' },
  { value: 72, label: 'هر ۳ روز' },
  { value: 168, label: 'هفته‌ای یک بار' },
]

const fmtSize = (n: number) =>
  n < 1024 * 1024
    ? `${Math.round(n / 1024).toLocaleString('fa-IR')} کیلوبایت`
    : `${(n / 1048576).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} مگابایت`

const fmtTime = (ms: number) =>
  new Date(ms).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })

/** «۳ ساعت دیگر» / «۲ روز پیش» — برای وضعیت، نه برای جدول. */
function relative(ms: number): string {
  const diff = ms - Date.now()
  const abs = Math.abs(diff)
  const unit = abs < 3_600_000 ? 'دقیقه' : abs < 86_400_000 ? 'ساعت' : 'روز'
  const div = unit === 'دقیقه' ? 60_000 : unit === 'ساعت' ? 3_600_000 : 86_400_000
  const n = Math.max(1, Math.round(abs / div)).toLocaleString('fa-IR')
  return diff >= 0 ? `${n} ${unit} دیگر` : `${n} ${unit} پیش`
}

const RESTORE_WARNING =
  'هشدار: بازیابی همه‌ی داده‌ی فعلیِ این کسب‌وکار را پاک می‌کند و نسخه‌ی داخلِ فایلِ پشتیبان را جایگزین می‌کند. این کار برگشت‌ناپذیر است.\n\nمطمئن هستید؟'

export function BackupPage({ token, me }: { token: string; me: MeResponse }) {
  const isOwner = Boolean(me.permissions['*'])
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [locals, setLocals] = useState<LocalBackup[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)

  const refresh = useCallback(async () => {
    if (!isElectron) return
    try {
      const [st, list] = await Promise.all([
        window.cubita.backupStatus(),
        window.cubita.backupListLocal(),
      ])
      setStatus(st)
      setLocals(list)
    } catch {
      // خواندنِ وضعیت نباید صفحه را از کار بیندازد؛ کارت‌های عملیات همچنان کار می‌کنند.
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function patch(next: Partial<BackupSettings>) {
    await window.cubita.backupSetSettings(next)
    await refresh()
  }

  /** هر عملیاتِ سنگین را با قفلِ دکمه و پیامِ یکسان اجرا می‌کند. */
  async function run(key: string, action: () => Promise<{ text: string; kind: 'ok' | 'err' } | null>) {
    setBusy(key)
    setMsg(null)
    try {
      setMsg(await action())
    } catch (err) {
      setMsg({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(null)
      await refresh()
    }
  }

  function handleBackupNow() {
    void run('now', async () => {
      if (isElectron) {
        const b = await window.cubita.backupNow()
        return { text: `نسخه‌ی تازه ساخته شد — ${fmtSize(b.size)}`, kind: 'ok' as const }
      }
      const data = await fetchBackupExport(token)
      const blob = new Blob([JSON.stringify(data)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `cubita-backup-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.json`
      a.click()
      URL.revokeObjectURL(url)
      return { text: 'فایلِ پشتیبان دانلود شد.', kind: 'ok' as const }
    })
  }

  function handleSaveAs() {
    void run('saveAs', async () => {
      const r = await window.cubita.backupSaveToFile()
      return r.saved ? { text: `ذخیره شد: ${r.path}`, kind: 'ok' as const } : null
    })
  }

  function handleRestoreLocal(b: LocalBackup) {
    if (!window.confirm(`${fmtTime(b.mtime)}\n\n${RESTORE_WARNING}`)) return
    void run(`restore-${b.file}`, async () => {
      const r = await window.cubita.backupRestoreFromLocal(b.file)
      return { text: r.message, kind: r.restored ? 'ok' : 'err' }
    })
  }

  function handleDelete(b: LocalBackup) {
    if (!window.confirm(`نسخه‌ی ${fmtTime(b.mtime)} حذف شود؟`)) return
    void run(`del-${b.file}`, async () => {
      await window.cubita.backupDeleteLocal(b.file)
      return { text: 'نسخه حذف شد.', kind: 'ok' }
    })
  }

  function handleRestoreFile() {
    if (!window.confirm(RESTORE_WARNING)) return
    void run('restoreFile', async () => {
      const r = await window.cubita.backupRestoreFromFile()
      if (r.canceled) return null
      return { text: r.message, kind: r.restored ? 'ok' : 'err' }
    })
  }

  async function handleRestoreWeb(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!window.confirm(RESTORE_WARNING)) return
    void run('restoreFile', async () => {
      const data = JSON.parse(await file.text())
      const out = await importBackup(token, data)
      return {
        text: `بازیابی کامل شد — ${(out.total_rows ?? 0).toLocaleString('fa-IR')} ردیف بازگردانده شد.`,
        kind: 'ok',
      }
    })
  }

  if (!isOwner) {
    return (
      <div className="page panels">
        <PageHeader
          icon={DatabaseBackup}
          title="پشتیبان‌گیری خودکار"
          description="نسخه‌ی پشتیبانِ کاملِ داده‌ی کسب‌وکار و تنظیماتِ خودکارسازیِ آن."
        />
        <div className="fy-note fy-note--warn">
          <AlertTriangle size={16} />
          <div>
            <strong>این بخش فقط برای مالکِ کسب‌وکار است.</strong>
            <p>
              فایلِ پشتیبان کلِ داده‌ی مالیِ کسب‌وکار است و بازیابی همه‌چیز را جایگزین می‌کند، پس
              دستِ نقشِ مالک می‌ماند نه هر کاربری با دسترسیِ مشاهده.
            </p>
          </div>
        </div>
      </div>
    )
  }

  const s = status?.settings
  const auto = isElectron && s

  return (
    <div className="page panels">
      <PageHeader
        icon={DatabaseBackup}
        title="پشتیبان‌گیری خودکار"
        description="نسخه‌ی پشتیبانِ کاملِ داده‌ی کسب‌وکار: زمان‌بندی، تعدادِ نسخه‌ها، محلِ نگه‌داری، و بازیابی."
      />

      {msg && (
        <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div className="bk-msg">{msg.text}</div>
        </div>
      )}

      {!isElectron && (
        <div className="fy-note fy-note--warn">
          <AlertTriangle size={16} />
          <div>
            <strong>خودکارسازی فقط در نسخه‌ی دسکتاپ کار می‌کند.</strong>
            <p>
              مرورگر اجازه‌ی نوشتن روی دیسکِ شما را به برنامه نمی‌دهد، پس نسخه‌ی خودکار روی وب
              ممکن نیست. این‌جا می‌توانید هر زمان یک فایلِ پشتیبان دانلود کنید یا از فایل بازیابی
              کنید؛ برای پشتیبانِ خودکار، برنامه‌ی دسکتاپ را نصب کنید.
            </p>
          </div>
        </div>
      )}

      <div className="workspace-split">
        {auto ? (
          <SectionCard
            icon={Clock}
            title="زمان‌بندی و نگه‌داری"
            description="تنظیمات همین‌جا ذخیره می‌شود و پروسه‌ی برنامه هر ساعت بررسی می‌کند که نوبتِ نسخه‌ی تازه رسیده یا نه."
          >
            <div className="bk-settings">
              <label className="bk-switch">
                <input
                  type="checkbox"
                  checked={s.enabled}
                  onChange={(e) => void patch({ enabled: e.target.checked })}
                />
                <span>
                  <strong>پشتیبان‌گیریِ خودکار فعال باشد</strong>
                  <span className="bk-hint">
                    با خاموش‌کردن، فقط نسخه‌های دستی گرفته می‌شوند.
                  </span>
                </span>
              </label>

              <label>
                فاصله‌ی نسخه‌ها
                <select
                  value={s.everyHours}
                  disabled={!s.enabled}
                  onChange={(e) => void patch({ everyHours: Number(e.target.value) })}
                >
                  {HOUR_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                چند نسخه نگه داشته شود
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={s.keep}
                  onChange={(e) => void patch({ keep: Number(e.target.value) })}
                />
                <span className="bk-hint">کهنه‌ترین‌ها خودکار پاک می‌شوند تا این تعداد بماند.</span>
              </label>

              <div className="bk-dir">
                <span className="bk-dir-label">پوشه‌ی نگه‌داری</span>
                <code className="bk-dir-path" title={status.dir}>
                  {status.dir}
                </code>
                <div className="bk-dir-actions">
                  <button
                    type="button"
                    onClick={() =>
                      void run('dir', async () => {
                        const r = await window.cubita.backupChooseDir()
                        return r.dir ? { text: `پوشه به ${r.dir} تغییر کرد.`, kind: 'ok' } : null
                      })
                    }
                    disabled={busy !== null}
                  >
                    <FolderOpen size={13} /> تغییرِ پوشه
                  </button>
                  {s.dir !== '' && (
                    <button
                      type="button"
                      onClick={() =>
                        void run('dirReset', async () => {
                          await window.cubita.backupResetDir()
                          return { text: 'به پوشه‌ی پیش‌فرض برگشت.', kind: 'ok' }
                        })
                      }
                      disabled={busy !== null}
                    >
                      <RotateCcw size={13} /> پیش‌فرض
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void window.cubita.backupOpenFolder()}
                    disabled={busy !== null}
                  >
                    <FolderOpen size={13} /> بازکردنِ پوشه
                  </button>
                </div>
                <span className="bk-hint">
                  اگر پوشه‌ای روی درایوِ بیرونی یا فضای ابری (OneDrive، Google Drive) انتخاب کنید،
                  نسخه‌ها بیرون از این کامپیوتر هم نگه داشته می‌شوند — که کلِ هدفِ پشتیبان است.
                </span>
              </div>
            </div>
          </SectionCard>
        ) : (
          <SectionCard
            icon={Download}
            title="پشتیبانِ دستی"
            description="یک فایلِ کاملِ داده‌ی کسب‌وکار روی دستگاهِ خودتان دانلود می‌شود."
          >
            <div className="backup-actions">
              <button type="button" className="btn-primary" onClick={handleBackupNow} disabled={busy !== null}>
                <Download size={15} /> {busy === 'now' ? 'در حال آماده‌سازی…' : 'دانلودِ فایلِ پشتیبان'}
              </button>
              <label className="btn-ghost btn-danger-ghost bk-file-btn">
                <Upload size={15} /> بازیابی از فایل
                <input type="file" accept="application/json,.json" onChange={handleRestoreWeb} hidden />
              </label>
            </div>
          </SectionCard>
        )}

        <div className="profile-side">
          {auto && (
            <SectionCard icon={ShieldCheck} title="وضعیت">
              <ul className="bk-status">
                <li>
                  <span>آخرین نسخه</span>
                  <strong>
                    {status.last ? `${fmtTime(status.last.mtime)} (${relative(status.last.mtime)})` : 'هنوز نسخه‌ای نیست'}
                  </strong>
                </li>
                <li>
                  <span>نسخه‌ی خودکارِ بعدی</span>
                  <strong>
                    {!s.enabled
                      ? 'خاموش'
                      : s.everyHours === 0
                        ? 'با همگام‌سازیِ بعدی'
                        : status.nextAt
                          ? relative(status.nextAt)
                          : 'در اولین فرصت'}
                  </strong>
                </li>
                <li>
                  <span>تعداد نسخه‌ها</span>
                  <strong>{status.count.toLocaleString('fa-IR')}</strong>
                </li>
                <li>
                  <span>فضای اشغال‌شده</span>
                  <strong>{fmtSize(status.totalSize)}</strong>
                </li>
              </ul>

              <div className="backup-actions">
                <button type="button" className="btn-primary" onClick={handleBackupNow} disabled={busy !== null}>
                  <Save size={15} /> {busy === 'now' ? 'در حال ساخت…' : 'همین حالا یک نسخه بگیر'}
                </button>
                <button type="button" className="btn-ghost" onClick={handleSaveAs} disabled={busy !== null}>
                  <HardDriveDownload size={15} /> ذخیره در محلِ دلخواه
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-danger-ghost"
                  onClick={handleRestoreFile}
                  disabled={busy !== null}
                >
                  <Upload size={15} /> بازیابی از فایل
                </button>
              </div>
            </SectionCard>
          )}

          <SectionCard
            icon={AlertTriangle}
            title="پیش از بازیابی بخوانید"
            description="بازیابی یک کارِ برگشت‌ناپذیر است."
          >
            <ul className="pw-facts">
              <li>
                <strong>بازیابی جایگزین می‌کند، نه ادغام.</strong> همه‌ی داده‌ی فعلیِ کسب‌وکار پاک
                و محتوای فایلِ پشتیبان جایش نوشته می‌شود.
              </li>
              <li>
                <strong>یا کامل انجام می‌شود یا هیچ.</strong> کلِ بازیابی در یک تراکنش است؛ اگر
                وسطِ کار خطایی بدهد، داده‌ی قبلی دست‌نخورده برمی‌گردد.
              </li>
              <li>
                <strong>پیش از بازیابی یک نسخه‌ی تازه بگیرید.</strong> این تنها راهِ برگشت به
                وضعیتِ فعلی است اگر فایلِ پشتیبان آن چیزی نبود که فکر می‌کردید.
              </li>
            </ul>
          </SectionCard>
        </div>
      </div>

      {auto && (
        <SectionCard
          icon={DatabaseBackup}
          title="نسخه‌های ذخیره‌شده"
          description="تازه‌ترین بالا. بازیابی از هر نسخه مستقیم از همین‌جا ممکن است."
        >
          {locals.length === 0 ? (
            <EmptyState icon={DatabaseBackup} text="هنوز نسخه‌ای ساخته نشده." />
          ) : (
            <div className="table-scroll">
              <table className="cards-on-mobile">
                <thead>
                  <tr>
                    <th>زمان</th>
                    <th>حجم</th>
                    <th>فایل</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {locals.map((b) => (
                    <tr key={b.file}>
                      <td className="card-title" data-label="زمان">
                        {fmtTime(b.mtime)}
                      </td>
                      <td data-label="حجم">{fmtSize(b.size)}</td>
                      <td data-label="فایل" className="bk-file">
                        {b.file}
                      </td>
                      <td data-label="عملیات">
                        <div className="fy-actions">
                          <button type="button" onClick={() => handleRestoreLocal(b)} disabled={busy !== null}>
                            <Upload size={13} /> بازیابی
                          </button>
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={() => handleDelete(b)}
                            disabled={busy !== null}
                          >
                            <Trash2 size={13} /> حذف
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      )}
    </div>
  )
}
