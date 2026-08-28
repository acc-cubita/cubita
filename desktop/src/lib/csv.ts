// تولیدِ CSV سمتِ کلاینت برای گزارش‌ها.
//
// **چرا سمتِ کلاینت:** داده‌ی هر گزارش همین حالا برای نمایش گرفته شده؛ ساختنِ دوباره‌اش
// روی سرور یعنی ۱۵ اندپوینتِ تازه برای کاری که مرورگر خودش می‌تواند. هم در وب و هم در
// رندررِ الکترون (که کرومیوم است) `Blob` + `<a download>` کار می‌کند.
//
// **BOM عمدی است:** بدون `﻿` ابتدای فایل، اکسل ویندوزی UTF-8 را به کدپیجِ محلی
// می‌خواند و فارسی به هم می‌ریزد. اعداد را دست‌نخورده (لاتین) نگه می‌داریم تا اکسل
// آن‌ها را «عدد» بفهمد و بشود جمع/مرتب کرد؛ فقط تاریخ‌ها به‌صورت متنِ شمسی می‌روند.

function escapeCell(value: string | number): string {
  const text = value == null ? '' : String(value)
  // ویرگول، نقل‌قول و خط جدید باید داخل نقل‌قول بروند؛ نقل‌قولِ داخلی دوبل می‌شود.
  if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`
  return text
}

/** پارسِ متنِ CSV به آرایه‌ای از ردیف‌ها (هر ردیف آرایه‌ی سلول‌های متنی).
 * نقل‌قول، ویرگول و خط جدیدِ داخلِ سلول را درست می‌فهمد؛ BOM و ردیف‌های خالی حذف می‌شوند. */
export function parseCsv(text: string): string[][] {
  const clean = text.replace(/^﻿/, '')
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false
  for (let i = 0; i < clean.length; i++) {
    const ch = clean[i]
    if (inQuotes) {
      if (ch === '"') {
        if (clean[i + 1] === '"') { cell += '"'; i++ } else inQuotes = false
      } else cell += ch
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      row.push(cell); cell = ''
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && clean[i + 1] === '\n') i++
      row.push(cell); cell = ''
      if (row.some((c) => c.trim() !== '')) rows.push(row)
      row = []
    } else cell += ch
  }
  if (cell !== '' || row.length > 0) {
    row.push(cell)
    if (row.some((c) => c.trim() !== '')) rows.push(row)
  }
  return rows
}

export function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]): void {
  const body = [headers, ...rows].map((row) => row.map(escapeCell).join(',')).join('\r\n')
  const blob = new Blob(['﻿' + body], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/** رشته‌ی عددیِ واردشده (فارسی/عربی/لاتین، با یا بدونِ جداکننده‌ی هزارگان) → عدد.
 *
 * ورودیِ گروهی از فایلِ کاربر می‌آید و ستونِ «قیمت» ممکن است «۱۵۰,۰۰۰» باشد؛ `Number()`
 * خام روی چنین رشته‌ای NaN می‌دهد و ردیف بی‌صدا صفر ثبت می‌شود. مقدارِ نامعتبر عمداً
 * صفر می‌شود نه NaN — تا محاسبه‌ی جمع‌ها نشکند. */
export function toNumber(s: string): number {
  const latin = (s || '')
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    .replace(/[،,\s]/g, '')
  const n = Number(latin)
  return Number.isFinite(n) ? n : 0
}
