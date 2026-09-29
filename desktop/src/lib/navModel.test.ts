/**
 * گیتِ منو — و مهم‌تر، **fail-open نبودنش**.
 *
 * قیدی که این فایل نگه می‌دارد: `isVisible` در `buildNav` برای کلیدی که در هیچ‌یک
 * از `PAGE_MODULE_KEY` و `GATED_MODULE_KEYS` نیست، `true` برمی‌گرداند. یعنی
 * فراموش‌کردنِ ثبتِ یک کلیدِ تازه، صفحه را **برای همه** باز می‌کند — بی هیچ خطایی،
 * بی هیچ هشداری. ماژولِ حسابرسی دقیقاً همان چیزی است که نباید این‌طور شود: قرار
 * است تا تأییدِ ما پنهان بماند.
 *
 * (گیتِ واقعی روی سرور است — `require_module("assurance_work")`. این تست فقط
 * می‌گوید منو هم با آن هم‌داستان است.)
 */
import { describe, it, expect } from 'vitest'

import {
  MODE_GROUP_LANDING,
  MODE_GROUP_ORDER,
  LEGACY_PAGES,
  NAV_GROUPS,
  PAGE_MODULE_KEY,
  buildNav,
  groupBarLabel,
  groupEntry,
  groupLanding,
  menuCategories,
  menuEntryVisible,
  navSections,
  orderNavGroups,
  resolveLegacyPage,
  uniqueNavItems,
  type PageKey,
} from './navModel'
import { LIST_MENUS, OPS_LIST_MAP, OPS_MENUS } from '../components/moduleLists'
import type { ExperienceMode } from './experienceMode'
import { DEFINITION_TITLES } from './menuSections'
import { mergeMenu } from './moduleMenu'

//: صفحه‌ی عملیاتِ کاری — در `NAV_GROUPS` است، پس با فیلترِ ناوبری سنجیده می‌شود.
const WORK_OPS: PageKey = 'assurancehealth'
//: دفترها ردیفِ منوی اصلی ندارند؛ دیده‌شدنشان را `menuEntryVisible` تعیین می‌کند
//: (همان چیزی که `ModulePanels` و کشوی موبایل صدا می‌زنند).
const WORK_LISTS: PageKey[] = ['assurancefindinglist', 'assurancerunlist']

const nav = (allowed: string[], enabled?: string[]) =>
  buildNav({
    tenantKind: 'standard',
    enabledModules: enabled ?? allowed,
    allowedModules: allowed,
  })

const keys = (allowed: string[], enabled?: string[]) => {
  const { groups, secondary } = nav(allowed, enabled)
  return new Set(uniqueNavItems(groups, secondary).map((i) => i.key))
}

//: مجموعه‌ای که «کسب‌وکارِ عادی» می‌بیند — بدونِ قراردادِ حسابرسی.
const BASE = ['overview', 'contacts', 'reports', 'accounting', 'assurance']

describe('گیت و دفتر اتوماسیون', () => {
  it('هر سه مسیر زیر مجوز همان ماژول‌اند', () => {
    for (const key of ['automation', 'letternew', 'letterlist'] as const) expect(PAGE_MODULE_KEY[key]).toBe('automation')
    expect(keys(BASE).has('automation')).toBe(false)
    expect(keys([...BASE, 'automation']).has('automation')).toBe(true)
    expect(keys([...BASE, 'automation'], BASE).has('letternew')).toBe(false)
  })
  it('ساخت نامه دفتر نظیر دارد و کارتابل نمای اقدام است', () => {
    expect(OPS_LIST_MAP.letternew).toBe('letterlist')
    expect(OPS_LIST_MAP.automation).toBe('view')
    expect(LIST_MENUS['اتوماسیون اداری'].map(i => i.key)).toEqual(['letterlist'])
  })
})

