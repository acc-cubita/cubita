/**
 * چه نقشی چه می‌بیند.
 *
 * نقش‌های این تست **کپیِ واقعیِ** `DEFAULT_ROLES` در
 * `backend/app/models/user.py` هستند. اگر روزی مجوزی آنجا عوض شود و اینجا نه،
 * این تست‌ها همان جایی‌اند که اختلاف را نشان می‌دهند — وگرنه فرق بین «کاربر
 * می‌بیند» و «سرور اجازه می‌دهد» بی‌صدا باز می‌شود و به‌شکلِ ۴۰۳ روی گوشیِ
 * کاربر ظاهر می‌شود.
 */
import type { Me } from '../../api/types'
import { canAccess, canSeeMarket, hasNoContent } from '../access'

type Perms = Record<string, string[]>

/** مجوزهای واقعیِ نقش‌ها — برداشته از DEFAULT_ROLES بک‌اند. */
const ROLES: Record<string, Perms> = {
  owner: { '*': ['view', 'create', 'update', 'delete', 'approve'] },
  accountant: {
    accounting: ['view', 'create', 'update', 'approve'],
    invoices: ['view', 'create', 'update'],
    checks_bank: ['view', 'create', 'update'],
    payroll: ['view'],
    assets: ['view', 'create', 'update', 'approve'],
    moadian: ['view', 'approve'],
    calendar: ['view', 'create', 'update', 'delete'],
    crm: ['view'],
    manufacturing: ['view', 'create', 'update'],
  },
  salesperson: {
    invoices: ['view', 'create'],
    inventory: ['view'],
    calendar: ['view', 'create', 'update'],
    crm: ['view', 'create', 'update'],
  },
  warehouse_keeper: {
    inventory: ['view', 'create', 'update'],
    calendar: ['view', 'create', 'update'],
    manufacturing: ['view', 'create', 'update'],
  },
  delivery_agent: { marketplace: ['view', 'deliver'] },
  payroll_officer: { payroll: ['view', 'create', 'update', 'approve'], calendar: ['view'] },
  // حسابِ دمو — رمزش روی سایتِ عمومی نمایش داده می‌شود، پس گیتش واقعاً مهم است.
  demo: {
    accounting: ['view'],
    invoices: ['view'],
    inventory: ['view'],
    checks_bank: ['view'],
    payroll: ['view'],
    assets: ['view'],
    calendar: ['view'],
    crm: ['view'],
    manufacturing: ['view'],
  },
}

const me = (role: keyof typeof ROLES, tenantKind = 'standard'): Me =>
  ({
    role_key: role,
    role_name: role,
    permissions: ROLES[role],
    tenant_kind: tenantKind,
  }) as unknown as Me

describe('مالک همه‌چیز را می‌بیند', () => {
  it.each(['dashboard', 'reports', 'contacts', 'newInvoice', 'treasury', 'stock'] as const)(
    '%s',
    (area) => {
      expect(canAccess(me('owner'), area)).toBe(true)
    },
  )
})

describe('حسابدار', () => {
  it('داشبورد، گزارش، اشخاص، فاکتور و خزانه را می‌بیند', () => {
    const u = me('accountant')
    expect(canAccess(u, 'dashboard')).toBe(true)
    expect(canAccess(u, 'reports')).toBe(true)
    expect(canAccess(u, 'contacts')).toBe(true)
    expect(canAccess(u, 'newInvoice')).toBe(true)
    expect(canAccess(u, 'treasury')).toBe(true)
  })
})

describe('فروشنده', () => {
  it('فاکتور و اشخاص را می‌بیند', () => {
    // «اشخاص» با مجوزِ invoices باز می‌شود، نه contacts — قاعده‌ی بک‌اند.
    expect(canAccess(me('salesperson'), 'contacts')).toBe(true)
    expect(canAccess(me('salesperson'), 'newInvoice')).toBe(true)
  })

  it('داشبورد و گزارش را نمی‌بیند — accounting ندارد', () => {
    // این همان موردی است که پیش از نقش‌محوری ۴۰۳ می‌داد.
    expect(canAccess(me('salesperson'), 'dashboard')).toBe(false)
    expect(canAccess(me('salesperson'), 'reports')).toBe(false)
  })

  it('خزانه را نمی‌بیند — checks_bank ندارد', () => {
    expect(canAccess(me('salesperson'), 'treasury')).toBe(false)
  })

  it('تبِ انبارگردانی نمی‌گیرد — inventory دارد ولی فقط view', () => {
    // اینجا عمداً `update` سنجیده می‌شود نه `view`. با `view` فروشنده تبی
    // می‌گرفت که همه‌ی دکمه‌هایش خاموش است — همان تبِ ۴۰۳‌دهنده‌ی پیش از فازِ ۲.
    expect(canAccess(me('salesperson'), 'stock')).toBe(false)
  })
})

