/**
 * کاتالوگِ کارت‌های داشبورد.
 *
 * قیدی که این فایل نگه می‌دارد: **هر کارتِ پیش‌فرض باید به جایی برسد که اسمش را
 * می‌برد.** لانچرِ «دریافت و پرداخت» سال‌ها به `contacts/treasury` اشاره می‌کرد —
 * تبی که وجود نداشت — پس کاربر روی کارت می‌زد و تبِ اولِ «اشخاص» باز می‌شد. هیچ
 * تایپی و هیچ ممیزی آن را نمی‌دید، چون `section` فقط یک رشته است. این تست همان
 * سکوت را می‌شکند: پیش‌فرضی که در کاتالوگ نباشد، قرمز می‌دهد.
 */
import { describe, it, expect } from 'vitest'

import { MODE_DEFAULT_CARDS, buildLaunchers, cardHint, launchIndex, resolveCards } from './launchers'
import type { MeResponse } from '../api'

const me = {
  id: 'u1',
  name: 'آزمون',
  email: 'a@b.c',
  phone: null,
  phone_verified: false,
  email_verified: true,
  role_key: 'owner',
  role_name: 'مالک',
  permissions: {},
  tenant_id: 't1',
  tenant_name: 'نمونه',
  tenant_kind: 'standard',
  is_trial: false,
  trial_days_left: null,
  trial_expired: false,
  locked_features: [],
  dashboard_cards: null,
  industry: 'general',
  trade: null,
  //: خالی یعنی «فیلتر نکن» (fail-open در `buildNav`) — کاتالوگِ کامل.
  enabled_modules: [],
  allowed_modules: [],
} as unknown as MeResponse

const groups = buildLaunchers(me)
const index = launchIndex(groups)

describe('کاتالوگِ مقصدها', () => {
  it('از ماژول‌های واقعی ساخته می‌شود، نه فهرستِ دستی', () => {
    expect(groups.length).toBeGreaterThan(5)
    expect(index.size).toBeGreaterThan(100)
  })

  it('هر شناسه یکتاست — صفحه‌ی مشترکِ دو گروه دو کارت نمی‌شود', () => {
    const all = groups.flatMap((g) => g.items.map((t) => t.id))
    expect(all.length).toBe(new Set(all).size)
  })

  it('هر دو نوعِ «عملیات» و «فهرست» در کاتالوگ هستند', () => {
    const kinds = new Set(groups.flatMap((g) => g.items.map((t) => t.kind)))
    expect(kinds).toEqual(new Set(['ops', 'list']))
  })

  it('شناسه‌ها همان شکلی‌اند که سرور می‌پذیرد', () => {
    const shape = /^[a-z][a-z0-9-]*(\/[a-z][a-z0-9-]*)?$/
    for (const id of index.keys()) expect(id, id).toMatch(shape)
  })

  it('کارتی به خودِ داشبورد نمی‌برد', () => {
    expect(index.has('overview')).toBe(false)
  })

  it('دو ردیفِ هم‌نامِ هم‌نوع در یک گروه نمی‌ماند', () => {
    //: هم‌نامیِ «عملیات» و «فهرست» عمدی است (قاعده‌ی نظیر: فرمِ ثبت و دفترِ همان)؛
    //: هم‌نامی *درونِ* یک نوع یعنی یک چیز دو بار آمده.
    for (const g of groups) {
      const keys = g.items.map((t) => `${t.kind}:${t.label}`)
      expect(new Set(keys).size, g.heading).toBe(keys.length)
    }
  })

  it('کارتِ فهرست از عملیاتِ هم‌نامش قابلِ تشخیص است', () => {
    const geo = [...index.values()].filter((t) => t.label === 'محل‌های جغرافیایی')
    expect(geo.length).toBe(2)
    expect(new Set(geo.map(cardHint)).size).toBe(2)
  })

  it('تبِ یک صفحه، نامِ صفحه‌ی میزبان را هم با خود دارد', () => {
    const tab = [...index.values()].find((t) => t.section !== undefined && t.parent !== undefined)
    expect(tab).toBeDefined()
  })
})

describe('کارت‌های پیش‌فرض', () => {
  const MODES = ['accountant', 'simple'] as const

  it.each(MODES)('**هسته‌ی این تست** — هر پیش‌فرضِ حالتِ %s در کاتالوگ هست', (mode) => {
    //: شناسه‌ی غلط این‌جا خطا نمی‌دهد — `resolveCards` بی‌صدا کنارش می‌گذارد و
    //: داشبورد فقط یک کارت کمتر دارد. «دفتر روزنامه» اول به `ebooks` نگاشته شده
    //: بود که «دفاتر تجارت الکترونیک» است، نه دفترِ روزنامه.
    for (const id of MODE_DEFAULT_CARDS[mode]) expect(index.has(id), id).toBe(true)
  })

  it.each(MODES)('پیش‌فرض‌های حالتِ %s تکراری ندارند', (mode) => {
    const ids = MODE_DEFAULT_CARDS[mode]
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('همان فهرستِ §۵۳ — هشت کارتِ حسابدار، هفت کارتِ ساده', () => {
    //: ساده هفت‌تاست نه هشت: «بدهکاران» و «طلبکاران» یک صفحه‌اند (`contacts/aging`
    //: با یک کلید) و دو کارت به یک مقصد قاعده‌ی یکتاییِ همین کاتالوگ را می‌شکست.
    expect(MODE_DEFAULT_CARDS.accountant).toHaveLength(8)
    expect(MODE_DEFAULT_CARDS.simple).toHaveLength(7)
  })

  it('دو حالت واقعاً دو داشبوردِ متفاوت‌اند', () => {
    const acc = new Set(MODE_DEFAULT_CARDS.accountant)
    expect(MODE_DEFAULT_CARDS.simple.some((id) => acc.has(id))).toBe(false)
  })

  it.each(MODES)('بدونِ انتخابِ کاربر، پیش‌فرض‌های حالتِ %s نشان داده می‌شوند', (mode) => {
    expect(resolveCards(groups, null, mode).map((t) => t.id)).toEqual(MODE_DEFAULT_CARDS[mode])
  })

  it.each(MODES)('فهرستِ خالی در حالتِ %s یعنی خالی — نه بازگشت به پیش‌فرض', (mode) => {
    expect(resolveCards(groups, [], mode)).toEqual([])
  })

  it('**عوض‌کردنِ حالت چیدمانِ شخصیِ کاربر را دست نمی‌زند**', () => {
    const saved = ['quotations', 'salesinvoice']
    const asAccountant = resolveCards(groups, saved, 'accountant').map((t) => t.id)
    const asSimple = resolveCards(groups, saved, 'simple').map((t) => t.id)
    expect(asAccountant).toEqual(saved)
    expect(asSimple).toEqual(saved)
  })

  it('شناسه‌ی ناشناخته کنار می‌رود و بقیه می‌مانند', () => {
    const cards = resolveCards(groups, ['salesinvoice', 'ماژولِ حذف‌شده', 'quotations'], 'simple')
    expect(cards.map((t) => t.id)).toEqual(['salesinvoice', 'quotations'])
  })

  it('ترتیبِ کاربر حفظ می‌شود', () => {
    expect(resolveCards(groups, ['quotations', 'salesinvoice'], 'accountant').map((t) => t.id)).toEqual([
      'quotations',
      'salesinvoice',
    ])
  })
})
