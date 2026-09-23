import { isValidElement, type ReactElement, type ReactNode } from 'react'
import { Circle, type LucideIcon } from 'lucide-react'

import { buildNav, menuEntryVisible, type PageKey } from './navModel'
import { TASK_LAUNCHERS } from './taskRegistry'
import type { ExperienceMode } from './experienceMode'
import { LIST_MENUS, OPS_MENUS } from '../components/moduleLists'
import { MODULE_SECTIONS, listSections, opsSections } from '../components/moduleSections'
import type { MeResponse } from '../api'

/**
 * کاتالوگِ «هر کارتی که می‌شود روی داشبورد گذاشت».
 *
 * **چرا این‌جا و نه یک فهرستِ تازه:** همان چیزی که کاربر در دو کارتِ کنارِ سایدبار
 * می‌بیند («عملیات» و «فهرست»، `ModulePanels`) باید در انتخاب‌گرِ داشبورد هم همان
 * باشد. پس این ماژول *هیچ* منویی تعریف نمی‌کند؛ فقط همان چهار منبعِ موجود را
 * می‌خوانَد و تخت می‌کند:
 *
 * - `NAV_GROUPS` (از `buildNav`، گیت‌شده با ماژول و نقش) — صفحه‌ها
 * - `MODULE_SECTIONS` — تب‌های هر صفحه‌ی تب‌دار
 * - `OPS_MENUS` — گروهی که منوی عملیاتش کار‌به‌کار است نه صفحه‌به‌صفحه
 * - `LIST_MENUS` — دفترهای هر گروه
 *
 * منویی که فردا به هر کدام اضافه شود، بی‌هیچ کاری این‌جا هم می‌آید.
 */

export type LaunchKind = 'ops' | 'list'

/** آیکنِ منبع دو شکل دارد: `NAV_GROUPS` عنصرِ آماده می‌دهد، بقیه خودِ کامپوننت را. */
export type LaunchIconSource = LucideIcon | ReactElement

export interface LaunchTarget {
  /** `page` یا `page/section` — همان چیزی که روی سرور ذخیره می‌شود. */
  id: string
  label: string
  /** نامِ صفحه‌ی میزبان، وقتی برچسب یک تب است و به‌تنهایی مبهم می‌ماند. */
  parent?: string
  /** نامِ گروهِ ناوبری — خطِ دومِ کارت و سرفصلِ انتخاب‌گر. */
  group: string
  kind: LaunchKind
  page: PageKey
  section?: string
  icon: LaunchIconSource
}

export interface LaunchGroup {
  heading: string
  icon?: ReactNode
  items: LaunchTarget[]
}

export const targetId = (page: PageKey, section?: string) => (section ? `${page}/${section}` : page)

/** نامِ صفحه‌ی میزبان برای خطِ دومِ یک تب — فقط وقتی چیزِ تازه‌ای می‌گوید.
 *  «باشگاه مشتریان / باشگاه مشتریان» فقط تکرار است. */
const hostLabel = (page: string, section: string) => (page === section ? undefined : page)

//: کارتی که به خودِ داشبورد می‌برد بی‌معناست — کاربر همین حالا آن‌جاست.
const NOT_A_CARD = new Set<PageKey>(['overview'])

/** `NavItem.icon` از نوعِ `ReactNode` است (هرچه باشد)، ولی در عمل همیشه یک عنصرِ
 *  آیکون است. این گارد فقط تایپ را صادق نگه می‌دارد. */
const asIcon = (icon: ReactNode): LaunchIconSource => (isValidElement(icon) ? (icon as ReactElement) : Circle)