describe('گیتِ ماژولِ حسابرسی', () => {
  it('**هسته‌ی این تست** — هر چهار کلید ثبت شده‌اند، پس هیچ‌کدام fail-open نیست', () => {
    for (const key of ['assurancerequest', WORK_OPS, ...WORK_LISTS] as PageKey[]) {
      expect(PAGE_MODULE_KEY[key], key).toBeDefined()
    }
  })

  it('صفحه‌ی درخواست با ماژولِ عادی باز است', () => {
    expect(keys(BASE).has('assurancerequest')).toBe(true)
  })

  it('صفحه‌های کاری بدونِ قراردادِ تأییدشده دیده نمی‌شوند', () => {
    expect(keys(BASE).has(WORK_OPS)).toBe(false)
    const { groups } = nav(BASE)
    for (const key of WORK_LISTS) expect(menuEntryVisible(key, groups), key).toBe(false)
  })

  it('با ماژولِ مشتق، صفحه‌های کاری می‌آیند', () => {
    const withWork = [...BASE, 'assurance_work']
    expect(keys(withWork).has(WORK_OPS)).toBe(true)
    const { groups } = nav(withWork)
    for (const key of WORK_LISTS) expect(menuEntryVisible(key, groups), key).toBe(true)
  })

  it('خاموش‌بودنِ خودِ ماژولِ حسابرسی، صفحه‌ی درخواست را هم می‌برد', () => {
    const visible = keys(['overview', 'contacts', 'reports'])
    expect(visible.has('assurancerequest')).toBe(false)
  })

})

describe('مدیریتِ پلتفرم برنمی‌گردد', () => {
  //: چهار منوی «مدیریت سامانه» به اپِ مستقلِ `admin/` کوچ کردند
  //: (`admin.cubita.ir`). این تست وارونه‌ی تستِ قبلی است: پیش‌تر اثبات می‌کرد
  //: کارتابلِ ستاد از `SUPER_ADMIN_NAV_ITEMS` **می‌آید**؛ حالا اثبات می‌کند
  //: هیچ‌کدامشان از هیچ راهی نمی‌آیند.
  //:
  //: گاردِ واقعی سرور است، ولی برگشتنِ یک منوی مدیریتی به اپِ مشتری دقیقاً همان
  //: چیزی است که این کوچ برای حذفش انجام شد — و بی‌صدا هم اتفاق می‌افتد.
  const ADMIN_KEYS = ['accounts', 'mpcommission', 'assuranceadmin', 'billing']

  const EVERY_MODULE = [
    ...BASE,
    'assurance_work',
    'manufacturing',
    'integration',
    'banking',
    'payroll',
    'fixedassets',
    'calendar',
  ]

  it('با هر ترکیبی از ماژول‌ها و نقش‌ها، هیچ منوی مدیریتی‌ای نیست', () => {
    for (const modules of [BASE, EVERY_MODULE, []]) {
      for (const kind of ['standard', 'distributor', 'retailer']) {
        for (const isOwner of [false, true]) {
          const { groups, secondary } = buildNav({
            tenantKind: kind,
            enabledModules: modules,
            allowedModules: modules,
            isOwner,
          })
          const found = uniqueNavItems(groups, secondary).map((i) => i.key as string)
          for (const key of ADMIN_KEYS) {
            expect(found, `${key} با ${kind}/${modules.length} ماژول برگشت`).not.toContain(key)
          }
          expect(groups.map((g) => g.heading)).not.toContain('مدیریت سامانه')
        }
      }
    }
  })
})

describe('fail-openِ عمومیِ گیت', () => {
  it('کلیدِ ثبت‌نشده برای همه دیده می‌شود — همان چیزی که این تست می‌پاید', () => {
    //: این رفتارِ *موجود* است و عمدی (ناوبریِ سیستمی نباید با فیلتر ناپدید شود).
    //: تست وجود دارد تا اگر کسی کلیدِ تازه‌ای اضافه کرد و ثبتش نکرد، بداند
    //: نتیجه‌اش «دیده‌شدن» است نه «پنهان‌شدن».
    expect(PAGE_MODULE_KEY['profile' as PageKey]).toBeUndefined()
    expect(keys(BASE).has('profile')).toBe(true)
  })
})