describe('انباردار', () => {
  it('بخش‌های مالی/فروش را نمی‌بیند', () => {
    const u = me('warehouse_keeper')
    for (const area of ['dashboard', 'reports', 'contacts', 'newInvoice', 'treasury'] as const) {
      expect(canAccess(u, area)).toBe(false)
    }
  })

  it('انبارگردانی را می‌بیند', () => {
    expect(canAccess(me('warehouse_keeper'), 'stock')).toBe(true)
  })

  it('دیگر صفحه‌ی «هنوز آماده نیست» نمی‌گیرد', () => {
    // پیش از فازِ ۴ این `true` بود و همان یافته دلیلِ وجودِ آن فاز شد: اپ برای
    // نقشی که کارش کاملاً میدانی است هیچ محتوایی نداشت.
    expect(hasNoContent(me('warehouse_keeper'))).toBe(false)
  })
})

describe('مأمورِ حمل', () => {
  it('فقط بازار را می‌بیند، و فقط اگر کسب‌وکارِ بازاری باشد', () => {
    expect(canSeeMarket(me('delivery_agent', 'distributor'))).toBe(true)
    expect(canSeeMarket(me('delivery_agent', 'standard'))).toBe(false)
  })

  it('تحویل می‌زند ولی تأیید/رد/گفتگو نه', () => {
    // اینها دقیقاً همان دکمه‌هایی بودند که تا پیش از این نشانش داده می‌شدند و
    // روی هرکدام ۴۰۳ می‌گرفت. مجوزش فقط marketplace:[view, deliver] است.
    const u = me('delivery_agent', 'distributor')
    expect(canAccess(u, 'marketDeliver')).toBe(true)
    expect(canAccess(u, 'marketApprove')).toBe(false)
    expect(canAccess(u, 'marketManage')).toBe(false)
    expect(canAccess(u, 'marketChat')).toBe(false)
  })

  it('وقتی بازار دارد، صفحه‌ی «هنوز آماده نیست» نمی‌گیرد', () => {
    expect(hasNoContent(me('delivery_agent', 'distributor'))).toBe(false)
    expect(hasNoContent(me('delivery_agent', 'standard'))).toBe(true)
  })
})

describe('مسئولِ حقوق', () => {
  it('اپِ موبایل هنوز چیزی برایش ندارد', () => {
    // تنها نقشی که بعد از فازِ ۴ هم دستِ خالی می‌ماند.
    expect(hasNoContent(me('payroll_officer'))).toBe(true)
    expect(canAccess(me('payroll_officer'), 'stock')).toBe(false)
  })
})

describe('حسابِ دمو (فقط مشاهده)', () => {
  it('می‌بیند ولی نمی‌تواند ثبت کند', () => {
    const u = me('demo')
    expect(canAccess(u, 'dashboard')).toBe(true)
    expect(canAccess(u, 'reports')).toBe(true)
    expect(canAccess(u, 'contacts')).toBe(true)
    // این‌ها مهم‌ترین‌اند: رمزِ این حساب عمومی است و نباید بتواند چیزی ثبت کند.
    expect(canAccess(u, 'newInvoice')).toBe(false)
    expect(canAccess(u, 'treasury')).toBe(false)
    // انبارگردانی سندِ حسابداری می‌سازد — حسابِ دمو مطلقاً نباید بتواند.
    expect(canAccess(u, 'stock')).toBe(false)
  })
})

describe('حالت‌های مرزی', () => {
  it('کاربرِ ناشناخته هیچ دسترسی ندارد', () => {
    expect(canAccess(null, 'dashboard')).toBe(false)
    expect(canSeeMarket(null)).toBe(false)
    expect(hasNoContent(null)).toBe(false) // هنوز وارد نشده — نه اینکه دسترسی ندارد
  })

  it('مالک با اکشنِ approve هم می‌تواند تحویل بزند', () => {
    // بازتابِ require_permission("marketplace", ("deliver", "approve")) — تنها
    // جای اپ که چند اکشنِ جایگزین دارد. مالک اصلاً اکشنِ deliver ندارد.
    expect(canAccess(me('owner', 'distributor'), 'marketDeliver')).toBe(true)
  })

  it('فروشنده تحویل نمی‌زند — هیچ‌کدام از دو اکشن را ندارد', () => {
    expect(canAccess(me('salesperson'), 'marketDeliver')).toBe(false)
  })

  it('مالکِ کسب‌وکارِ غیرِ بازاری، تبِ بازار را نمی‌بیند', () => {
    // مجوزِ * دارد ولی بازار برایش بی‌معنی است — دو شرطِ جدا.
    expect(canSeeMarket(me('owner', 'standard'))).toBe(false)
    expect(canSeeMarket(me('owner', 'distributor'))).toBe(true)
  })
})
