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
  NAV_GROUPS,
  PAGE_MODULE_KEY,
  buildNav,
  groupLanding,
  menuEntryVisible,
  orderNavGroups,
  uniqueNavItems,
  type PageKey,
} from './navModel'
import type { ExperienceMode } from './experienceMode'

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