describe('ترتیبِ منو در هر حالت — UI-01 §۵۲', () => {
  const MODES: ExperienceMode[] = ['accountant', 'simple']
  const EVERY = [
    ...BASE, 'assurance_work', 'manufacturing', 'integration', 'banking', 'payroll', 'fixedassets', 'calendar',
  ]
  const headings = (mode: ExperienceMode, modules: string[] = EVERY) =>
    orderNavGroups(nav(modules).groups, mode).map((g) => g.heading)

  //: شناسه‌ی غلط این‌جا خطا نمی‌دهد: گروهِ ناشناخته فقط رتبه‌ی آخر می‌گیرد و مقصدِ
  //: ناشناخته بی‌صدا به پیش‌فرض برمی‌گردد. پس باید صریح سنجیده شود.
  it.each(MODES)('هر نامِ گروه و هر مقصدِ «%s» واقعاً در منو هست', (mode) => {
    const byHeading = new Map(NAV_GROUPS.map((g) => [g.heading, g]))
    for (const h of MODE_GROUP_ORDER[mode]) expect(byHeading.has(h), h).toBe(true)
    for (const [h, key] of Object.entries(MODE_GROUP_LANDING[mode])) {
      expect(byHeading.get(h)?.items.map((i) => i.key), `${h} ← ${key}`).toContain(key)
    }
  })

  it('حسابدار: حسابداری و دریافت و پرداخت بلافاصله بعد از داشبورد', () => {
    expect(headings('accountant').slice(0, 3)).toEqual(['میزکار', 'حسابداری', 'دریافت و پرداخت'])
  })

  it('ساده: همان ترتیبِ قبلی، بی هیچ جابه‌جایی', () => {
    expect(headings('simple')).toEqual(nav(EVERY).groups.map((g) => g.heading))
  })

  it('بقیه‌ی گروه‌ها در حالتِ حسابدار ترتیبِ نسبیِ خودشان را نگه می‌دارند', () => {
    const moved = new Set(MODE_GROUP_ORDER.accountant)
    const rest = (mode: ExperienceMode) => headings(mode).filter((h) => !moved.has(h))
    expect(rest('accountant')).toEqual(rest('simple'))
  })

  it('**حالت ≠ مجوز** — با هر ترکیبِ ماژول و نوعِ حساب، هر دو حالت دقیقاً همان صفحه‌ها را نشان می‌دهند', () => {
    const snapshot = (groups: ReturnType<typeof nav>['groups']) =>
      groups.map((g) => `${g.heading}:${g.items.map((i) => i.key).join(',')}`).sort()
    for (const modules of [BASE, EVERY, [], ['overview', 'contacts', 'reports']]) {
      for (const kind of ['standard', 'distributor', 'retailer']) {
        for (const isOwner of [false, true]) {
          const { groups } = buildNav({ tenantKind: kind, enabledModules: modules, allowedModules: modules, isOwner })
          const label = `${kind}/${modules.length}/${isOwner}`
          expect(snapshot(orderNavGroups(groups, 'accountant')), label).toEqual(snapshot(groups))
          expect(snapshot(orderNavGroups(groups, 'simple')), label).toEqual(snapshot(groups))
        }
      }
    }
  })

  it('بی ماژولِ حسابداری، حالتِ حسابدار گروهی را که نیست نمی‌سازد', () => {
    //: `reports` هم بیرون است: صفحه‌ی «گزارش‌ها» در همین گروه است و ماژولِ خودش را
    //: دارد، پس با آن گروه با یک صفحه زنده می‌ماند.
    const h = headings('accountant', ['overview', 'contacts', 'banking'])
    expect(h).not.toContain('حسابداری')
    expect(h.slice(0, 2)).toEqual(['میزکار', 'دریافت و پرداخت'])
  })

  it('کلیک روی «حسابداری»: حسابدار به سند می‌رود، ساده به پیش‌فرض', () => {
    const acct = nav(EVERY).groups.find((g) => g.heading === 'حسابداری')!
    expect(groupLanding(acct, 'accountant')).toBe('journalentry')
    expect(groupLanding(acct, 'simple')).toBeUndefined()
  })

  it('مقصدی که این کسب‌وکار نمی‌بیند انتخاب نمی‌شود — به پیش‌فرض برمی‌گردد', () => {
    const acct = NAV_GROUPS.find((g) => g.heading === 'حسابداری')!
    const withoutJournal = { ...acct, items: acct.items.filter((i) => i.key !== 'journalentry') }
    expect(groupLanding(withoutJournal, 'accountant')).toBeUndefined()
  })
})

describe('«مجوز نرم‌افزار» فقط در کوبیتا سازمانی', () => {
  it('در بیلدِ ابری (بی‌cubitaConfig) هیچ‌جای منو نیست', () => {
    const { groups, secondary } = buildNav({ tenantKind: 'standard', isOwner: true })
    const keys = [...groups.flatMap((g) => g.items), ...secondary].map((i) => i.key)
    expect(keys).not.toContain('license')
  })
})

