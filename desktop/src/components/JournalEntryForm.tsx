import { useId, useState, type KeyboardEvent } from 'react'
import { AlertTriangle, BookOpen, Check, CheckCircle2, ChevronDown, Keyboard, Rows3, Trash2 } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { SearchSelect } from './SearchSelect'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import {
  AddRowButton,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  InputAffix,
  MoreOptions,
  RowAction,
} from './form/FormKit'
import { useJournalEntryDraft, type JournalEntryDraft } from '../lib/journalEntryDraft'
import { useExperienceMode } from '../lib/experienceMode'
import { JournalGrid } from './JournalGrid'
import { openCellPicker } from '../lib/gridPicker'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * فرمِ «ثبت سند حسابداری دستی» — منطق در هوکِ [useJournalEntryDraft].
 *
 * **حالتِ حسابدار یک کارت است:** نوارِ فشرده‌ی سربرگ (شرح، تاریخ، وضعیت، شماره‌ی فرعی
 * در یک ردیف)، گرید، و راهنمای میان‌برها — تا چشم از سربرگ تا اولین ردیف راهی نرود.
 * حالتِ ساده همان دو کارتِ راهنما را دارد (سربرگ با «گزینه‌های بیشتر»، و جدولِ ساده).
 *
 * در هر دو، نوارِ شناورِ پایین ([JournalFooter]) سه عدد و دکمه‌ی ثبت را همیشه جلوی چشم
 * نگه می‌دارد: جمعِ بدهکار، جمعِ بستانکار، و اختلاف با رنگِ توازن — سندی که جمعش نمی‌خواند
 * نباید تا لحظه‌ی زدنِ دکمه پنهان بماند، و حسابدار نباید تفاضل را در ذهن حساب کند.
 */
