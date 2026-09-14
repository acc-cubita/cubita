import { useCallback, useEffect, useState } from 'react'
import { PackageSearch, Search } from 'lucide-react'
import { searchSerials, type SerialTrace } from '../api'
import { formatJalali } from '../lib/jalali'
import { JalaliDatePicker } from './JalaliDatePicker'

/**
 * جست‌وجوی سریال — یک ردیابیِ میان‌سندی، نه یک فهرستِ موجودی.
 *
 * پیش از این سریال یک بن‌بست بود: به بچِ ورودش وصل بود و فروش هیچ‌وقت لمسش
 * نمی‌کرد، پس «به چه کسی فروخته شد؟» جوابی نداشت و «کجاست؟» تا ابد «در همان بچِ
 * اول» می‌ماند.
 *
 * هر نتیجه **کلِ تاریخچه‌اش** را می‌آورد، نه فقط آخرین وضعیت — وگرنه باز یک
 * بن‌بستِ تازه ساخته‌ایم. «در انبار» هم مشتق است از آخرین رویداد، نه ستونی که
 * با هر حرکت بازنویسی شود.
 */
export function SerialSearchTab({ token }: { token: string }) {
  const [serial, setSerial] = useState('')
  const [range, setRange] = useState<{ from: string; to: string }>({ from: '', to: '' })
  const [rows, setRows] = useState<SerialTrace[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<Record<string, boolean>>({})

  const run = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      setRows(
        await searchSerials(token, {
          serial: serial.trim() || undefined,
          date_from: range.from || undefined,
          date_to: range.to || undefined,
        }),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }, [token, serial, range.from, range.to])

  useEffect(() => {
    void run()
    // بارِ اول: همه‌ی سریال‌ها. جست‌وجو با دکمه انجام می‌شود، نه با هر حرف.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <section className="stack">
      <p className="muted">
        هر سریال با <strong>کلِ تاریخچه‌اش</strong> می‌آید — از کدام سند وارد شد، با کدام سند
        خارج شد، و به چه کسی. «در انبار» از آخرین رویداد مشتق می‌شود.
      </p>

      <div className="toolbar">
        <label className="field">
          <span>سریال</span>
          <input
            value={serial}
            onChange={(e) => setSerial(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void run() }}
            placeholder="بخشی از سریال"
            dir="ltr"
          />
        </label>
        <label className="field">
          <span>از تاریخ</span>
          <JalaliDatePicker value={range.from} onChange={(v) => setRange((r) => ({ ...r, from: v }))} />
        </label>
        <label className="field">
          <span>تا تاریخ</span>
          <JalaliDatePicker value={range.to} onChange={(v) => setRange((r) => ({ ...r, to: v }))} />
        </label>
        <button type="button" className="btn-primary" disabled={busy} onClick={() => void run()}>
          <Search size={15} /> {busy ? 'در حال جست‌وجو…' : 'جست‌وجو'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {rows === null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <p className="muted">
          سریالی با این شرایط پیدا نشد. سریال‌ها از «بچ و انقضا» به هر بارِ ورودی اضافه می‌شوند.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="entity-table cards-on-mobile">
            <thead>
              <tr>
                <th>سریال</th>
                <th>کالا</th>
                <th>بچ</th>
                <th>وضعیت</th>
                <th>آخرین رویداد</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <Trace
                  key={row.serial_id}
                  row={row}
                  open={!!open[row.serial_id]}
                  onToggle={() => setOpen((o) => ({ ...o, [row.serial_id]: !o[row.serial_id] }))}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Trace({ row, open, onToggle }: { row: SerialTrace; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr>
        <td className="card-title" data-label="سریال" dir="ltr">{row.serial}</td>
        <td data-label="کالا">
          <div className="entity-name">{row.item_name}</div>
          <div className="entity-sub">{row.item_sku}</div>
        </td>
        <td data-label="بچ">{row.batch_number || '—'}</td>
        <td data-label="وضعیت">
          <span className={row.in_stock ? 'text-success' : 'muted'}>
            {row.in_stock ? 'در انبار' : 'خارج شده'}
          </span>
        </td>
        <td data-label="آخرین رویداد">
          {row.last_event_label || '—'}
          {row.last_entry_date ? ` — ${formatJalali(row.last_entry_date)}` : ''}
        </td>
        <td className="card-actions">
          <button type="button" onClick={onToggle}>
            <PackageSearch size={13} /> {open ? 'بستن' : `تاریخچه (${row.events.length.toLocaleString('fa-IR')})`}
          </button>
        </td>
      </tr>
      {open && (
        <tr className="card-full">
          <td colSpan={6}>
            <div className="table-scroll">
              <table className="entity-table table-plain">
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>رویداد</th>
                    <th>سند</th>
                    <th>طرف حساب</th>
                  </tr>
                </thead>
                <tbody>
                  {row.events.map((e, i) => (
                    <tr key={i}>
                      <td>{formatJalali(e.entry_date)}</td>
                      <td>{e.event_label}</td>
                      <td>
                        {e.source_label}
                        {e.source_number != null ? ` #${e.source_number.toLocaleString('fa-IR')}` : ''}
                      </td>
                      <td>{e.counterparty || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