describe('بازچینیِ منوهای حسابداری — ۱۴۰۵/۰۷/۰۳', () => {
  const accounting = NAV_GROUPS.find((g) => g.heading === 'حسابداری')!
  //: ترتیبِ دسته‌ها از ۱۴۰۵/۰۷/۰۶: کارِ هرروزه اول، ساختار ته.
  const SECTIONS = ['ثبت سند', 'بازبینی اسناد', 'گزارش و کنترل', 'اصلاح و تعدیل', 'پایان دوره', 'ساختار و تعریف‌ها']

  it('شش دسته به ترتیبِ کار، هر ردیف در یک دسته و ردیف‌های هم‌دسته پشتِ هم', () => {
    expect(accounting.items.every((i) => i.section)).toBe(true)
    expect(navSections(accounting.items).map((s) => s.title)).toEqual(SECTIONS)
    //: پشتِ هم: هر دسته فقط یک بار «شروع» می‌شود.
    const starts = accounting.items.filter((it, i) => it.section !== accounting.items[i - 1]?.section)
    expect(starts).toHaveLength(SECTIONS.length)
  })

  it('منوی ادغام‌شده برنمی‌گردد — نه در منو، نه در فهرست', () => {
    const menu = new Set(NAV_GROUPS.flatMap((g) => g.items.map((i) => i.key as string)))
    const lists = new Set(Object.values(LIST_MENUS).flatMap((m) => m.map((i) => i.key as string)))
    for (const old of Object.keys(LEGACY_PAGES)) {
      expect(menu.has(old), old).toBe(false)
      expect(lists.has(old), old).toBe(false)
      expect(old in OPS_LIST_MAP, old).toBe(false)
    }
  })

  it('هیچ دو منوی حسابداری هم‌نام نیستند', () => {
    const labels = accounting.items.map((i) => i.label)
    expect(new Set(labels).size).toBe(labels.length)
  })

  it('هر کلیدِ قدیمی به صفحه‌ای می‌رود که واقعاً در منوست', () => {
    const menu = new Set(NAV_GROUPS.flatMap((g) => g.items.map((i) => i.key)))
    for (const [old, to] of Object.entries(LEGACY_PAGES)) expect(menu.has(to.page), `${old} → ${to.page}`).toBe(true)
  })

  it('مسیرِ قدیمی به جای تازه، بقیه دست‌نخورده', () => {
    expect(resolveLegacyPage('finalizeentries')).toEqual({ page: 'entrycartable', section: null })
    expect(resolveLegacyPage('generaldoc', 'x')).toEqual({ page: 'balancereport', section: 'general' })
    expect(resolveLegacyPage('newaccount')).toEqual({ page: 'acctchart', section: 'new' })
    expect(resolveLegacyPage('inventory', 'count')).toEqual({ page: 'inventory', section: 'count' })
  })
})

describe('navSections', () => {
  it('دسته‌ها به ترتیبِ اولین ظهور، ردیف‌ها به ترتیبِ خودشان — حتی اگر درهم آمده باشند', () => {
    const out = navSections<{ k: number; section?: string }>([
      { k: 1, section: 'الف' },
      { k: 2, section: 'ب' },
      { k: 3, section: 'الف' },
    ])
    expect(out.map((s) => [s.title, s.items.map((i) => i.k)])).toEqual([
      ['الف', [1, 3]],
      ['ب', [2]],
    ])
  })

  it('گروهِ بی‌دسته یک دسته‌ی بی‌نام است', () => {
    expect(navSections<{ k: number; section?: string }>([{ k: 1 }, { k: 2 }])).toEqual([{ title: null, items: [{ k: 1 }, { k: 2 }] }])
  })
})