export function JournalEntryForm({
  token,
  accounts,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  onQueued: () => void
}) {
  const d = useJournalEntryDraft({ token, accounts, onQueued })
  //: **یک پیش‌نویس، دو نما.** هر دو حالت از همین هوک می‌خوانند و همان کلیدهای
  //: `usePersistentState` را دارند، پس عوض‌کردنِ حالت وسطِ ثبت هیچ داده‌ای را
  //: از بین نمی‌برد — نه ردیفی، نه مبلغی (§۳۵). این خاصیتِ طراحی است، نه کدِ
  //: اضافه: چیزی برای «انتقال» وجود ندارد چون حالت اصلاً مالکِ داده نیست.
  const { isAccountant } = useExperienceMode()
  const [keysOpen, setKeysOpenState] = useState(readKeysOpen)
  const setKeysOpen = (open: boolean) => {
    setKeysOpenState(open)
    writeKeysOpen(open)
  }

  if (d.postableAccounts.length === 0) {
    return (
      <SectionCard icon={BookOpen} title="ثبت سند حسابداری">
        <div className="ef-empty">قبل از ثبت سند، یک‌بار «هم‌گام‌سازی» کنید تا چارت حساب در دسترس باشد.</div>
      </SectionCard>
    )
  }

  //: فیلدهای حرفه‌ای و کم‌کاربردِ سربرگ. حسابدار همه را کنارِ هم می‌بیند (همان چیدمانِ
  //: پیشین)؛ حالتِ ساده پشتِ «گزینه‌های بیشتر» جمعشان می‌کند (§۲۹). **هیچ‌کدام در سرور
  //: اجباری نیست** — وضعیت پیش‌فرضِ «موقت» دارد و بقیه اختیاری‌اند — پس پنهان‌کردنشان
  //: ثبتی را نمی‌شکند. تفصیلیِ ردیف، که گاهی اجباری است، این‌جا نیست: در جدولِ ردیف‌ها
  //: می‌ماند و هر وقت لازم شد دیده می‌شود.
  const advancedFields = (
    <>
      <FormField
        label="وضعیت سند"
        tip="موقت: در کارتابل بازبینی می‌شود. دائم: همین حالا قطعی می‌شود و دیگر ادغام یا بازشماره‌گذاری نمی‌شود."
      >
        {(id) => (
          <SearchSelect
            id={id}
            value={d.status}
            onChange={(e) => d.setStatus(e.target.value as 'temporary' | 'permanent')}
          >
            <option value="temporary">موقت — در کارتابل بازبینی شود</option>
            <option value="permanent">دائم — همین حالا قطعی</option>
          </SearchSelect>
        )}
      </FormField>
      <FormField label="شماره فرعی" optional tip="ارجاعِ خودتان: شماره‌ی پرونده، سندِ سیستمِ قبلی یا کدِ دسته.">
        {(id) => (
          <input
            id={id}
            value={d.subNumber}
            onChange={(e) => d.setSubNumber(e.target.value)}
            maxLength={30}
            placeholder="مثلاً: پرونده ۱۴۲"
          />
        )}
      </FormField>
      {d.costCenters.length > 0 && (
        <FormField label="مرکز هزینه / پروژه" optional>
          {(id) => (
            <SearchSelect id={id} value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
              <option value="">— بدون مرکز —</option>
              {d.costCenters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code ? `${c.code} — ${c.name}` : c.name}
                </option>
              ))}
            </SearchSelect>
          )}
        </FormField>
      )}
      {d.analytics.length > 0 && (
        <FormField label="تفصیلی سایر" optional>
          {(id) => (
            <SearchSelect id={id} value={d.analyticId} onChange={(e) => d.setAnalyticId(e.target.value)}>
              <option value="">— بدون تفصیلی —</option>
              {d.analytics.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} — {a.name}
                </option>
              ))}
            </SearchSelect>
          )}
        </FormField>
      )}
      {/* ارزِ سند: تا وقتی انتخاب نشده، ستونِ ارزی در ردیف‌ها هم دیده نمی‌شود —
          اکثرِ سندها ریالی‌اند و یک ستونِ همیشه‌خالی فقط شلوغی است. */}
      {d.currencies.length > 0 && (
        <FormField label="ارز سند" optional tip="تا ارز انتخاب نشود، ستونِ مبلغِ ارزی در ردیف‌ها نمی‌آید.">
          {(id) => (
            <SearchSelect id={id} value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
              <option value="">— ریالی —</option>
              {d.currencies.map((c) => (
                <option key={c.id} value={c.code}>
                  {c.code} — {c.name}
                </option>
              ))}
            </SearchSelect>
          )}
        </FormField>
      )}
      {d.currencyCode && (
        <FormField label={`نرخ ${d.currencyCode}`}>
          {(id) => (
            <InputAffix unit="ریال">
              <NumberInput id={id} value={d.fxRate} onChange={d.setFxRate} allowDecimal />
            </InputAffix>
          )}
        </FormField>
      )}
    </>
  )
  //: داده‌ی پُر پنهان نمی‌شود: پیش‌نویس ماندگار است و ممکن است از جلسه‌ی قبل یا از حالتِ
  //: حسابدار مقداری در این فیلدها مانده باشد.
  const hasAdvancedValues =
    d.status !== 'temporary' || d.subNumber.trim() !== '' || Boolean(d.costCenterId) || Boolean(d.analyticId) || Boolean(d.currencyCode)
  const advancedSummary = [
    'وضعیت',
    'شماره فرعی',
    ...(d.costCenters.length > 0 ? ['مرکز هزینه'] : []),
    ...(d.analytics.length > 0 ? ['تفصیلی'] : []),
    ...(d.currencies.length > 0 ? ['ارز'] : []),
  ].join('، ')

  if (isAccountant) {
    return (
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void d.submit()
        }}
        onKeyDown={(e) => {
          if (!(e.ctrlKey || e.metaKey)) return
          //: Ctrl+S از **هر جای** فرم، نه فقط از خانه‌های گرید — کنارِ دکمه نوشته شده، پس
          //: باید از سربرگ هم کار کند (در مرورگر وگرنه «ذخیره‌ی صفحه» باز می‌شد). گرید خودش
          //: همین را زودتر می‌گیرد و `preventDefault` می‌کند؛ این شرط جلوی ثبتِ دوباره را می‌گیرد.
          if (e.code === 'KeyS' && !e.defaultPrevented) {
            e.preventDefault()
            if (!d.submitting) void d.submit()
          }
          //: Ctrl+/ راهنما را باز و بسته می‌کند — همان قراردادِ رایجِ «فهرستِ میان‌برها».
          //: `code` و نه `key`: روی چیدمانِ فارسی `key` این کلید «/» نیست.
          if (e.code === 'Slash') {
            e.preventDefault()
            setKeysOpen(!keysOpen)
            //: راهنما زیرِ آخرین ردیف است؛ در سندِ بلند بی این، باز می‌شد و دیده نمی‌شد.
            const guide = e.currentTarget.querySelector('.jg-keys')
            if (!keysOpen) requestAnimationFrame(() => guide?.scrollIntoView?.({ block: 'nearest' }))
          }
        }}
      >
        <SectionCard
          icon={BookOpen}
          title="سند حسابداری"
          tip="سندِ تازه «موقت» ثبت می‌شود تا در کارتابل بازبینی شود؛ فاکتور، فیش و چک خودشان خودکار سند می‌خورند. شماره عطف را سرور هنگامِ ثبت می‌دهد."
          badge={<CountBadge>{fa(d.validLineCount)} ردیف معتبر</CountBadge>}
        >
          <JournalHeaderBar d={d} />
          <JournalGrid d={d} />
          {/* دکمه برای کاربرِ ماوس می‌ماند — حتی در حالت حسابدار (§۲۱، §۴۵). */}
          <AddRowButton onClick={d.addLine}>افزودن ردیف (Ctrl+Enter)</AddRowButton>
          <ShortcutGuide open={keysOpen} onOpenChange={setKeysOpen} />
        </SectionCard>
        <JournalFooter d={d} shortcut />
      </form>
    )
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        void d.submit()
      }}
    >
      <SectionCard
        icon={BookOpen}
        title="سربرگ سند"
        //: حالتِ ساده بی اصطلاحِ «کارتابل» و «عطف»: کاربرِ ساده این‌ها را لازم ندارد، و
        //: راهِ درستِ کارهای روزمره‌اش فرم‌های خودشان است نه سندِ دستی (§۲۷، §۵۱).
        tip="بیشترِ کارها سندِ دستی نمی‌خواهند: فاکتور، دریافت و پرداخت و چک خودشان سند می‌زنند. این فرم برای جابه‌جایی‌هایی است که فرمِ خودشان را ندارند."
      >
        <FormGrid>
          <FormField label="شرح سند">
            {(id) => <input id={id} value={d.description} onChange={(e) => d.setDescription(e.target.value)} />}
          </FormField>
          <FormField label="تاریخ سند" required>
            {(id) => <JalaliDatePicker id={id} value={d.entryDate} onChange={d.setEntryDate} />}
          </FormField>
        </FormGrid>
        <MoreOptions summary={advancedSummary} forceOpen={hasAdvancedValues}>
          <FormGrid>{advancedFields}</FormGrid>
        </MoreOptions>
      </SectionCard>

      <SectionCard
        icon={Rows3}
        title="ردیف‌های سند"
        tip="در هر ردیف یک حساب انتخاب کنید و مبلغ را فقط در یکی از دو ستون بنویسید. جمعِ «بدهکار» و «بستانکار» باید برابر شود؛ نوارِ پایین نشان می‌دهد چقدر مانده."
        badge={<CountBadge>{fa(d.validLineCount)} ردیف معتبر</CountBadge>}
      >
        <JournalLinesTable d={d} />
        <AddRowButton onClick={d.addLine}>افزودن ردیف</AddRowButton>
      </SectionCard>

      <JournalFooter d={d} />
    </form>
  )
}

