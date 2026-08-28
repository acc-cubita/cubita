import { RotateCcw } from 'lucide-react'
import type { PermissionMap, PermissionModule } from '../api'

/** آیا این نقشه دسترسیِ کامل («*») می‌دهد؟ نقشِ مالک همین است. */
export const isFullAccess = (p: PermissionMap) => Array.isArray(p['*'])

const fa = (n: number) => n.toLocaleString('fa-IR')

/** خلاصه‌ی خوانا از یک نقشه‌ی دسترسی — «۳ ماژول · ۷ اجازه». */
export function summarize(p: PermissionMap): string {
  if (isFullAccess(p)) return 'دسترسی کامل'
  const modules = Object.keys(p).filter((k) => (p[k] ?? []).length > 0)
  if (modules.length === 0) return 'بدون دسترسی'
  const actions = modules.reduce((sum, k) => sum + (p[k]?.length ?? 0), 0)
  return `${fa(modules.length)} ماژول · ${fa(actions)} اجازه`
}

/**
 * جدولِ ماژول × اکشن.
 *
 * «مشاهده» ستونِ ویژه است: بدونِ آن هیچ اکشنِ دیگری معنا ندارد (کاربر اجازه‌ی ثبت
 * دارد ولی صفحه‌ای برای دیدنش نه). پس برداشتنِ «مشاهده» کلِ ماژول را پاک می‌کند و
 * زدنِ هر اکشنِ دیگر، «مشاهده» را هم روشن می‌کند — همان قاعده‌ای که سرور هم اعمال
 * می‌کند، تا آنچه می‌بینید همان چیزی باشد که ذخیره می‌شود.
 */
export function PermissionMatrix({
  modules,
  value,
  onChange,
  onReset,
  readOnly,
  note,
}: {
  modules: PermissionModule[]
  value: PermissionMap
  onChange: (next: PermissionMap | null) => void
  onReset?: () => void
  readOnly?: boolean
  note?: string
}) {
  if (modules.length === 0) return null

  const has = (mod: string, action: string) => (value[mod] ?? []).includes(action)

  function toggle(mod: PermissionModule, action: string) {
    if (readOnly) return
    const current = new Set(value[mod.key] ?? [])
    if (action === 'view' && current.has('view')) {
      current.clear()
    } else if (current.has(action)) {
      current.delete(action)
    } else {
      current.add(action)
      current.add('view')
    }
    const next: PermissionMap = { ...value }
    if (current.size === 0) delete next[mod.key]
    else next[mod.key] = mod.actions.map((a) => a.key).filter((k) => current.has(k))
    onChange(next)
  }

  function toggleWholeModule(mod: PermissionModule) {
    if (readOnly) return
    const next: PermissionMap = { ...value }
    if ((value[mod.key] ?? []).length === mod.actions.length) delete next[mod.key]
    else next[mod.key] = mod.actions.map((a) => a.key)
    onChange(next)
  }

  return (
    <div className="tm-matrix">
      <div className="tm-matrix-head">
        <span>دسترسی به ماژول‌ها</span>
        <span className="tm-matrix-sum">{summarize(value)}</span>
        {onReset && (
          <button type="button" onClick={onReset}>
            <RotateCcw size={12} /> بازگشت به نقش
          </button>
        )}
      </div>
      {note && <p className="bk-hint tm-matrix-note">{note}</p>}
      <div className="table-scroll">
        <table className="tm-matrix-table table-plain">
          <thead>
            <tr>
              <th>ماژول</th>
              {['مشاهده', 'ثبت', 'ویرایش', 'حذف', 'تأیید', 'تحویل'].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {modules.map((mod) => {
              const granted = (value[mod.key] ?? []).length
              return (
                <tr key={mod.key} className={granted > 0 ? 'on' : ''}>
                  <th scope="row">
                    <button
                      type="button"
                      className="tm-mod-name"
                      onClick={() => toggleWholeModule(mod)}
                      disabled={readOnly}
                      title="روشن/خاموش‌کردنِ همه‌ی اجازه‌های این ماژول"
                    >
                      {mod.label}
                    </button>
                    {mod.hint && <span className="tm-mod-hint">{mod.hint}</span>}
                  </th>
                  {['view', 'create', 'update', 'delete', 'approve', 'deliver'].map((action) => {
                    const supported = mod.actions.some((a) => a.key === action)
                    return (
                      <td key={action}>
                        {supported ? (
                          <input
                            type="checkbox"
                            checked={has(mod.key, action)}
                            disabled={readOnly}
                            onChange={() => toggle(mod, action)}
                            aria-label={`${mod.label} — ${action}`}
                          />
                        ) : (
                          <span className="tm-na">—</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
