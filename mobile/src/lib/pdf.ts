import * as Print from 'expo-print'
import * as Sharing from 'expo-sharing'
import { KIND_LABEL } from '../api/contacts'
import type { ContactStatement } from '../api/types'

// ساختِ PDFِ کارتِ حساب سمتِ اپ (expo-print از HTML) و اشتراک با شیتِ اندروید
// (واتس‌اپ/ایمیل/…). بک‌اند برای این گزارش endpointِ PDF ندارد، پس اینجا رندر می‌شود.

const fa = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')

function balanceLabel(v: number): string {
  if (v > 0) return `${fa(v)} (بدهکار به شما)`
  if (v < 0) return `${fa(-v)} (بستانکار)`
  return '۰ (تسویه)'
}

function buildHtml(s: ContactStatement): string {
  const rows = s.lines
    .map(
      (l) => `
      <tr>
        <td>${l.txn_date}</td>
        <td>${KIND_LABEL[l.kind] ?? l.kind}${l.number != null ? ` #${l.number.toLocaleString('fa-IR')}` : ''}</td>
        <td class="num">${Number(l.debit) ? fa(l.debit) : ''}</td>
        <td class="num">${Number(l.credit) ? fa(l.credit) : ''}</td>
        <td class="num">${fa(l.balance)}</td>
      </tr>`,
    )
    .join('')

  return `<!doctype html><html dir="rtl" lang="fa"><head><meta charset="utf-8"/>
  <style>
    * { font-family: 'Vazirmatn', 'Tahoma', sans-serif; box-sizing: border-box; }
    body { margin: 24px; color: #16181d; }
    h1 { font-size: 20px; margin: 0 0 4px; }
    .muted { color: #6b7280; font-size: 12px; }
    .summary { display: flex; gap: 16px; margin: 16px 0; }
    .box { flex: 1; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px 12px; }
    .box .k { color: #6b7280; font-size: 11px; }
    .box .v { font-size: 15px; font-weight: 700; margin-top: 2px; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 12px; }
    th, td { text-align: right; padding: 7px 8px; border-bottom: 1px solid #eef0f3; }
    th { background: #f8f9fb; color: #6b7280; font-weight: 600; }
    td.num, th.num { text-align: left; font-variant-numeric: tabular-nums; }
    .foot { margin-top: 14px; font-size: 14px; font-weight: 700; }
  </style></head><body>
    <h1>کارتِ حساب — ${s.contact_name}</h1>
    <div class="muted">تاریخِ گزارش: ${new Date().toLocaleDateString('fa-IR')}</div>
    <div class="summary">
      <div class="box"><div class="k">ماندهٔ ابتدای دوره</div><div class="v">${balanceLabel(Number(s.opening_balance))}</div></div>
      <div class="box"><div class="k">ماندهٔ نهایی</div><div class="v">${balanceLabel(Number(s.closing_balance))}</div></div>
    </div>
    <table>
      <thead><tr><th>تاریخ</th><th>شرح</th><th class="num">بدهکار</th><th class="num">بستانکار</th><th class="num">مانده</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5" class="muted">تراکنشی ثبت نشده است.</td></tr>'}</tbody>
    </table>
    <div class="foot">ماندهٔ نهایی: ${balanceLabel(Number(s.closing_balance))}</div>
  </body></html>`
}

/** کارتِ حساب را به PDF تبدیل و از طریقِ شیتِ اشتراکِ اندروید به‌اشتراک می‌گذارد. */
export async function shareStatementPdf(s: ContactStatement): Promise<void> {
  const { uri } = await Print.printToFileAsync({ html: buildHtml(s) })
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(uri, {
      mimeType: 'application/pdf',
      dialogTitle: `کارتِ حساب — ${s.contact_name}`,
      UTI: 'com.adobe.pdf',
    })
  }
}