/**
 * نوارِ فشرده‌ی سربرگ در حالتِ حسابدار — یک ردیفِ افقی به‌جای سه ردیفِ فیلدِ بلند.
 *
 * چهار فیلدِ هر سند (شرح، تاریخ، وضعیت، شماره‌ی فرعی) در ردیفِ اول؛ فیلدهای کسب‌وکاری
 * که فقط گاهی لازم‌اند (مرکز هزینه، تفصیلیِ سایر، ارز) در ردیفِ دومِ کوچک‌تر و فقط اگر
 * کسب‌وکار آن‌ها را تعریف کرده باشد. برچسب‌ها ریز و بالای فیلدند: همان اطلاعات در کمتر
 * از نیمِ ارتفاعِ قبلی (UI-01 §۳۰: تراکم در حالتِ حسابدار).
 *
 * F4 از هر جای سربرگ فهرستِ حسابِ اولین ردیفِ بی‌حساب را باز می‌کند — کاربر لازم نیست
 * اول به گرید برود.
 */
function JournalHeaderBar({ d }: { d: JournalEntryDraft }) {
  const uid = useId()
  const ids = {
    desc: `${uid}-desc`,
    date: `${uid}-date`,
    status: `${uid}-status`,
    sub: `${uid}-sub`,
    center: `${uid}-center`,
    analytic: `${uid}-analytic`,
    currency: `${uid}-currency`,
    rate: `${uid}-rate`,
  }
  const hasSecondary = d.costCenters.length > 0 || d.analytics.length > 0 || d.currencies.length > 0

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key !== 'F4') return
    e.preventDefault()
    const row = Math.max(0, d.lines.findIndex((l) => !l.accountId))
    //: ستونِ حساب همیشه اولین ستونِ گرید است (`cols[0]` در `JournalGrid`).
    openCellPicker(e.currentTarget.closest('form')?.querySelector(`[data-cell="${row}-0"]`))
  }

  return (
    <div className="jh-bar" onKeyDown={onKeyDown}>
      <div className="jh-row">
        <div className="jh-field jh-field--grow">
          <label className="jh-label" htmlFor={ids.desc}>
            شرح سند
          </label>
          <input
            id={ids.desc}
            value={d.description}
            onChange={(e) => d.setDescription(e.target.value)}
            placeholder="شرحِ کلیِ این سند"
          />
        </div>
        <div className="jh-field jh-field--date">
          <label className="jh-label" htmlFor={ids.date}>
            تاریخ سند <span className="jh-req" aria-hidden="true">*</span>
          </label>
          <JalaliDatePicker id={ids.date} value={d.entryDate} onChange={d.setEntryDate} />
        </div>
        <div className="jh-field jh-field--status">
          <span className="jh-label" id={ids.status}>
            وضعیت سند
          </span>
          <StatusToggle value={d.status} onChange={d.setStatus} labelledBy={ids.status} />
        </div>
        <div className="jh-field jh-field--sub">
          <label
            className="jh-label"
            htmlFor={ids.sub}
            title="ارجاعِ خودتان: شماره‌ی پرونده، سندِ سیستمِ قبلی یا کدِ دسته."
          >
            شماره فرعی
          </label>
          <input
            id={ids.sub}
            value={d.subNumber}
            onChange={(e) => d.setSubNumber(e.target.value)}
            maxLength={30}
            placeholder="اختیاری"
          />
        </div>
      </div>

      {hasSecondary && (
        <div className="jh-row jh-row--sub">
          {d.costCenters.length > 0 && (
            <div className="jh-field">
              <label className="jh-label" htmlFor={ids.center}>
                مرکز هزینه / پروژه
              </label>
              <SearchSelect id={ids.center} value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {d.costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code ? `${c.code} — ${c.name}` : c.name}
                  </option>
                ))}
              </SearchSelect>
            </div>
          )}
          {d.analytics.length > 0 && (
            <div className="jh-field">
              <label className="jh-label" htmlFor={ids.analytic}>
                تفصیلی سایر
              </label>
              <SearchSelect id={ids.analytic} value={d.analyticId} onChange={(e) => d.setAnalyticId(e.target.value)}>
                <option value="">— بدون تفصیلی —</option>
                {d.analytics.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            </div>
          )}
          {d.currencies.length > 0 && (
            <div className="jh-field">
              <label
                className="jh-label"
                htmlFor={ids.currency}
                title="تا ارز انتخاب نشود، ستونِ مبلغِ ارزی در ردیف‌ها نمی‌آید."
              >
                ارز سند
              </label>
              <SearchSelect id={ids.currency} value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
                <option value="">— ریالی —</option>
                {d.currencies.map((c) => (
                  <option key={c.id} value={c.code}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </SearchSelect>
            </div>
          )}
          {d.currencyCode && (
            <div className="jh-field">
              <label className="jh-label" htmlFor={ids.rate}>
                نرخ {d.currencyCode}
              </label>
              <InputAffix unit="ریال">
                <NumberInput id={ids.rate} value={d.fxRate} onChange={d.setFxRate} allowDecimal />
              </InputAffix>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const STATUS_OPTIONS = [
  { value: 'temporary', label: 'موقت', hint: 'در کارتابل بازبینی می‌شود.' },
  { value: 'permanent', label: 'دائم', hint: 'همین حالا قطعی می‌شود و دیگر ادغام یا بازشماره‌گذاری نمی‌شود.' },
] as const

/**
 * «موقت / دائم» به‌صورتِ دو دکمه‌ی کنارِ هم به‌جای فهرستِ کشویی — یک کلیک، و وضعیت با یک
 * نگاه خوانده می‌شود. الگوی radiogroup: Tab یک‌بار واردش می‌شود و ←/→ عوضش می‌کند.
 */
function StatusToggle({
  value,
  onChange,
  labelledBy,
}: {
  value: 'temporary' | 'permanent'
  onChange: (v: 'temporary' | 'permanent') => void
  labelledBy: string
}) {
  return (
    <div
      className="jh-seg"
      role="radiogroup"
      aria-labelledby={labelledBy}
      onKeyDown={(e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
        e.preventDefault()
        onChange(value === 'temporary' ? 'permanent' : 'temporary')
        const group = e.currentTarget
        requestAnimationFrame(() => group.querySelector<HTMLElement>('[aria-checked="true"]')?.focus())
      }}
    >
      {STATUS_OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          tabIndex={value === o.value ? 0 : -1}
          className={`jh-seg-opt jh-seg-opt--${o.value}`}
          title={o.hint}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/**
 * راهنمای میان‌برها — یک خطِ کم‌رنگ زیرِ گرید که با کلیک یا Ctrl+/ باز می‌شود.
 *
 * بسته: سه میان‌برِ اصلی و راهِ دیدنِ بقیه، در یک خط. باز: همه، در چهار دسته. پیش‌تر
 * ده میان‌بر همیشه باز بود و دو خطِ پُر زیرِ هر سند می‌گرفت؛ حسابداری که یادشان گرفته
 * دیگر لازمشان ندارد، و تازه‌کار با یک کلیک همه را می‌بیند. باز/بسته روی همین دستگاه
 * می‌ماند. در موبایل پنهان است: صفحه‌کلیدِ فیزیکی نیست.
 */
const KEY_PEEK: [string, string][] = [
  ['Enter', 'خانه‌ی بعد'],
  ['F4', 'فهرستِ حساب‌ها'],
  ['Ctrl+S', 'ثبت'],
]

const KEY_GROUPS: { title: string; keys: [string, string][] }[] = [
  {
    title: 'حرکت',
    keys: [
      ['Enter', 'خانه‌ی بعد'],
      ['Tab', 'خانه‌ی بعد؛ در پایان، ردیفِ تازه'],
      ['← → ↑ ↓', 'جابه‌جایی بینِ خانه‌ها'],
      ['Ctrl+G', 'رفتن به ردیف'],
    ],
  },
  {
    title: 'ورود و انتخاب',
    keys: [
      ['F2', 'ویرایشِ متنِ خانه'],
      ['F4', 'فهرستِ حساب‌ها'],
      ['Alt+↓', 'فهرستِ همین خانه'],
    ],
  },
  {
    title: 'ردیف‌ها',
    keys: [
      ['Ctrl+Enter', 'ردیفِ تازه'],
      ['Ctrl+D', 'تکرارِ ردیف'],
      ['Ctrl+Shift+C', 'کپیِ حساب از ردیفِ قبل'],
      ['Ctrl+Delete', 'حذفِ ردیف'],
    ],
  },
  {
    title: 'سند',
    keys: [
      ['Ctrl+S', 'ثبتِ سند'],
      ['Ctrl+/', 'باز و بسته کردنِ این راهنما'],
    ],
  },
]

const KEYS_OPEN_KEY = 'cubita.journal.shortcutsOpen'

//: ترجیحِ نمایشی است، نه داده: اگر ذخیره‌گاه در دسترس نبود راهنما بسته شروع می‌شود.
function readKeysOpen(): boolean {
  try {
    return localStorage.getItem(KEYS_OPEN_KEY) === '1'
  } catch {
    return false
  }
}

function writeKeysOpen(open: boolean) {
  try {
    localStorage.setItem(KEYS_OPEN_KEY, open ? '1' : '0')
  } catch {
    /* بی‌ذخیره هم کار می‌کند */
  }
}

function ShortcutGuide({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <details className="jg-keys" open={open} onToggle={(e) => onOpenChange(e.currentTarget.open)}>
      <summary aria-keyshortcuts="Control+/">
        <Keyboard size={15} aria-hidden="true" />
        <span className="jg-keys-title">میان‌برها</span>
        <span className="jg-keys-peek">
          {KEY_PEEK.map(([keys, what]) => (
            <span key={keys}>
              <kbd dir="ltr">{keys}</kbd> {what}
            </span>
          ))}
        </span>
        <span className="jg-keys-more">
          {open ? 'بستن' : 'همه‌ی میان‌برها'} <kbd dir="ltr">Ctrl+/</kbd>
          <ChevronDown size={14} aria-hidden="true" />
        </span>
      </summary>
      <div className="jg-keys-panel">
        {KEY_GROUPS.map((g) => (
          <div key={g.title} className="jg-keys-group" role="group" aria-label={g.title}>
            <div className="jg-keys-group-title">{g.title}</div>
            {g.keys.map(([keys, what]) => (
              <div key={keys} className="jg-keys-row">
                <kbd dir="ltr">{keys}</kbd>
                <span>{what}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </details>
  )
}

type BalanceState = 'empty' | 'ok' | 'err'

function balanceState(d: JournalEntryDraft): BalanceState {
  if (d.totalDebit === 0 && d.totalCredit === 0) return 'empty'
  return d.isBalanced ? 'ok' : 'err'
}

/**
 * نوارِ شناورِ پایینِ سند: جمع‌ها و دکمه‌ی ثبت، همیشه در دیدرس.
 *
 * هر دو حالت همین را دارند. جای `ActionBar`ِ عمومی، چون این‌جا نوار خودش محتوای اصلی
 * است، نه جای یک دکمه: عددها درشت‌اند، رنگِ توازن روی لبه‌ی بالای کلِ نوار می‌نشیند، و
 * دکمه‌ی ثبت بزرگ‌تر از دکمه‌ی فرم‌های دیگر است. `shortcut` فقط در حالتِ حسابدار
 * «Ctrl+S» را کنارِ دکمه می‌نویسد — حالتِ ساده آن میان‌بر را ندارد.
 *
 * **چرا دو لایه (`jf-dock` و `jf-foot`).** لایه‌ی بیرونی می‌چسبد و ظرفِ `scroll-state`
 * است؛ لایه‌ی درونی ظاهر است و وقتی نوار واقعاً چسبیده، گوشه‌های پایینش صاف می‌شود.
 * پرس‌وجوی `scroll-state` فقط فرزندان را می‌تواند رنگ کند، نه خودِ ظرف را.
 */
function JournalFooter({ d, shortcut = false }: { d: JournalEntryDraft; shortcut?: boolean }) {
  const state = balanceState(d)
  return (
    <div className="jf-dock">
      <div className={`jf-foot jf-foot--${state}`}>
        <BalanceSummary d={d} state={state} />
        <div className="jf-msg">
          <FormStatus msg={d.message} />
        </div>
        <button
          type="submit"
          className="btn-primary jf-submit"
          disabled={d.submitting}
          aria-keyshortcuts={shortcut ? 'Control+S' : undefined}
        >
          <Check size={18} aria-hidden="true" /> {d.submitting ? 'در حال ثبت…' : 'ثبت سند'}
          {shortcut && (
            <kbd className="jf-submit-kbd" dir="ltr" aria-hidden="true">
              Ctrl+S
            </kbd>
          )}
        </button>
      </div>
    </div>
  )
}

/**
 * سه عددِ زنده‌ی سند: جمعِ بدهکار، جمعِ بستانکار، و اختلاف.
 *
 * سبز = متوازن، قرمز = اختلاف (با اینکه کدام طرف بیشتر است، تا حسابدار بداند ردیفِ بعد
 * بدهکار است یا بستانکار)، خاکستری = هنوز مبلغی نیست. اختلاف `aria-live` دارد تا
 * صفحه‌خوان هم بشنودش.
 */
function BalanceSummary({ d, state }: { d: JournalEntryDraft; state: BalanceState }) {
  const diff = Math.abs(d.totalDebit - d.totalCredit)
  return (
    <div className={`jb-sum jb-sum--${state}`} role="group" aria-label="جمعِ سند">
      <div className="jb-stat">
        <span className="jb-k">جمع بدهکار</span>
        <span className="jb-v">{fa(d.totalDebit)}</span>
      </div>
      <div className="jb-stat">
        <span className="jb-k">جمع بستانکار</span>
        <span className="jb-v">{fa(d.totalCredit)}</span>
      </div>
      <div className="jb-stat jb-stat--diff" aria-live="polite">
        <span className="jb-k">{state === 'ok' ? 'توازن' : 'اختلاف'}</span>
        <span className="jb-v">
          {state === 'empty' ? (
            'مبلغی وارد نشده'
          ) : state === 'ok' ? (
            <>
              <CheckCircle2 size={18} aria-hidden="true" /> متوازن
            </>
          ) : (
            <>
              <AlertTriangle size={18} aria-hidden="true" /> {fa(diff)}
              <small>{d.totalDebit > d.totalCredit ? 'بدهکار بیشتر' : 'بستانکار بیشتر'}</small>
            </>
          )}
        </span>
      </div>
    </div>
  )
}

/** گریدِ ردیف‌های سند (حساب + بدهکار/بستانکار). */
export function JournalLinesTable({ d }: { d: JournalEntryDraft }) {
  // ستون‌های پیگیری فقط وقتی ظاهر می‌شوند که دستِ‌کم یک ردیف حسابِ پیگیری‌دار
  // داشته باشد. همیشه نشان دادنشان جدولِ چهارستونی را برای همه‌ی کسانی که هرگز
  // پیگیری نمی‌خواهند به شش‌ستونی تبدیل می‌کرد.
  const showTracking = d.lines.some((l) => d.trackingAllowed.has(l.accountId))
  // ستونِ تفصیلی هم مثلِ پیگیری فقط وقتی می‌آید که ردیفی لازمش داشته باشد — ولی
  // برخلافِ پیگیری، این یکی **اجباری** است و خالی‌ماندنش سند را رد می‌کند.
  const showTafsili = d.lines.some((l) => d.tafsiliRequired.has(l.accountId))
  //: شرحِ ردیف در حالت ساده ستونِ همیشگی نیست — اکثرِ سندهای ساده لازمش ندارند.
  //: ولی اگر کاربری در حالت حسابدار شرح نوشته و بعد به ساده برگشته، ستون
  //: می‌آید: داده‌ای که ثبت می‌شود هرگز نباید نامرئی بماند (§۳۵).
  const showLineDescription = d.lines.some((l) => (l.description ?? '').trim() !== '')
  //: مرکزِ هزینه‌ی ردیف در حالتِ ساده ستون ندارد — مگر ردیفی از حالتِ حسابدار مقدار
  //: آورده باشد؛ مقداری که ثبت می‌شود نامرئی نمی‌ماند.
  const showLineCostCenter = d.lines.some((l) => Boolean(l.costCenterId))
  return (
    <div className="table-scroll ef-table-wrap">
      <table className="cards-on-mobile ef-table ef-table--edit">
        <thead>
          <tr>
            <th className="ef-col-min">ردیف</th>
            <th>حساب</th>
            {d.currencyCode && <th>مبلغ ارزی</th>}
            {showTafsili && <th>تفصیلی</th>}
            {showLineCostCenter && <th>مرکز هزینه</th>}
            {showLineDescription && <th>شرح ردیف</th>}
            <th>بدهکار</th>
            <th>بستانکار</th>
            {showTracking && <th>شماره پیگیری</th>}
            {showTracking && <th>تاریخ پیگیری</th>}
            <th className="ef-col-min" aria-label="حذف" />
          </tr>
        </thead>
        <tbody>
          {d.lines.map((line, i) => (
            <tr key={i}>
              <td className="card-title ef-col-min" data-label="ردیف">
                ردیف {fa(i + 1)}
              </td>
              <td className="card-wide ef-col-wide" data-label="حساب">
                <SearchSelect
                  aria-label={`حسابِ ردیفِ ${fa(i + 1)}`}
                  value={line.accountId}
                  onChange={(e) => d.updateLine(i, { accountId: e.target.value })}
                >
                  <option value="">— انتخاب حساب —</option>
                  {d.postableAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </SearchSelect>
              </td>
              {d.currencyCode && (
                <td className="card-wide" data-label="مبلغ ارزی">
                  <InputAffix unit={d.currencyCode}>
                    <NumberInput
                      aria-label={`مبلغِ ارزیِ ردیفِ ${fa(i + 1)}`}
                      value={line.fxAmount ?? ''}
                      onChange={(v) => d.setLineFx(i, v)}
                      allowDecimal
                    />
                  </InputAffix>
                </td>
              )}
              {showTafsili && (
                <td className="card-wide" data-label="تفصیلی">
                  {d.tafsiliRequired.has(line.accountId) ? (
                    <SearchSelect
                      aria-label={`تفصیلیِ ردیفِ ${fa(i + 1)}`}
                      value={line.analyticId ?? ''}
                      onChange={(e) => d.updateLine(i, { analyticId: e.target.value })}
                      //: در «شناور» فیلد هست ولی اجباری نیست — همان انتخابی که
                      //: کاربر در تنظیمات ← شخصی‌سازی کرده.
                      required={d.tafsiliMode !== 'floating'}
                    >
                      {/* اگر سطحِ سند تفصیلی دارد، خالی‌گذاشتن یعنی «همان» — پس
                          متنِ گزینه‌ی خالی باید همین را بگوید، نه «انتخاب کنید». */}
                      <option value="">{d.analyticId ? '— تفصیلیِ سند —' : '— انتخاب کنید —'}</option>
                      {d.analytics.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </SearchSelect>
                  ) : (
                    <input type="text" value="" disabled placeholder="—" readOnly aria-label="بدونِ تفصیلی" />
                  )}
                </td>
              )}
              {showLineCostCenter && (
                <td className="card-wide" data-label="مرکز هزینه">
                  <SearchSelect
                    aria-label={`مرکزِ هزینه‌ی ردیفِ ${fa(i + 1)}`}
                    value={line.costCenterId ?? ''}
                    onChange={(e) => d.updateLine(i, { costCenterId: e.target.value })}
                  >
                    <option value="">{d.costCenterId ? '— مرکزِ سند —' : '— بدون مرکز —'}</option>
                    {d.costCenters.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code ? `${c.code} — ${c.name}` : c.name}
                      </option>
                    ))}
                  </SearchSelect>
                </td>
              )}
              {showLineDescription && (
                <td className="card-wide" data-label="شرح ردیف">
                  <input
                    type="text"
                    aria-label={`شرحِ ردیفِ ${fa(i + 1)}`}
                    value={line.description ?? ''}
                    onChange={(e) => d.updateLine(i, { description: e.target.value })}
                    placeholder="اختیاری"
                  />
                </td>
              )}
              <td className="card-wide" data-label="بدهکار">
                <InputAffix unit="ریال">
                  <NumberInput
                    aria-label={`بدهکارِ ردیفِ ${fa(i + 1)}`}
                    value={line.debit}
                    onChange={(v) => d.updateLine(i, { debit: v, credit: '' })}
                  />
                </InputAffix>
              </td>
              <td className="card-wide" data-label="بستانکار">
                <InputAffix unit="ریال">
                  <NumberInput
                    aria-label={`بستانکارِ ردیفِ ${fa(i + 1)}`}
                    value={line.credit}
                    onChange={(v) => d.updateLine(i, { credit: v, debit: '' })}
                  />
                </InputAffix>
              </td>
              {showTracking && (
                <td className="card-wide" data-label="شماره پیگیری">
                  {/* ردیفی که حسابش پیگیری نمی‌پذیرد خالی و غیرفعال می‌ماند، نه
                      پنهان: ستون که هست، جای خالی خودش می‌گوید این حساب پیگیری
                      ندارد. */}
                  <input
                    type="text"
                    aria-label={`شماره پیگیریِ ردیفِ ${fa(i + 1)}`}
                    value={line.trackingNo ?? ''}
                    onChange={(e) => d.updateLine(i, { trackingNo: e.target.value })}
                    disabled={!d.trackingAllowed.has(line.accountId)}
                    maxLength={50}
                    placeholder={d.trackingAllowed.has(line.accountId) ? 'شماره‌ی حواله/نامه' : '—'}
                  />
                </td>
              )}
              {showTracking && (
                <td className="card-wide" data-label="تاریخ پیگیری">
                  {d.trackingAllowed.has(line.accountId) ? (
                    <JalaliDatePicker
                      value={line.trackingDate ?? ''}
                      onChange={(v) => d.updateLine(i, { trackingDate: v })}
                    />
                  ) : (
                    <input type="text" value="" disabled placeholder="—" readOnly aria-label="بدونِ پیگیری" />
                  )}
                </td>
              )}
              <td className="card-actions ef-col-min">
                <RowAction
                  icon={Trash2}
                  label="حذف ردیف"
                  danger
                  disabled={d.lines.length === 2}
                  title={d.lines.length === 2 ? 'سند دست‌کم دو ردیف می‌خواهد.' : undefined}
                  onClick={() => d.removeLine(i)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
