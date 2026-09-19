import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Info, Keyboard, Search, X } from 'lucide-react'

import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { buildCommands, textMatches } from '../lib/commands'
import {
  assign,
  chordFromEvent,
  chordId,
  chordLabel,
  chordProblem,
  findConflict,
  idForTarget,
  isBrowserReserved,
  labelFromId,
  loadShortcuts,
  saveShortcuts,
  targetKey,
  unassign,
  type ShortcutMap,
} from '../lib/shortcuts'
import type { MeResponse } from '../api'

/**
 * کلیدهای میان‌بر — هر ماژول یا کاری که کاربر زیاد سراغش می‌رود، یک کلید.
 *
 * فهرستِ مقصدها همان `buildCommands` است که جست‌وجوی داشبورد و کامندپالت
 * می‌خوانند؛ یعنی هر ماژولی که به منو اضافه شود، بی‌هیچ کاری این‌جا هم می‌آید.
 *
 * **دو قاعده‌ی این صفحه:**
 *
 * ۱. ترکیب با **جای فیزیکیِ کلید** ذخیره می‌شود. روی کیبوردِ فارسی همان کلید
 *    حرفِ دیگری تایپ می‌کند، و میان‌بری که با حرف ذخیره شود بی‌صدا از کار
 *    می‌افتد — دقیقاً بلایی که سرِ `Ctrl+K` آمده بود.
 * ۲. ترکیبی که مرورگر برای خودش برمی‌دارد **رد نمی‌شود**، هشدار می‌گیرد؛ در
 *    نسخه‌ی ویندوز همان ترکیب کار می‌کند. («گزارش، نه گارد».)
 */
