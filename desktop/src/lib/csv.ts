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
