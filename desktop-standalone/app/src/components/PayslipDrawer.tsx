import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, Printer } from 'lucide-react'
import type { PayslipRecord } from '../api'
import { JALALI_MONTH_NAMES } from '../lib/jalali'

const fa = (v: string | number) => Math.round(Number(v || 0)).toLocaleString('fa-IR')

export type PayslipEmployee = { first_name: string; last_name: string; national_id: string }
export type PayslipPeriod = { year: number; month: number }

/**
 * فیشِ حقوقیِ یک کارمند با ریزِ کاملِ درآمد و کسورات، و دکمه‌ی چاپ (پنجره‌ی مستقلِ چاپ
 * که خودش را چاپ می‌کند — بدونِ نیاز به اندپوینتِ سرور، مثل نمای چاپیِ سبک).
 */
export function PayslipDrawer({
  payslip, employee, period, onClose,
}: {
  payslip: PayslipRecord
  employee: PayslipEmployee | undefined
  period: PayslipPeriod | undefined
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const name = employee ? `${employee.first_name} ${employee.last_name}`.trim() : '—'
  const periodLabel = period ? `${JALALI_MONTH_NAMES[period.month - 1]} ${period.year}` : '—'

  const earnings: [string, string][] = [
    ['حقوقِ پایه', payslip.base_salary],
    ['مزایا (مسکن، خواربار، سایر)', payslip.allowances_total],
    ['اضافه‌کاری', payslip.overtime_pay],
  ]
  const deductions: [string, string][] = [
    ['بیمه — سهمِ کارمند', payslip.insurance_employee_share],
    ['مالیاتِ حقوق', payslip.tax_amount],
  ]

  function printPayslip() {
    const win = window.open('', '_blank', 'width=820,height=1000')
    if (!win) return
    const row = (label: string, value: string, strong = false) =>
      `<tr${strong ? ' class="strong"' : ''}><td>${label}</td><td class="num">${fa(value)}</td></tr>`
    win.document.write(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>فیشِ حقوقی ${payslip.number ?? ''} — ${name}</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Vazirmatn, Tahoma, sans-serif; margin: 28px; color: #1f2937; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .muted { color: #6b7280; font-size: 13px; }
  .head { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #111827; padding-bottom: 12px; margin-bottom: 16px; }
  .meta { text-align: left; font-size: 13px; line-height: 1.9; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 18px; }
  th { text-align: right; background: #f3f4f6; font-size: 13px; padding: 8px 10px; border: 1px solid #e5e7eb; }
  td { padding: 8px 10px; border: 1px solid #e5e7eb; font-size: 13.5px; }
  td.num { text-align: left; font-variant-numeric: tabular-nums; }
  tr.strong td { font-weight: 800; background: #f9fafb; }
  .net { display: flex; justify-content: space-between; align-items: center; border: 2px solid #111827; border-radius: 10px; padding: 14px 18px; font-size: 17px; font-weight: 800; }
  .cols { display: flex; gap: 20px; }
  .cols > div { flex: 1; }
  .foot { margin-top: 26px; color: #6b7280; font-size: 11.5px; line-height: 1.8; }
</style></head><body>
  <div class="head">
    <div>
      <h1>فیشِ حقوقی</h1>
      <div class="muted">دوره: ${periodLabel}</div>
    </div>
    <div class="meta">
      <div>کارمند: <strong>${name}</strong></div>
      <div>کد ملی: ${employee?.national_id ?? '—'}</div>
      <div>شماره فیش: ${payslip.number ?? '—'}</div>
    </div>
  </div>
  <div class="cols">
    <div>
      <table>
        <thead><tr><th>درآمد</th><th class="num">ریال</th></tr></thead>
        <tbody>
          ${earnings.map(([l, v]) => row(l, v)).join('')}
          ${row('جمعِ ناخالص', payslip.gross_pay, true)}
        </tbody>
      </table>
    </div>
    <div>
      <table>
        <thead><tr><th>کسورات</th><th class="num">ریال</th></tr></thead>
        <tbody>
          ${deductions.map(([l, v]) => row(l, v)).join('')}
          ${row('جمعِ کسورات', String(Number(payslip.insurance_employee_share) + Number(payslip.tax_amount)), true)}
        </tbody>
      </table>
    </div>
  </div>
  <div class="net"><span>خالصِ پرداختی</span><span>${fa(payslip.net_pay)} ریال</span></div>
  <div class="foot">
    حقوقِ مشمولِ مالیات: ${fa(payslip.taxable_pay)} ریال — بیمه‌ی سهمِ کارفرما: ${fa(payslip.insurance_employer_share)} ریال.<br>
    این فیش بر پایه‌ی حکمِ حقوقیِ جاری و کارکردِ همان دوره صادر شده است.
  </div>
  <script>window.onload = function(){ window.print(); }</script>
</body></html>`)
    win.document.close()
  }

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <div>
              <div className="drawer-title-main">فیشِ حقوقی: {name}</div>
              <div className="drawer-title-sub">دوره {periodLabel} · شماره {payslip.number ?? '—'}</div>
            </div>
          </div>
          <div className="drawer-head-actions">
            <button type="button" className="btn-primary" onClick={printPayslip}><Printer size={15} /> چاپ</button>
            <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن"><X size={18} /></button>
          </div>
        </div>

        <div className="drawer-body">
          <div className="kardex-summary">
            <div className="kardex-stat"><span>جمعِ ناخالص</span><strong>{fa(payslip.gross_pay)}</strong></div>
            <div className="kardex-stat"><span>کسورات</span><strong className="pos-out">{fa(Number(payslip.insurance_employee_share) + Number(payslip.tax_amount))}</strong></div>
            <div className="kardex-stat"><span>خالصِ پرداختی</span><strong className="pos-in">{fa(payslip.net_pay)}</strong></div>
          </div>

          <div className="entity-table-wrap">
            <table className="entity-table payslip-lines-table">
              <tbody>
                <tr><td data-label="ردیف">حقوقِ پایه</td><td data-label="مبلغ" className="money-cell">{fa(payslip.base_salary)}</td></tr>
                <tr><td data-label="ردیف">مزایا (مسکن، خواربار، سایر)</td><td data-label="مبلغ" className="money-cell">{fa(payslip.allowances_total)}</td></tr>
                <tr><td data-label="ردیف">اضافه‌کاری</td><td data-label="مبلغ" className="money-cell">{fa(payslip.overtime_pay)}</td></tr>
                <tr className="payslip-subtotal"><td data-label="ردیف">جمعِ ناخالص</td><td data-label="مبلغ" className="money-cell"><strong>{fa(payslip.gross_pay)}</strong></td></tr>
                <tr><td data-label="ردیف">بیمه — سهمِ کارمند</td><td data-label="مبلغ" className="money-cell pos-out">−{fa(payslip.insurance_employee_share)}</td></tr>
                <tr><td data-label="ردیف">مالیاتِ حقوق</td><td data-label="مبلغ" className="money-cell pos-out">−{fa(payslip.tax_amount)}</td></tr>
                <tr className="payslip-net"><td data-label="ردیف">خالصِ پرداختی</td><td data-label="مبلغ" className="money-cell"><strong>{fa(payslip.net_pay)}</strong></td></tr>
              </tbody>
            </table>
          </div>

          <p className="field-hint">
            حقوقِ مشمولِ مالیات: {fa(payslip.taxable_pay)} ریال — بیمه‌ی سهمِ کارفرما: {fa(payslip.insurance_employer_share)} ریال.
          </p>
        </div>
      </div>
    </div>,
    document.body,
  )
}
