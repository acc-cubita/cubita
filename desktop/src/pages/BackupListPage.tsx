import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, DatabaseBackup, FolderOpen, RefreshCw, Trash2, Upload } from 'lucide-react'
import { importBackup, type MeResponse } from '../api'
import { isElectron } from '../platform'
import type { LocalBackup } from '../electron.d'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'

/**
 * فهرستِ نسخه‌های پشتیبان — نیمه‌ی «دیدن و بازیابی‌کردن».
 *
 * صفحه‌ی «پشتیبان‌گیری خودکار» زمان‌بندی و ساختِ نسخه را دارد؛ کارِ روی نسخه‌ی موجود
 * (بازیابی، حذف) این‌جاست، چون به یک ردیفِ مشخص گره خورده.
 *
 * نسخه‌ها روی دیسکِ خودِ کاربرند نه سرور، پس نسخه‌ی وب فهرستی ندارد و صریح می‌گوید؛
 * ولی بازیابی از فایل آن‌جا هم کار می‌کند، چون بازیابی سمتِ سرور انجام می‌شود.
 */

const fmtSize = (n: number) =>
  n < 1024 * 1024
    ? `${Math.round(n / 1024).toLocaleString('fa-IR')} کیلوبایت`
    : `${(n / 1048576).toLocaleString('fa-IR', { maximumFractionDigits: 1 })} مگابایت`

const fmtTime = (ms: number) =>
  new Date(ms).toLocaleString('fa-IR', { dateStyle: 'medium', timeStyle: 'short' })

const RESTORE_WARNING =
  'هشدار: بازیابی همه‌ی داده‌ی فعلیِ این کسب‌وکار را پاک می‌کند و نسخه‌ی داخلِ فایلِ پشتیبان را جایگزین می‌کند. این کار برگشت‌ناپذیر است.\n\nمطمئن هستید؟'

export function BackupListPage({ token, me }: { token: string; me: MeResponse }) {
  const isOwner = Boolean(me.permissions['*'])
  const [locals, setLocals] = useState<LocalBackup[]>([])
  const [dir, setDir] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)

  const refresh = useCallback(async () => {
    if (!isElectron) return
    try {
      const [list, status] = await Promise.all([
        window.cubita.backupListLocal(),
        window.cubita.backupStatus(),
      ])
      setLocals(list)
      setDir(status.dir)
    } catch {
      // خواندنِ فهرست نباید صفحه را از کار بیندازد؛ بازیابی از فایل همچنان هست.
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

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
          title="نسخه‌های پشتیبانی و بازیابی"
          description="نسخه‌های پشتیبانِ داده‌ی کسب‌وکار."
        />
        <div className="fy-note fy-note--warn">
          <AlertTriangle size={16} />
          <div>
            <strong>این بخش فقط برای مالکِ کسب‌وکار است.</strong>
            <p>فایلِ پشتیبان کلِ داده‌ی مالی است و بازیابی همه‌چیز را جایگزین می‌کند.</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={DatabaseBackup}
        title="نسخه‌های پشتیبانی و بازیابی"
        description="نسخه‌های ذخیره‌شده روی این کامپیوتر — تازه‌ترین بالا. بازیابی از هر نسخه مستقیم از همین‌جا ممکن است."
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
            <strong>فهرستِ نسخه‌ها فقط در نسخه‌ی دسکتاپ دیده می‌شود.</strong>
            <p>
              نسخه‌ها روی دیسکِ خودِ شما ذخیره می‌شوند و مرورگر به آن دسترسی ندارد. با این حال
              بازیابی از فایل این‌جا هم کار می‌کند، چون خودِ بازیابی سمتِ سرور انجام می‌شود.
            </p>
          </div>
        </div>
      )}

      <SectionCard
        icon={DatabaseBackup}
        title="نسخه‌های ذخیره‌شده"
        description={isElectron && dir ? dir : undefined}
        actions={
          <div className="check-actions">
            {isElectron && (
              <>
                <button type="button" onClick={() => void window.cubita.backupOpenFolder()} disabled={busy !== null}>
                  <FolderOpen size={13} /> پوشه
                </button>
                <button
                  type="button"
                  className="btn-danger-ghost"
                  disabled={busy !== null}
                  onClick={() => {
                    if (!window.confirm(RESTORE_WARNING)) return
                    void run('restoreFile', async () => {
                      const r = await window.cubita.backupRestoreFromFile()
                      if (r.canceled) return null
                      return { text: r.message, kind: r.restored ? 'ok' : 'err' }
                    })
                  }}
                >
                  <Upload size={13} /> بازیابی از فایل
                </button>
              </>
            )}
            {!isElectron && (
              <label className="btn-ghost btn-danger-ghost bk-file-btn">
                <Upload size={13} /> بازیابی از فایل
                <input type="file" accept="application/json,.json" onChange={handleRestoreWeb} hidden />
              </label>
            )}
            {isElectron && (
              <button type="button" onClick={() => void refresh()} disabled={busy !== null} title="به‌روزرسانی">
                <RefreshCw size={13} />
              </button>
            )}
          </div>
        }
      >
        {!isElectron ? (
          <EmptyState icon={DatabaseBackup} text="در نسخه‌ی وب فهرستی وجود ندارد." />
        ) : locals.length === 0 ? (
          <EmptyState icon={DatabaseBackup} text="هنوز نسخه‌ای ساخته نشده. از «تنظیمات ← پشتیبان‌گیری خودکار» یکی بسازید." />
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
                        <button
                          type="button"
                          disabled={busy !== null}
                          onClick={() => {
                            if (!window.confirm(`${fmtTime(b.mtime)}\n\n${RESTORE_WARNING}`)) return
                            void run(`restore-${b.file}`, async () => {
                              const r = await window.cubita.backupRestoreFromLocal(b.file)
                              return { text: r.message, kind: r.restored ? 'ok' : 'err' }
                            })
                          }}
                        >
                          <Upload size={13} /> بازیابی
                        </button>
                        <button
                          type="button"
                          className="btn-danger"
                          disabled={busy !== null}
                          onClick={() => {
                            if (!window.confirm(`نسخه‌ی ${fmtTime(b.mtime)} حذف شود؟`)) return
                            void run(`del-${b.file}`, async () => {
                              await window.cubita.backupDeleteLocal(b.file)
                              return { text: 'نسخه حذف شد.', kind: 'ok' }
                            })
                          }}
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
    </div>
  )
}
