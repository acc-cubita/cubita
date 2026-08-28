import { BookOpen, Plus, Trash2, Save } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { JalaliDatePicker } from './JalaliDatePicker'
import { useJournalEntryDraft, type JournalEntryDraft } from '../lib/journalEntryDraft'

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
          {d.costCenters.length > 0 && (
            <label>
              مرکز هزینه/پروژه (اختیاری)
              <select value={d.costCenterId} onChange={(e) => d.setCostCenterId(e.target.value)}>
                <option value="">— بدون مرکز —</option>
                {d.costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code ? `${c.code} — ${c.name}` : c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {d.analytics.length > 0 && (
            <label>
              تفصیلی سایر (اختیاری)
              <select value={d.analyticId} onChange={(e) => d.setAnalyticId(e.target.value)}>
                <option value="">— بدون تفصیلی —</option>
                {d.analytics.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} — {a.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            وضعیتِ سند
            <select
              value={d.status}
              onChange={(e) => d.setStatus(e.target.value as 'temporary' | 'permanent')}
            >
              <option value="temporary">موقت — در کارتابل بازبینی شود</option>
              <option value="permanent">دائم — همین حالا قطعی</option>
            </select>
          </label>
          {/* ارزِ سند: تا وقتی انتخاب نشده، ستونِ ارزی در ردیف‌ها هم دیده نمی‌شود —
              اکثرِ سندها ریالی‌اند و یک ستونِ همیشه‌خالی فقط شلوغی است. */}
          {d.currencies.length > 0 && (
            <label>
              ارزِ سند (اختیاری)
              <select value={d.currencyCode} onChange={(e) => d.setCurrencyCode(e.target.value)}>
                <option value="">— ریالی —</option>
                {d.currencies.map((c) => (
                  <option key={c.id} value={c.code}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </select>
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
  return (
    <div className="table-scroll">
      <table className="invoice-lines cards-on-mobile">
        <thead>
          <tr>
            <th>حساب</th>
            {d.currencyCode && <th>مبلغ {d.currencyCode}</th>}
            <th>بدهکار</th>
            <th>بستانکار</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {d.lines.map((line, i) => (
            <tr key={i}>
              <td data-label="حساب">
                <select value={line.accountId} onChange={(e) => d.updateLine(i, { accountId: e.target.value })}>
                  <option value="">— انتخاب حساب —</option>
                  {d.postableAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.name}
                    </option>
                  ))}
                </select>
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
              <td data-label="بدهکار">
                <NumberInput value={line.debit} onChange={(v) => d.updateLine(i, { debit: v, credit: '' })} />
              </td>
              <td data-label="بستانکار">
                <NumberInput value={line.credit} onChange={(v) => d.updateLine(i, { credit: v, debit: '' })} />
              </td>
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
