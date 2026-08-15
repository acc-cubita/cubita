import { Wallet, Save, RefreshCw, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'
import type { AccountCache } from '../electron.d'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { StatCard } from './StatCard'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali } from '../lib/jalali'
import { usePettyCashDraft, type PettyCashDraft } from '../lib/pettyCashDraft'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

/**
 * تنخواه‌گردان (پوسته‌های تیره/روشن) — موجودیِ زنده + دو فرمِ شارژ/هزینه کنارِ هم +
 * دفترچه‌ی گردش. منطق در هوکِ مشترکِ [usePettyCashDraft].
 */
export function PettyCashPanel({ token, accounts }: { token: string; accounts: AccountCache[] }) {
  const d = usePettyCashDraft({ token, accounts })

  return (
    <div className="page-block">
      <div className="stat-grid">
        <StatCard
          icon={<Wallet size={18} />}
          label="موجودیِ تنخواه‌گردان"
          value={d.balance == null ? '—' : fa(d.balance)}
          hint="ریال"
          tone={d.balance != null && d.balance < 0 ? 'danger' : 'default'}
        />
      </div>

      <div className="workspace-split">
        <SectionCard icon={ArrowDownToLine} title="شارژ تنخواه‌گردان" description="انتقالِ پول از صندوق/بانک به تنخواه.">
          <form
            className="invoice-form"
            onSubmit={(e) => {
              e.preventDefault()
              void d.submitCharge()
            }}
          >
            <label>از حساب
              <select value={d.chargeSourceId} onChange={(e) => d.setChargeSourceId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {d.postable.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </label>
            <label>مبلغ<NumberInput value={d.chargeAmount} onChange={d.setChargeAmount} /></label>
            <label>تاریخ<JalaliDatePicker value={d.chargeDate} onChange={d.setChargeDate} /></label>
            <div className="invoice-form-footer"><button type="submit" className="btn-primary" disabled={d.submitting}><Save size={14} /> شارژ</button></div>
          </form>
        </SectionCard>

        <SectionCard icon={ArrowUpFromLine} title="هزینه‌کرد از تنخواه‌گردان" description="ثبتِ هزینه‌ی پرداخت‌شده از تنخواه.">
          <form
            className="invoice-form"
            onSubmit={(e) => {
              e.preventDefault()
              void d.submitExpense()
            }}
          >
            <label>بابت حساب هزینه
              <select value={d.expenseAccountId} onChange={(e) => d.setExpenseAccountId(e.target.value)}>
                <option value="">— انتخاب —</option>
                {d.expenseAccounts.map((a) => <option key={a.id} value={a.id}>{a.code} — {a.name}</option>)}
              </select>
            </label>
            <label>مبلغ<NumberInput value={d.expenseAmount} onChange={d.setExpenseAmount} /></label>
            <label>توضیحات<input type="text" value={d.expenseDescription} onChange={(e) => d.setExpenseDescription(e.target.value)} /></label>
            <label>تاریخ<JalaliDatePicker value={d.expenseDate} onChange={d.setExpenseDate} /></label>
            <div className="invoice-form-footer"><button type="submit" className="btn-primary" disabled={d.submitting}><Save size={14} /> ثبت هزینه</button></div>
          </form>
        </SectionCard>
      </div>
      {d.message && <div className="hint">{d.message}</div>}

      <PettyCashLedger d={d} />
    </div>
  )
}

/** دفترچه‌ی گردشِ تنخواه (موجودی + جدولِ ماندهٔ در حال اجرا) — مشترکِ فرم و ویزارد. */
export function PettyCashLedger({ d }: { d: PettyCashDraft }) {
  const pg = usePagination(d.rows, 10)
  return (
    <SectionCard
      icon={Wallet}
      title="دفترچه‌ی تنخواه‌گردان"
      description="گردشِ شارژ و هزینه با ماندهٔ در حال اجرا، تازه‌ترین اول."
      actions={<button onClick={() => void d.refresh()}><RefreshCw size={13} /> به‌روزرسانی</button>}
    >
      {d.error && <div className="error">{d.error}</div>}
      {d.txns == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : d.rows.length === 0 ? (
        <EmptyState icon={Wallet} text="هنوز گردشی در تنخواه ثبت نشده." />
      ) : (
        <div className="entity-table-wrap">
          <table className="entity-table petty-table">
            <thead>
              <tr><th>تاریخ</th><th>نوع</th><th>شرح</th><th>مبلغ</th><th>مانده</th></tr>
            </thead>
            <tbody>
              {pg.pageItems.map((t) => (
                <tr key={t.id}>
                  <td data-label="تاریخ">{formatJalali(t.transaction_date)}</td>
                  <td data-label="نوع">
                    <span className={`status-badge ${t.type === 'charge' ? 'tone-success' : 'tone-warning'}`}>
                      {t.type === 'charge' ? 'شارژ' : 'هزینه'}
                    </span>
                  </td>
                  <td data-label="شرح">{t.description || '—'}</td>
                  <td data-label="مبلغ" className={`money-cell ${t.type === 'charge' ? 'pos-in' : 'pos-out'}`}>
                    {t.type === 'charge' ? '+' : '−'}{fa(Number(t.amount))}
                  </td>
                  <td data-label="مانده" className="money-cell"><strong>{fa(t.running)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
  )
}
