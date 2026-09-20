import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronLeft, LayoutGrid, RotateCcw, X } from 'lucide-react'

import { LaunchIcon } from './LaunchIcon'
import type { LaunchGroup, LaunchTarget } from '../lib/launchers'
import { textMatches } from '../lib/commands'
import { CountBadge, FormStatus, SearchField } from './form/FormKit'

const fa = (n: number) => n.toLocaleString('fa-IR')

/** سقفِ کارت — همان عددی که سرور هم می‌پذیرد (`app/schemas/dashboard.py`). */
export const MAX_CARDS = 24

/**
 * انتخاب‌گرِ کارت‌های داشبورد: ماژول‌ها باز می‌شوند، کاربر زیرمنوهای موردِ نیازش را
 * تیک می‌زند، و با «تأیید» همان‌ها کارتِ داشبورد می‌شوند.
 *
 * **چرا تیک و نه کشیدن‌ورهاکردن:** انتخاب از میانِ چندصد زیرمنو کارِ *پیداکردن* است
 * نه کارِ چیدن؛ جست‌وجو و تیک این را در چند ثانیه تمام می‌کند. ترتیبِ کارت‌ها همان
 * ترتیبی می‌ماند که کاربر تیک زده — پس اولین چیزی که انتخاب می‌کند، اولین کارت است.
 */
export function LauncherPicker({
  groups,
  selected,
  busy,
  error,
  onCancel,
  onConfirm,
  onReset,
}: {
  groups: LaunchGroup[]
  selected: string[]
  busy: boolean
  error: string | null
  onCancel: () => void
  onConfirm: (ids: string[]) => void
  onReset: () => void
}) {
  const [picked, setPicked] = useState<string[]>(selected)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<'all' | 'ops' | 'list'>('all')
  //: پیش‌فرضْ بسته: پانزده ماژولِ بازشده یعنی چندصد ردیف و کاربر باید کلِ برنامه را
  //: اسکرول کند تا ماژولِ خودش را ببیند. گروهی که از قبل کارتی دارد باز می‌شود.
  const [open, setOpen] = useState<Set<string>>(
    () => new Set(groups.filter((g) => g.items.some((i) => selected.includes(i.id))).map((g) => g.heading)),
  )
  const searchRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    searchRef.current?.querySelector('input')?.focus()
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  const searching = query.trim().length > 0

  const shown = useMemo(
    () =>
      groups
        .map((g) => ({
          ...g,
          items: g.items.filter(
            (t) =>
              (kind === 'all' || t.kind === kind) &&
              textMatches(`${t.label} ${t.parent ?? ''} ${t.group}`, query),
          ),
        }))
        .filter((g) => g.items.length > 0),
    [groups, query, kind],
  )

  const pickedSet = new Set(picked)
  const full = picked.length >= MAX_CARDS

  function toggle(t: LaunchTarget) {
    setPicked((prev) =>
      prev.includes(t.id)
        ? prev.filter((id) => id !== t.id)
        : prev.length >= MAX_CARDS
          ? prev
          : [...prev, t.id],
    )
  }

  //: پرتال به `body` — وگرنه پوشش، فرزندِ مستقیمِ `.dash`/`.guided-dash` می‌شد و
  //: قاعده‌ی `.dash > *` پس‌زمینه و padding پنل را به آن می‌داد. همان الگوی کشوها.
  return createPortal(
    <div className="modal-overlay" onClick={onCancel}>
      <div
        className="modal-card lp-card"
        role="dialog"
        aria-modal="true"
        aria-label="انتخاب کارت‌های داشبورد"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <span>
            <LayoutGrid size={16} /> انتخابِ کارت‌های داشبورد
          </span>
          <button type="button" onClick={onCancel} aria-label="بستن">
            <X size={16} />
          </button>
        </div>

        <div className="modal-body lp-body">
          <p className="lp-lead">
            ماژولِ موردِ نظر را باز کنید و هر زیرمنویی را که هر روز سراغش می‌روید تیک بزنید.
            برای هر تیک یک کارت روی داشبورد می‌نشیند.
          </p>

          <div className="lp-tools">
            <div ref={searchRef} className="lp-search">
              <SearchField
                value={query}
                onChange={setQuery}
                placeholder="نامِ منو، مثلِ فاکتور فروش یا کاردکس"
                label="جست‌وجوی منو"
              />
            </div>
            <div className="lp-kinds" role="group" aria-label="نوعِ منو">
              {([
                ['all', 'همه'],
                ['ops', 'عملیات'],
                ['list', 'فهرست'],
              ] as const).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  className={kind === k ? 'lp-kind is-on' : 'lp-kind'}
                  aria-pressed={kind === k}
                  onClick={() => setKind(k)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {shown.length === 0 ? (
            <p className="muted lp-empty">منویی با این نام پیدا نشد.</p>
          ) : (
            shown.map((g) => {
              //: در حالتِ جست‌وجو همه باز است: کاربر دنبالِ یک نام می‌گردد، نه دنبالِ ماژول.
              const isOpen = searching || open.has(g.heading)
              const count = g.items.filter((t) => pickedSet.has(t.id)).length
              return (
                <section key={g.heading} className={isOpen ? 'lp-group is-open' : 'lp-group'}>
                  <button
                    type="button"
                    className="lp-group-head"
                    aria-expanded={isOpen}
                    onClick={() =>
                      setOpen((prev) => {
                        const next = new Set(prev)
                        if (next.has(g.heading)) next.delete(g.heading)
                        else next.add(g.heading)
                        return next
                      })
                    }
                  >
                    <ChevronLeft size={16} className="lp-chev" aria-hidden="true" />
                    <span className="lp-group-title">{g.heading}</span>
                    {count > 0 && <CountBadge accent>{fa(count)}</CountBadge>}
                    <span className="lp-group-count">{fa(g.items.length)} منو</span>
                  </button>

                  {isOpen && (
                    <div className="lp-items">
                      {g.items.map((t) => {
                        const on = pickedSet.has(t.id)
                        return (
                          <label
                            key={t.id}
                            className={on ? 'lp-item is-on' : full ? 'lp-item is-full' : 'lp-item'}
                          >
                            <input
                              type="checkbox"
                              checked={on}
                              disabled={!on && full}
                              onChange={() => toggle(t)}
                            />
                            <LaunchIcon icon={t.icon} size={16} />
                            <span className="lp-item-label">
                              {t.label}
                              {t.parent && <span className="lp-item-parent">{t.parent}</span>}
                            </span>
                            <span className={t.kind === 'list' ? 'lp-tag is-list' : 'lp-tag'}>
                              {t.kind === 'list' ? 'فهرست' : 'عملیات'}
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  )}
                </section>
              )
            })
          )}
        </div>

        <div className="modal-foot lp-foot">
          <div className="ef-actions-status lp-status">
            <FormStatus
              msg={error ? { text: error, kind: 'err' } : null}
              idle={
                full
                  ? `${fa(MAX_CARDS)} کارت انتخاب شده — سقفِ داشبورد همین است.`
                  : `${fa(picked.length)} کارت انتخاب شده.`
              }
            />
          </div>
          <button type="button" className="ef-btn-secondary" onClick={onReset} disabled={busy}>
            <RotateCcw size={15} /> بازگرداندن به پیش‌فرض
          </button>
          <button type="button" className="ef-btn-secondary" onClick={onCancel} disabled={busy}>
            <X size={15} /> انصراف
          </button>
          <button type="button" className="btn-primary" onClick={() => onConfirm(picked)} disabled={busy}>
            <Check size={16} /> {busy ? 'در حال ذخیره…' : 'تأیید'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
