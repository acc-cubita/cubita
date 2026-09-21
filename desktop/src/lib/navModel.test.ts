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

import { PAGE_MODULE_KEY, buildNav, menuEntryVisible, uniqueNavItems, type PageKey } from './navModel'

//: صفحه‌ی عملیاتِ کاری — در `NAV_GROUPS` است، پس با فیلترِ ناوبری سنجیده می‌شود.
const WORK_OPS: PageKey = 'assurancehealth'
//: دفترها ردیفِ منوی اصلی ندارند؛ دیده‌شدنشان را `menuEntryVisible` تعیین می‌کند
//: (همان چیزی که `ModulePanels` و کشوی موبایل صدا می‌زنند).
const WORK_LISTS: PageKey[] = ['assurancefindinglist', 'assurancerunlist']

const nav = (allowed: string[], enabled?: string[]) =>
  buildNav({
    isPlatformAdmin: false,
    isSuperAdmin: false,
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

  it('کارتابلِ ستاد از NAV_GROUPS نمی‌آید — پس گیتِ ماژول شاملش نیست', () => {
    //: `assuranceadmin` در `SUPER_ADMIN_NAV_ITEMS` است و با `is_super_admin`
    //: گیت می‌شود، نه با ماژول. آمدنش این‌جا یعنی جای اشتباهی ثبت شده.
    expect(keys([...BASE, 'assurance_work']).has('assuranceadmin')).toBe(false)
    const asSuper = buildNav({
      isPlatformAdmin: false,
      isSuperAdmin: true,
      tenantKind: 'standard',
      enabledModules: BASE,
      allowedModules: BASE,
    })
    const superKeys = uniqueNavItems(asSuper.groups, asSuper.secondary).map((i) => i.key)
    expect(superKeys).toContain('assuranceadmin')
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
