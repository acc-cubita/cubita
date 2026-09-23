import { AlertTriangle, BookOpen, Check, CheckCircle2, Keyboard, Rows3, Trash2 } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { SearchSelect } from './SearchSelect'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import {
  ActionBar,
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

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * فرمِ «ثبت سند حسابداری دستی» — منطق در هوکِ [useJournalEntryDraft].
 *
 * دو کارت و یک نوار: سربرگِ سند، ردیف‌ها، و نوارِ چسبنده‌ای که جمعِ بدهکار/بستانکار را همیشه
 * جلوی چشم نگه می‌دارد — سندی که جمعش نمی‌خواند نباید تا لحظه‌ی زدنِ دکمه پنهان بماند.
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
        tip={
          isAccountant
            ? 'سندِ تازه «موقت» ثبت می‌شود تا در کارتابل بازبینی شود؛ فاکتور، فیش و چک خودشان خودکار سند می‌خورند. شماره عطف را سرور هنگامِ ثبت می‌دهد.'
            : 'بیشترِ کارها سندِ دستی نمی‌خواهند: فاکتور، دریافت و پرداخت و چک خودشان سند می‌زنند. این فرم برای جابه‌جایی‌هایی است که فرمِ خودشان را ندارند.'
        }
      >
        <FormGrid>
          <FormField label="شرح سند">
            {(id) => <input id={id} value={d.description} onChange={(e) => d.setDescription(e.target.value)} />}
          </FormField>
          <FormField label="تاریخ سند" required>
            {(id) => <JalaliDatePicker id={id} value={d.entryDate} onChange={d.setEntryDate} />}
          </FormField>
          {isAccountant && advancedFields}
        </FormGrid>
        {!isAccountant && (
          <MoreOptions summary={advancedSummary} forceOpen={hasAdvancedValues}>
            <FormGrid>{advancedFields}</FormGrid>
          </MoreOptions>
        )}
      </SectionCard>

      <SectionCard
        icon={Rows3}
        title="ردیف‌های سند"
        //: در حالت حسابدار راهنمای طولانی جای گرید را می‌گیرد (§۳۰) — همان
        //: جمله در حالت ساده مفید است و اینجا فقط تراکم را می‌خورد.
        tip={
          isAccountant
            ? undefined
            : 'در هر ردیف یک حساب انتخاب کنید و مبلغ را فقط در یکی از دو ستون بنویسید. جمعِ «بدهکار» و «بستانکار» باید برابر شود؛ نوارِ پایین نشان می‌دهد چقدر مانده.'
        }
        badge={<CountBadge>{fa(d.validLineCount)} ردیف معتبر</CountBadge>}
        actions={isAccountant ? <ShortcutHint /> : undefined}
      >
        {isAccountant ? <JournalGrid d={d} /> : <JournalLinesTable d={d} />}
        {/* دکمه برای کاربرِ ماوس می‌ماند — حتی در حالت حسابدار (§۲۱، §۴۵). */}
        <AddRowButton onClick={d.addLine}>افزودن ردیف{isAccountant ? ' (Ctrl+Enter)' : ''}</AddRowButton>
      </SectionCard>

      <ActionBar status={<FormStatus msg={d.message} idle={<BalanceStatus d={d} />} />}>
        <button type="submit" className="btn-primary" disabled={d.submitting}>
          <Check size={16} /> {d.submitting ? 'در حال ثبت…' : 'ثبت سند'}
        </button>
      </ActionBar>
    </form>
  )
}

/**
 * لینکِ کوچکِ «میان‌برها» بالای گرید (§۳۹).
 *
 * میان‌برهای گرید در `ShortcutsPage` هم ثبت شده‌اند؛ این فقط راهِ دیدنشان بدونِ
 * ترک‌کردنِ فرم است. عمداً یک `title` است نه پاپ‌آور: حسابدارِ وسطِ کار نباید
 * چیزی برای بستن داشته باشد.
 */
function ShortcutHint() {
  return (
    <span
      className="jg-hint"
      title={[
        'Enter — مقدار بعدی (در ستونِ مبلغِ خالی: پذیرشِ باقی‌مانده)',
        'Shift+Enter — مقدار قبلی',
        'Tab / Shift+Tab — فیلد بعد/قبل',
        '↑ ↓ — ردیف بالا/پایین در همان ستون',
        'Ctrl+Enter — افزودن ردیف',
        'Ctrl+D — تکرار ردیف',
        'Ctrl+Shift+C — کپی از ردیف قبل',
        'Ctrl+Delete — حذف ردیف',
        'Ctrl+S — ثبت سند',
        'Esc — بستنِ فهرستِ انتخاب',
      ].join('\n')}
    >
      <Keyboard size={14} aria-hidden="true" /> میان‌برها
    </span>
  )
}

/** جمعِ زنده‌ی سند در نوارِ پایین، با نشانِ توازن. */
function BalanceStatus({ d }: { d: JournalEntryDraft }) {
  if (d.totalDebit === 0 && d.totalCredit === 0) return <>مبلغی وارد نشده است.</>
  return (
    <span className={d.isBalanced ? 'is-ok' : 'is-err'}>
      {d.isBalanced ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />} بدهکار {fa(d.totalDebit)} · بستانکار{' '}
      {fa(d.totalCredit)}
      {d.isBalanced ? ' — متوازن' : ` — اختلاف ${fa(Math.abs(d.totalDebit - d.totalCredit))}`}
    </span>
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
  return (
    <div className="table-scroll ef-table-wrap">
      <table className="cards-on-mobile ef-table ef-table--edit">
        <thead>
          <tr>
            <th className="ef-col-min">ردیف</th>
            <th>حساب</th>
            {d.currencyCode && <th>مبلغ ارزی</th>}
            {showTafsili && <th>تفصیلی</th>}
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
