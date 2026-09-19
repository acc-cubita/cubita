/**
 * کلیدهای میان‌بر.
 *
 * قیدِ اصلی که این فایل نگه می‌دارد: **میان‌بر با جای فیزیکیِ کلید ذخیره می‌شود،
 * نه با حرفی که چیدمان تولید می‌کند.** اگر روزی کسی به `key` برگردد، میان‌برها
 * روی کیبوردِ فارسی بی‌صدا از کار می‌افتند — همان چیزی که یک بار سرِ `Ctrl+K`
 * اتفاق افتاد و تا وقتی کاربر گزارش نداد کسی نفهمید.
 */
import { describe, it, expect } from 'vitest'

import {
  assign,
  chordFromEvent,
  chordId,
  chordLabel,
  chordProblem,
  findConflict,
  idForTarget,
  isBrowserReserved,
  isTypingTarget,
  labelFromId,
  unassign,
  type ShortcutMap,
} from './shortcuts'

const ev = (code: string, mods: Partial<Record<'ctrlKey' | 'altKey' | 'shiftKey' | 'metaKey', boolean>> = {}) => ({
  code,
  ctrlKey: false,
  altKey: false,
  shiftKey: false,
  metaKey: false,
  ...mods,
})

describe('ساختِ ترکیب', () => {
  it('**هسته‌ی این ویژگی** — چیدمان بی‌اثر است، چون جای فیزیکی ذخیره می‌شود', () => {
    //: روی کیبوردِ فارسی همین کلید «ن» تایپ می‌کند، ولی `code` همان KeyK است.
    expect(chordId(chordFromEvent(ev('KeyK', { ctrlKey: true })))).toBe('ctrl+KeyK')
  })

  it('ترتیبِ تغییردهنده‌ها متعارف می‌شود', () => {
    const a = chordId(chordFromEvent(ev('KeyI', { ctrlKey: true, altKey: true })))
    const b = chordId(chordFromEvent(ev('KeyI', { altKey: true, ctrlKey: true })))
    expect(a).toBe(b)
    expect(a).toBe('ctrl+alt+KeyI')
  })

  it('برچسبِ خواندنی می‌دهد و از شناسه هم برمی‌گردد', () => {
    const c = chordFromEvent(ev('Digit1', { ctrlKey: true, shiftKey: true }))
    expect(chordLabel(c)).toBe('Ctrl + Shift + 1')
    expect(labelFromId(chordId(c))).toBe('Ctrl + Shift + 1')
  })
})

describe('ترکیبِ پذیرفتنی', () => {
  it('کلیدِ تنها رد می‌شود — وگرنه وسطِ تایپ می‌پرد', () => {
    expect(chordProblem(chordFromEvent(ev('KeyA')))).toBe('needs-modifier')
  })

  it('Shift به‌تنهایی کافی نیست؛ همان تایپِ حرفِ بزرگ است', () => {
    expect(chordProblem(chordFromEvent(ev('KeyA', { shiftKey: true })))).toBe('needs-modifier')
  })

  it('خودِ کلیدِ تغییردهنده ترکیب نیست', () => {
    expect(chordProblem(chordFromEvent(ev('ControlLeft', { ctrlKey: true })))).toBe('modifier-only')
  })

  it('کلیدِ F تنها قبول است — تایپ نمی‌کند', () => {
    expect(chordProblem(chordFromEvent(ev('F2')))).toBeNull()
  })

  it('Ctrl یا Alt کافی است', () => {
    expect(chordProblem(chordFromEvent(ev('KeyA', { ctrlKey: true })))).toBeNull()
    expect(chordProblem(chordFromEvent(ev('KeyA', { altKey: true })))).toBeNull()
  })
})

describe('ترکیب‌هایی که مرورگر برمی‌دارد', () => {
  it('Ctrl+T شناسایی می‌شود ولی جلویش گرفته نمی‌شود — در دسکتاپ کار می‌کند', () => {
    expect(isBrowserReserved('ctrl+KeyT')).toBe(true)
  })

  it('Ctrl+B آزاد است', () => {
    expect(isBrowserReserved('ctrl+KeyB')).toBe(false)
  })
})

describe('نسبت‌دادن و برخورد', () => {
  const base: ShortcutMap = { 'ctrl+KeyB': { page: 'inventory' } }

  it('برخورد را با نامِ صاحبِ فعلی گزارش می‌کند', () => {
    expect(findConflict(base, 'ctrl+KeyB')).toBe('inventory')
    expect(findConflict(base, 'ctrl+KeyZ')).toBeNull()
  })

  it('اگر صاحبش خودش باشد، برخورد نیست', () => {
    expect(findConflict(base, 'ctrl+KeyB', 'inventory')).toBeNull()
  })

  it('**هر مقصد یک میان‌بر** — نسبتِ تازه، قبلی را برمی‌دارد', () => {
    const next = assign(base, 'ctrl+KeyN', { page: 'inventory' })
    expect(idForTarget(next, 'inventory')).toBe('ctrl+KeyN')
    expect(next['ctrl+KeyB']).toBeUndefined()
    expect(Object.keys(next)).toHaveLength(1)
  })

  it('**هر ترکیب یک مقصد** — گرفتنِ ترکیبِ دیگری آن را از صاحبِ قبلی می‌گیرد', () => {
    const next = assign(base, 'ctrl+KeyB', { page: 'crm' })
    expect(next['ctrl+KeyB']).toEqual({ page: 'crm' })
    expect(idForTarget(next, 'inventory')).toBeNull()
  })

  it('تب‌های یک صفحه مقصدهای جدا هستند', () => {
    let m = assign({}, 'ctrl+KeyD', { page: 'inventory', section: 'stock' })
    m = assign(m, 'ctrl+KeyE', { page: 'inventory', section: 'kardex' })
    expect(Object.keys(m)).toHaveLength(2)
    expect(idForTarget(m, 'inventory/stock')).toBe('ctrl+KeyD')
  })

  it('برداشتن', () => {
    expect(unassign(base, 'inventory')).toEqual({})
  })
})

describe('گاردِ تایپ', () => {
  it('وقتی کاربر در حالِ نوشتن است، میان‌بر نباید بپرد', () => {
    for (const tag of ['INPUT', 'TEXTAREA', 'SELECT']) {
      expect(isTypingTarget({ tagName: tag } as unknown as EventTarget)).toBe(true)
    }
    expect(isTypingTarget({ tagName: 'DIV', isContentEditable: true } as unknown as EventTarget)).toBe(true)
    expect(isTypingTarget({ tagName: 'DIV' } as unknown as EventTarget)).toBe(false)
    expect(isTypingTarget(null)).toBe(false)
  })
})