export function ShortcutsPage({
  me,
  onNavigate,
}: {
  me: MeResponse
  onNavigate: (page: string, section?: string) => void
}) {
  const [map, setMap] = useState<ShortcutMap>(() => loadShortcuts())
  const [query, setQuery] = useState('')
  const [recording, setRecording] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)
  const recordingRef = useRef<string | null>(null)
  recordingRef.current = recording

  const commands = useMemo(() => buildCommands(me), [me])
  const rows = useMemo(
    () => commands.filter((c) => textMatches(`${c.title} ${c.subtitle ?? ''}`, query)),
    [commands, query],
  )

  /** ضبط: اولین ترکیبِ معتبری که کاربر می‌زند. */
  useEffect(() => {
    if (!recording) return
    function onKey(e: KeyboardEvent) {
      const key = recordingRef.current
      if (!key) return
      e.preventDefault()
      e.stopPropagation()

      if (e.code === 'Escape') {
        setRecording(null)
        return
      }
      const chord = chordFromEvent(e)
      const problem = chordProblem(chord)
      if (problem === 'modifier-only') return //: هنوز منتظرِ کلیدِ اصلی
      if (problem === 'needs-modifier') {
        setMsg({ text: 'میان‌بر باید دستِ‌کم یکی از Ctrl یا Alt را داشته باشد — وگرنه وسطِ تایپ اجرا می‌شود.', kind: 'err' })
        return
      }

      const id = chordId(chord)
      const clash = findConflict(map, id, key)
      if (clash) {
        const owner = commands.find((c) => targetKey({ page: c.page, section: c.section }) === clash)
        setMsg({ text: `«${chordLabel(chord)}» از قبل به «${owner?.title ?? clash}» داده شده.`, kind: 'err' })
        return
      }

      const cmd = commands.find((c) => targetKey({ page: c.page, section: c.section }) === key)
      if (!cmd) return
      const next = assign(map, id, { page: cmd.page, section: cmd.section })
      setMap(next)
      setRecording(null)
      setMsg(
        saveShortcuts(next)
          ? {
              text: isBrowserReserved(id)
                ? `«${chordLabel(chord)}» ثبت شد — ولی مرورگر این ترکیب را برای خودش برمی‌دارد. در نسخه‌ی ویندوز کار می‌کند.`
                : `«${chordLabel(chord)}» به «${cmd.title}» داده شد.`,
              kind: isBrowserReserved(id) ? 'err' : 'ok',
            }
          : { text: 'ذخیره نشد — مرورگر اجازه‌ی نگه‌داشتنِ تنظیمات را نداد (پنجره‌ی ناشناس؟).', kind: 'err' },
      )
    }
    //: `capture` تا پیش از هر شنونده‌ی دیگری برسد؛ وگرنه `Ctrl+K` وسطِ ضبط
    //: کامندپالت را باز می‌کرد.
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [recording, map, commands])

  function clear(key: string) {
    const next = unassign(map, key)
    setMap(next)
    saveShortcuts(next)
    setMsg(null)
  }

  const assigned = Object.keys(map).length

  return (
    <div className="page panels">
      <PageHeader
        icon={Keyboard}
        title="کلیدهای میان‌بر"
        description="برای ماژول‌ها و کارهایی که زیاد سراغشان می‌روید یک کلید بگذارید تا از هر جای برنامه با همان باز شوند."
      />

      {msg && (
        <section className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <Info size={16} /> : <AlertTriangle size={16} />}
          <span>{msg.text}</span>
        </section>
      )}

      <SectionCard
        icon={Keyboard}
        title="میان‌برها"
        description={
          assigned === 0
            ? 'هنوز میان‌بری تعریف نشده. روی «تعریف» بزنید و بعد کلیدها را فشار دهید.'
            : `${assigned.toLocaleString('fa-IR')} میان‌بر تعریف شده. روی «تعریف» بزنید و بعد کلیدها را فشار دهید.`
        }
      >
        <p className="field-hint sc-note">
          <Info size={14} /> میان‌برها روی همین دستگاه ذخیره می‌شوند و با جای
          فیزیکیِ کلید کار می‌کنند — پس با کیبوردِ فارسی هم می‌آیند.
        </p>

        <div className="sc-search">
          <Search size={16} />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="جست‌وجو میان ماژول‌ها و کارها…"
            aria-label="جست‌وجوی مقصد"
          />
        </div>

        <div className="table-scroll">
          <table className="cards-on-mobile">
            <thead>
              <tr>
                <th>مقصد</th>
                <th>نوع</th>
                <th>کلید</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    چیزی با این نام پیدا نشد.
                  </td>
                </tr>
              ) : (
                rows.map((c) => {
                  const key = targetKey({ page: c.page, section: c.section })
                  const id = idForTarget(map, key)
                  const isRec = recording === key
                  return (
                    <tr key={c.id}>
                      <td className="card-title" data-label="مقصد">
                        {c.title}
                      </td>
                      <td data-label="نوع">{c.kind === 'task' ? 'کار' : 'صفحه'}</td>
                      <td data-label="کلید">
                        {isRec ? (
                          <span className="sc-recording">کلیدها را فشار دهید… (Esc برای انصراف)</span>
                        ) : id ? (
                          <kbd className="sc-kbd">{labelFromId(id)}</kbd>
                        ) : (
                          <span className="muted">—</span>
                        )}
                        {id && isBrowserReserved(id) && !isRec && (
                          <span className="sc-warn" title="مرورگر این ترکیب را برای خودش برمی‌دارد">
                            <AlertTriangle size={13} /> فقط در نسخه‌ی ویندوز
                          </span>
                        )}
                      </td>
                      <td className="card-actions">
                        <button type="button" onClick={() => { setMsg(null); setRecording(isRec ? null : key) }}>
                          {isRec ? 'انصراف' : id ? 'تغییر' : 'تعریف'}
                        </button>
                        {id && (
                          <button type="button" className="btn-ghost" onClick={() => clear(key)} title="برداشتنِ میان‌بر">
                            <X size={14} />
                          </button>
                        )}
                        <button type="button" className="btn-ghost" onClick={() => onNavigate(c.page, c.section)}>
                          رفتن
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  )
}