describe('مرتب‌سازیِ زیرمنوها — ۱۴۰۵/۰۷/۰۶', () => {
  const group = (h: string) => NAV_GROUPS.find((g) => g.heading === h)
  const DEFINITION_TITLES = new Set(['تعریف‌ها', 'ساختار و تعریف‌ها'])

  it('«شرکت» دیگر نیست و هر صفحه‌اش به ماژولِ داده‌ی خودش رفته', () => {
    expect(group('شرکت')).toBeUndefined()
    const home: Record<string, PageKey[]> = {
      'مشتریان و فروش': ['contactnew', 'contactgroup', 'geo', 'installments', 'contactimport'],
      'دریافت و پرداخت': ['ownertxn'],
      'حسابداری': ['costcenter', 'openingops', 'yearendops', 'yearendreminder'],
      'گزارش و ابزار': ['mgmtreports', 'reportbuilder', 'dayactivity', 'usagereport', 'calendar', 'dataexport', 'dataimport'],
    }
    for (const [h, pages] of Object.entries(home)) {
      const keys = group(h)!.items.map((i) => i.key)
      for (const p of pages) expect(keys, `${p} ← ${h}`).toContain(p)
    }
  })

  it('گروهِ بلند (بیش از هشت کار) دسته‌بندی شده، دسته‌ها پشتِ هم و تعریف‌ها همیشه آخر', () => {
    for (const g of NAV_GROUPS) {
      const work = g.items.filter((i) => !i.guide)
      if (work.length <= 8) continue
      expect(work.every((i) => i.section), g.heading).toBe(true)
      const titles = navSections(work).map((s) => s.title!)
      //: پشتِ هم: هر دسته فقط یک بار شروع می‌شود.
      const starts = work.filter((it, i) => it.section !== work[i - 1]?.section)
      expect(starts, g.heading).toHaveLength(titles.length)
      const defs = titles.findIndex((t) => DEFINITION_TITLES.has(t))
      if (defs !== -1) expect(defs, g.heading).toBe(titles.length - 1)
    }
  })

  it('همین قاعده برای منوهای کار‌به‌کار و فهرست', () => {
    for (const [h, menu] of [...Object.entries(OPS_MENUS), ...Object.entries(LIST_MENUS)]) {
      if (menu.length <= 8) continue
      expect(menu.every((e) => e.category), h).toBe(true)
      const titles = menuCategories(menu).map((c) => c.title!)
      const starts = menu.filter((e, i) => e.category !== menu[i - 1]?.category)
      expect(starts, h).toHaveLength(titles.length)
      const defs = titles.findIndex((t) => DEFINITION_TITLES.has(t))
      if (defs !== -1) expect(defs, h).toBe(titles.length - 1)
    }
  })

  it('در هیچ ماژولی دو ردیف هم‌نام نیست — نه دو عملیات، نه عملیات و دفترش', () => {
    for (const g of NAV_GROUPS) {
      //: گروهی که منوی کار‌به‌کار دارد («تامین‌کنندگان و انبار») ردیف‌های صفحه‌اش را نشان نمی‌دهد.
      const ops = (OPS_MENUS[g.heading] ?? g.items).map((e) => e.label)
      expect(new Set(ops).size, g.heading).toBe(ops.length)
      const lists = (LIST_MENUS[g.heading] ?? []).map((e) => e.label)
      expect(new Set(lists).size, g.heading).toBe(lists.length)
      //: گروهِ تک‌صفحه‌ای که نامِ خودش را دارد («تولید» ← «تولید») استثناست — آن ردیف تکرارِ سرتیتر است.
      for (const l of lists) expect(ops, `${g.heading}: «${l}»`).not.toContain(l)
    }
  })

  it('در هیچ ماژولی دو ردیف یک آیکن ندارند', () => {
    const typeOf = (n: unknown) => (n as { type?: unknown })?.type
    for (const g of NAV_GROUPS) {
      const items = uniqueNavItems([g])
      const icons = items.map((i) => typeOf(i.icon))
      expect(new Set(icons).size, g.heading).toBe(icons.length)
    }
    for (const [h, menu] of [...Object.entries(OPS_MENUS), ...Object.entries(LIST_MENUS)]) {
      const icons = menu.map((e) => e.icon)
      expect(new Set(icons).size, h).toBe(icons.length)
    }
  })

  it('ترجیح‌های شخصی و راهنما در منوی کاربرند، نه در «تنظیمات»', () => {
    const personal: PageKey[] = ['password', 'theme', 'shortcuts', 'help']
    const settings = group('تنظیمات')!.items.map((i) => i.key)
    const { secondary } = nav(BASE)
    for (const k of personal) {
      expect(settings, k).not.toContain(k)
      expect(secondary.map((i) => i.key), k).toContain(k)
    }
  })

  it('صفحه‌های آمده به «حسابداری» و «دریافت و پرداخت» گروه را بی ماژولش زنده نگه نمی‌دارند', () => {
    //: `reports` بیرون است، همان دلیلِ تستِ ترتیب: «گزارش‌ها» ماژولِ خودش را دارد و گروه را زنده نگه می‌دارد.
    const headings = (modules: string[]) => nav(modules).groups.map((g) => g.heading)
    expect(headings(['overview', 'contacts', 'banking'])).not.toContain('حسابداری')
    expect(headings(['overview', 'contacts', 'accounting'])).not.toContain('دریافت و پرداخت')
  })

  it('کلیک روی نامِ ماژول به اولین کار می‌رود، نه به «مسیرِ کار»', () => {
    expect(groupEntry(group('مشتریان و فروش')!).key).toBe('salesinvoice')
    expect(groupEntry(group('دریافت و پرداخت')!).key).toBe('receiptvoucher')
    expect(groupEntry(group('حقوق و دستمزد')!).key).toBe('payroll')
  })

  it('نامِ روی نوار: گروهِ ذاتاً تک‌صفحه نامِ صفحه، گروهِ فیلترشده نامِ خودش', () => {
    expect(groupBarLabel(group('میزکار')!)).toBe('داشبورد')
    expect(groupBarLabel(group('دارایی ثابت')!)).toBe('دارایی ثابت')
    //: پیش از تأییدِ قرارداد فقط «درخواست» دیده می‌شود؛ نوار باز هم «حسابرسی» می‌گوید.
    const assurance = nav(BASE).groups.find((g) => g.heading === 'حسابرسی')!
    expect(assurance.items).toHaveLength(1)
    expect(groupBarLabel(assurance)).toBe('حسابرسی')
  })
})

