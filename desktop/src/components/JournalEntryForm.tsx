import { BookOpen, Plus, Trash2, Save } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { useJournalEntryDraft, type JournalEntryDraft } from '../lib/journalEntryDraft'
import { SearchSelect } from '../components/SearchSelect'

/** فرمِ کلاسیکِ «ثبت سند حسابداری دستی» (پوسته‌های تیره/روشن). منطق در هوکِ [useJournalEntryDraft]. */
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

  return (
    <SectionCard icon={BookOpen} title="ثبت سند حسابداری دستی">
      {d.postableAccounts.length === 0 ? (
        <p className="hint">قبل از ثبت سند، یک‌بار «هم‌گام‌سازی» کنید تا چارت حساب در دسترس باشد.</p>
      ) : (
        <form
          className="invoice-form"
          onSubmit={(e) => {
            e.preventDefault()
            void d.submit()
          }}
        >
          <label>
            شرح سند
            <input type="text" value={d.description} onChange={(e) => d.setDescription(e.target.value)} />
          </label>
          <label>
            تاریخ سند
            <JalaliDatePicker value={d.entryDate} onChange={d.setEntryDate} />
          </label>
          {/* شماره عطف عمداً در فرم نیست: سرور لحظه‌ی ثبت می‌دهدش و کاربر
              انتخابی ندارد. پس از ثبت، در دفترِ «اسناد حسابداری» دیده می‌شود. */}
          <label>
            شماره فرعی (اختیاری)
            <input
              type="text"
              value={d.subNumber}
              onChange={(e) => d.setSubNumber(e.target.value)}
              maxLength={30}
              placeholder="شماره‌ی پرونده، سندِ سیستمِ قبلی، کدِ دسته"
            />
          </label>
          {d.costCenters.length > 0 && (
            <label>
              مرکز هزینه/پروژه (اختیاری)
              <SearchSelect value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {d.costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code ? `${c.code} — ${c.name}` : c.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
          )}
          {d.analytics.length > 0 && (
            <label>
              تفصیلی سایر (اختیاری)
              <SearchSelect value={d.analyticId} onChange={(e) => d.setAnalyticId(e.target.value)}>
                <option value="">— بدون تفصیلی —</option>
                {d.analytics.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
          )}
          <label>
            وضعیتِ سند
            <SearchSelect
              value={d.status}
              onChange={(e) => d.setStatus(e.target.value as 'temporary' | 'permanent')}
            >
              <option value="temporary">موقت — در کارتابل بازبینی شود</option>
              <option value="permanent">دائم — همین حالا قطعی</option>
            </SearchSelect>
          </label>
          {/* ارزِ سند: تا وقتی انتخاب نشده، ستونِ ارزی در ردیف‌ها هم دیده نمی‌شود —
              اکثرِ سندها ریالی‌اند و یک ستونِ همیشه‌خالی فقط شلوغی است. */}
          {d.currencies.length > 0 && (
            <label>
              ارزِ سند (اختیاری)
              <SearchSelect value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
                <option value="">— ریالی —</option>
                {d.currencies.map((c) => (
                  <option key={c.id} value={c.code}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </SearchSelect>
            </label>
          )}
          {d.currencyCode && (
            <label>
              نرخِ {d.currencyCode} (ریال)
              <NumberInput value={d.fxRate} onChange={d.setFxRate} allowDecimal />
            </label>
          )}

          <JournalLinesTable d={d} />

          <div className="invoice-form-footer">
            <button type="button" onClick={d.addLine}>
              <Plus size={14} /> افزودن ردیف
            </button>
            <span className={d.isBalanced ? 'invoice-total' : 'invoice-total error'}>
              بدهکار: {d.totalDebit.toLocaleString('fa-IR')} / بستانکار: {d.totalCredit.toLocaleString('fa-IR')}
            </span>
            <button type="submit" className="btn-primary" disabled={d.submitting}>
              <Save size={14} /> ثبت سند
            </button>
          </div>

          {d.message && <div className="hint">{d.message}</div>}
        </form>
      )}
    </SectionCard>
  )
}

/** گریدِ ردیف‌های سند (حساب + بدهکار/بستانکار) — مشترکِ فرم و ویزارد. */
export function JournalLinesTable({ d }: { d: JournalEntryDraft }) {
  // ستون‌های پیگیری فقط وقتی ظاهر می‌شوند که دستِ‌کم یک ردیف حسابِ پیگیری‌دار
  // داشته باشد. همیشه نشان دادنشان جدولِ چهارستونی را برای همه‌ی کسانی که هرگز
  // پیگیری نمی‌خواهند به شش‌ستونی تبدیل می‌کرد.
  const showTracking = d.lines.some((l) => d.trackingAllowed.has(l.accountId))
  // ستونِ تفصیلی هم مثلِ پیگیری فقط وقتی می‌آید که ردیفی لازمش داشته باشد — ولی
  // برخلافِ پیگیری، این یکی **اجباری** است و خالی‌ماندنش سند را رد می‌کند.
  const showTafsili = d.lines.some((l) => d.tafsiliRequired.has(l.accountId))
  return (
    <div className="table-scroll">
      <table className="invoice-lines cards-on-mobile">
        <thead>
          <tr>
            <th>حساب</th>
            {d.currencyCode && <th>مبلغ {d.currencyCode}</th>}
            {showTafsili && <th>تفصیلی</th>}
            <th>بدهکار</th>
            <th>بستانکار</th>
            {showTracking && <th>شماره پیگیری</th>}
            {showTracking && <th>تاریخ پیگیری</th>}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {d.lines.map((line, i) => (
            <tr key={i}>
              <td data-label="حساب">
                <SearchSelect value={line.accountId} onChange={(e) => d.updateLine(i, { accountId: e.target.value })}>
                  <option value="">— انتخاب حساب —</option>
                  {d.postableAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </SearchSelect>
              </td>
              {d.currencyCode && (
                <td data-label="مبلغ ارزی">
                  <NumberInput
                    value={line.fxAmount ?? ''}
                    onChange={(v) => d.setLineFx(i, v)}
                    allowDecimal
                  />
                </td>
              )}
              {showTafsili && (
                <td data-label="تفصیلی">
                  {d.tafsiliRequired.has(line.accountId) ? (
                    <SearchSelect
                      value={line.analyticId ?? ''}
                      onChange={(e) => d.updateLine(i, { analyticId: e.target.value })}
                      //: در «شناور» فیلد هست ولی اجباری نیست — همان انتخابی که
                      //: کاربر در تنظیمات ← شخصی‌سازی کرده.
                      required={d.tafsiliMode !== 'floating'}
                    >
                      {/* اگر سطحِ سند تفصیلی دارد، خالی‌گذاشتن یعنی «همان» — پس
                          متنِ گزینه‌ی خالی باید همین را بگوید، نه «انتخاب کنید». */}
                      <option value="">
                        {d.analyticId ? '— تفصیلیِ سند —' : '— انتخاب کنید —'}
                      </option>
                      {d.analytics.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </SearchSelect>
                  ) : (
                    <input type="text" value="" disabled placeholder="—" readOnly />
                  )}
                </td>
              )}
              <td data-label="بدهکار">
                <NumberInput value={line.debit} onChange={(v) => d.updateLine(i, { debit: v, credit: '' })} />
              </td>
              <td data-label="بستانکار">
                <NumberInput value={line.credit} onChange={(v) => d.updateLine(i, { credit: v, debit: '' })} />
              </td>
              {showTracking && (
                <td data-label="شماره پیگیری">
                  {/* ردیفی که حسابش پیگیری نمی‌پذیرد خالی و غیرفعال می‌ماند، نه
                      پنهان: ستون که هست، جای خالی خودش می‌گوید این حساب پیگیری
                      ندارد. */}
                  <input
                    type="text"
                    value={line.trackingNo ?? ''}
                    onChange={(e) => d.updateLine(i, { trackingNo: e.target.value })}
                    disabled={!d.trackingAllowed.has(line.accountId)}
                    maxLength={50}
                    placeholder={d.trackingAllowed.has(line.accountId) ? 'شماره‌ی حواله/نامه' : '—'}
                  />
                </td>
              )}
              {showTracking && (
                <td data-label="تاریخ پیگیری">
                  {d.trackingAllowed.has(line.accountId) ? (
                    <JalaliDatePicker
                      value={line.trackingDate ?? ''}
                      onChange={(v) => d.updateLine(i, { trackingDate: v })}
                    />
                  ) : (
                    <input type="text" value="" disabled placeholder="—" readOnly />
                  )}
                </td>
              )}
              <td className="card-actions">
                <button
                  type="button"
                  className="icon-btn-danger"
                  onClick={() => d.removeLine(i)}
                  disabled={d.lines.length === 2}
                  aria-label="حذف ردیف"
                >
                  <Trash2 size={14} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