/**
 * کارت‌هایی که کاربرِ بدونِ انتخاب می‌بیند — **بسته به حالتِ تجربه‌اش.**
 *
 * فهرست‌ها از §۵۳ی تسکِ UI-01 آمده‌اند. پیش از این یک فهرستِ ثابت بود (شش
 * لانچرِ `TASK_LAUNCHERS`)؛ همان شش‌تا برای حسابداری که روزش با سند و تراز می‌گذرد و
 * برای فروشنده‌ای که فقط فاکتور می‌بُرد.
 *
 * **حالت فقط *پیش‌فرض* را تعیین می‌کند.** کسی که کارت‌هایش را خودش چیده
 * (`dashboard_cards` پُر) با عوض‌کردنِ حالت چیدمانش را از دست نمی‌دهد؛ حالت فقط
 * برای کسی مهم است که هنوز انتخابی نکرده. و چون `resolveCards` هر شناسه‌ای را که
 * کاربر به آن دسترسی ندارد کنار می‌گذارد، این فهرست **مجوز نمی‌دهد** — حالت ≠ مجوز.
 *
 * هر شناسه به صفحه‌ای موجود می‌رسد؛ تستِ `launchers.test.ts` این را قفل کرده، چون
 * شناسه‌ی غلط این‌جا خطا نمی‌دهد — بی‌صدا حذف می‌شود و داشبورد یک کارت کم دارد.
 *
 * سه نگاشت که از خودِ نامِ §۵۳ پیدا نیستند و در کد سنجیده شدند:
 * * «دفتر روزنامه» ← `ledgerreport`: آن صفحه با `useState<Book>('journal')` روی
 *   دفترِ روزنامه باز می‌شود. (`ebooks` هم‌نامش نیست؛ «دفاتر تجارت الکترونیک» است.)
 * * «سود» ← `reports`: تب‌های آن صفحه پیوندِ مستقیم ندارند، ولی اولین و پیش‌فرضش
 *   «سود و زیان» است.
 * * «بدهکاران» و «طلبکاران» ← **یک** کارتِ `contacts/aging`: آن صفحه هر دو را با
 *   یک کلید نشان می‌دهد و پیوندی به نمای بدهی ندارد. دو کارت به یک مقصد قاعده‌ی
 *   «هر شناسه یکتاست»ِ همین کاتالوگ را می‌شکست، پس حالتِ ساده هفت کارت دارد نه هشت.
 */
export const MODE_DEFAULT_CARDS: Record<ExperienceMode, readonly string[]> = {
  accountant: [
    'journalentry', //    ثبت سند
    'ledgerreport', //    دفتر روزنامه
    'accountbrowse', //   مرور حساب
    'balancereport', //   تراز آزمایشی
    'contactoverview', // طرف حساب
    'bankreconcile', //   مغایرت‌ها
    'assurancehealth', // هشدار حسابرسی
    'checkoplist', //     چک‌ها
  ],
  simple: [
    'salesinvoice', //       فروش
    'purchases/invoices', // خرید
    'receiptvoucher', //     دریافت
    'paymentvoucher', //     پرداخت
    'inventory/stock', //    موجودی
    'reports', //            سود
    'contacts/aging', //     بدهکاران و طلبکاران
  ],
}

/** توضیحِ خطِ دومِ کارت، فقط برای لانچرهایی که توضیحِ نوشته‌شده دارند. */
const TASK_HINTS = new Map(TASK_LAUNCHERS.map((t) => [targetId(t.page, t.section), t.desc]))

/**
 * خطِ دومِ کارت: توضیحِ لانچر اگر بود، وگرنه جایی که این کارت از آن می‌آید.
 *
 * برای دفترها «فهرست» هم می‌آید، چون عملیات و فهرستِ نظیرش گاهی **هم‌نام**اند
 * («محل‌های جغرافیایی» هم فرمِ ثبت است و هم دفترِ ثبت‌شده‌ها). بدونِ این، دو کارتِ
 * یکسان روی داشبورد می‌نشست و کاربر باید حدس می‌زد کدام به فرم می‌برد.
 */
export function cardHint(t: LaunchTarget): string {
  const hint = TASK_HINTS.get(t.id)
  if (hint) return hint
  const where = t.parent ? `${t.group} · ${t.parent}` : t.group
  return t.kind === 'list' ? `${where} · فهرست` : where
}