describe('منوی یک‌فهرستیِ ماژول — دفتر زیرِ دسته‌ی کارش (۱۴۰۵/۰۷/۰۶)', () => {
  //: دسته‌ای که فقط دفتر دارد عمدی است و این‌جا نام برده می‌شود؛ غلطِ تایپی در `category` بی‌صدا دسته‌ی تازه می‌ساخت.
  const LIST_ONLY: Record<string, string[]> = { 'تامین‌کنندگان و انبار': ['موجودی'] }
  const merged = (heading: string) => {
    const g = NAV_GROUPS.find((x) => x.heading === heading)!
    const ops: { title: string | null; items: unknown[] }[] = OPS_MENUS[heading]
      ? menuCategories(OPS_MENUS[heading])
      : navSections(g.items)
    return mergeMenu(ops, menuCategories(LIST_MENUS[heading] ?? []), (t) => DEFINITION_TITLES.has(t))
  }

  it('در ماژولِ دسته‌دار هر دفتر دسته دارد، دسته‌ی فقط-دفتر همان فهرستِ عمدی است، و تعریف‌ها ته‌اند', () => {
    for (const g of NAV_GROUPS) {
      const lists = LIST_MENUS[g.heading] ?? []
      const ops = OPS_MENUS[g.heading] ? menuCategories(OPS_MENUS[g.heading]) : navSections(g.items)
      if (lists.length === 0 || ops.every((c) => c.title === null)) continue
      expect(lists.every((e) => e.category), g.heading).toBe(true)
      const m = merged(g.heading)
      expect(m.filter((c) => c.title && c.ops.length === 0).map((c) => c.title), g.heading).toEqual(LIST_ONLY[g.heading] ?? [])
      const titles = m.map((c) => c.title ?? '')
      const defs = titles.findIndex((t) => DEFINITION_TITLES.has(t))
      if (defs !== -1) expect(titles.slice(defs).every((t) => DEFINITION_TITLES.has(t)), g.heading).toBe(true)
    }
  })

  it('نمونه‌ها: «اسناد حسابداری» زیرِ «ثبت سند»، «عملیات چک» زیرِ «چک»، «فاکتورهای فروش» زیرِ «کار روزانه»', () => {
    const where = (heading: string, label: string) =>
      merged(heading).find((c) => c.lists.some((e) => e.label === label))?.title
    expect(where('حسابداری', 'اسناد حسابداری')).toBe('ثبت سند')
    expect(where('دریافت و پرداخت', 'عملیات چک')).toBe('چک')
    expect(where('مشتریان و فروش', 'فاکتورهای فروش')).toBe('کار روزانه')
    expect(where('مشتریان و فروش', 'سرنخ‌ها')).toBe('باشگاه مشتریان')
  })
})