export function buildLaunchers(me: MeResponse): LaunchGroup[] {
  const { groups } = buildNav({
    tenantKind: me.tenant_kind,
    enabledModules: me.enabled_modules,
    allowedModules: me.allowed_modules,
    isOwner: me.role_key === 'owner',
  })

  //: صفحه‌ای که در دو گروه آمده (اعلامیه بدهکار/بستانکار در فروش و در انبار) یک
  //: کارت دارد نه دو تا — همان کاری که `uniqueNavItems` با فهرستِ تخت می‌کند.
  const seen = new Set<string>()
  const out: LaunchGroup[] = []

  for (const g of groups) {
    const items: LaunchTarget[] = []
    const push = (t: LaunchTarget) => {
      if (seen.has(t.id)) return
      seen.add(t.id)
      items.push(t)
    }
    const reachable = (key: PageKey) => menuEntryVisible(key, groups)

    // ── عملیات ───────────────────────────────────────────────────────────
    const opsMenu = OPS_MENUS[g.heading]
    if (opsMenu) {
      for (const e of opsMenu) {
        if (!reachable(e.key)) continue
        push({
          id: targetId(e.key, e.section),
          label: e.label,
          group: g.heading,
          kind: 'ops',
          page: e.key,
          section: e.section,
          icon: e.icon,
        })
      }
    } else {
      for (const it of g.items) {
        if (NOT_A_CARD.has(it.key)) continue
        const own = opsSections(MODULE_SECTIONS[it.key] ?? [])
        //: صفحه‌ای هم‌نامِ گروه که تب دارد، کارتِ خودش را نمی‌گیرد: «انبار ← انبار»
        //: یک سطحِ تکراری است و تب‌هایش همان کار را دقیق‌تر انجام می‌دهند. (همان
        //: تصمیمِ `ModulePanels` برای ردیفِ «والدِ» زائد.)
        //:
        //: و اگر یکی از تب‌هایش **هم‌نامِ خودِ صفحه** باشد (`crm` و تبِ «باشگاه
        //: مشتریان»)، دو ردیفِ هم‌نام در انتخاب‌گر می‌نشست و کاربر باید حدس می‌زد
        //: کدام کدام است. تب دقیق‌تر است و به همان صفحه می‌رود، پس همان می‌ماند.
        const shadowed = own.some((sec) => sec.label === it.label)
        if (!shadowed && !(it.label === g.heading && own.length > 0)) {
          push({
            id: it.key,
            label: it.label,
            group: g.heading,
            kind: 'ops',
            page: it.key,
            icon: asIcon(it.icon),
          })
        }
        for (const s of own) {
          push({
            id: targetId(it.key, s.key),
            label: s.label,
            parent: hostLabel(it.label, s.label),
            group: g.heading,
            kind: 'ops',
            page: it.key,
            section: s.key,
            icon: s.icon,
          })
        }
      }
    }

    // ── فهرست ────────────────────────────────────────────────────────────
    const listMenu = LIST_MENUS[g.heading]
    if (listMenu) {
      for (const e of listMenu) {
        if (!reachable(e.key)) continue
        push({
          id: targetId(e.key, e.section),
          label: e.label,
          group: g.heading,
          kind: 'list',
          page: e.key,
          section: e.section,
          icon: e.icon,
        })
      }
    } else {
      for (const it of g.items) {
        if (NOT_A_CARD.has(it.key)) continue
        for (const s of listSections(MODULE_SECTIONS[it.key] ?? [])) {
          push({
            id: targetId(it.key, s.key),
            label: s.label,
            parent: hostLabel(it.label, s.label),
            group: g.heading,
            kind: 'list',
            page: it.key,
            section: s.key,
            icon: s.icon,
          })
        }
      }
    }

    if (items.length > 0) out.push({ heading: g.heading, icon: g.icon, items })
  }

  return out
}

/** نگاشتِ شناسه → مقصد، برای رسیدنِ سریع از فهرستِ ذخیره‌شده به کارت. */
export function launchIndex(groups: LaunchGroup[]): Map<string, LaunchTarget> {
  return new Map(groups.flatMap((g) => g.items).map((t) => [t.id, t]))
}

/**
 * کارت‌هایی که باید نشان داده شوند.
 *
 * `null` یعنی کاربر هنوز انتخاب نکرده → پیش‌فرض‌های **حالتِ خودش**. `[]` یعنی عمداً
 * خالی گذاشته → هیچ کارتی، در هر دو حالت. شناسه‌ی ناشناخته (ماژولی که خاموش شده،
 * تبی که حذف شده) بی‌صدا کنار می‌رود تا کارتِ مرده‌ای که به جایی نمی‌برد روی داشبورد
 * نماند.
 *
 * `mode` عمداً اجباری است و پیش‌فرض ندارد: پیش‌فرضِ پنهان همان جایی است که یک
 * فراخوانِ تازه بی‌صدا کارت‌های حالتِ اشتباه را نشان می‌داد.
 */
export function resolveCards(
  groups: LaunchGroup[],
  saved: string[] | null,
  mode: ExperienceMode,
): LaunchTarget[] {
  const index = launchIndex(groups)
  const ids = saved ?? MODE_DEFAULT_CARDS[mode]
  return ids.map((id) => index.get(id)).filter((t): t is LaunchTarget => t !== undefined)
}
