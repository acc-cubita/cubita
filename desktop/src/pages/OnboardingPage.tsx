import { useEffect, useMemo, useState } from 'react'
import { Download, FileUp, Rocket, Save, Table2, Trash2, Wallet } from 'lucide-react'
import {
  createOpeningBalances,
  fetchAccountsLive,
  fetchItemsLive,
  fetchOpeningStatus,
  fetchWarehousesLive,
  importContacts,
  importItems,
  type ContactImportRow,
  type ImportResult,
  type ItemImportRow,
  type OpeningStatus,
} from '../api'
import { downloadCsv, parseCsv } from '../lib/csv'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { Tabs } from '../components/Tabs'
import { JalaliDatePicker } from '../components/JalaliDatePicker'
import { formatJalali } from '../lib/jalali'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

// اعدادِ فارسی/عربی → لاتین، حذفِ جداکننده‌ی هزارگان.
function toNumber(s: string): number {
  const latin = (s || '')
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    .replace(/[،,\s]/g, '')
  const n = Number(latin)
  return Number.isFinite(n) ? n : 0
}

const truthy = (s: string) => ['بله', 'خدمات', 'خدماتی', 'true', '1', 'yes'].includes((s || '').trim().toLowerCase())

function mapType(s: string): string {
  const t = (s || '').trim()
  if (t.includes('تأمین') || t.includes('تامین') || t === 'supplier') return 'supplier'
  if (t.includes('هر') || t === 'both') return 'both'
  return 'customer'
}

function stripHeader(rows: string[][], firstHeader: string): string[][] {
  if (rows.length === 0) return rows
  const c0 = (rows[0][0] || '').trim()
  // ردیفِ اول اگر برچسبِ سرستون بود (نه داده) حذف می‌شود.
  if (c0 === firstHeader || c0 === 'کد کالا' || c0 === 'نام') return rows.slice(1)
  return rows
}

// ── تب ورودِ گروهی (کالا یا اشخاص) ─────────────────────
function ImportTab({
  token,
  kind,
}: {
  token: string
  kind: 'items' | 'contacts'
}) {
  const [text, setText] = useState('')
  const [result, setResult] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isItems = kind === 'items'
  const template = isItems
    ? { headers: ['کد کالا', 'نام', 'دسته', 'واحد', 'خدماتی (بله/خیر)', 'قیمت فروش', 'بارکد'], sample: ['K-100', 'نمونه کالا', 'عمومی', 'عدد', 'خیر', '150000', ''] }
    : { headers: ['نام', 'نوع (مشتری/تأمین‌کننده/هردو)', 'تلفن', 'ایمیل', 'نوع شخص (حقیقی/حقوقی)', 'کد/شناسه ملی', 'کد اقتصادی', 'کد پستی', 'نشانی'], sample: ['شرکت نمونه', 'مشتری', '02112345678', '', 'حقوقی', '10101010101', '411111111111', '1234567890', 'تهران'] }

  const parsed = useMemo(() => {
    if (!text.trim()) return [] as string[][]
    return stripHeader(parseCsv(text), template.headers[0])
  }, [text, template.headers])

  function downloadTemplate() {
    downloadCsv(isItems ? 'قالب-کالا' : 'قالب-اشخاص', template.headers, [template.sample])
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setText(await file.text())
    setResult(null)
    e.target.value = ''
  }

  async function submit() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      if (isItems) {
        const rows: ItemImportRow[] = parsed.map((c) => ({
          sku: (c[0] || '').trim(),
          name: (c[1] || '').trim(),
          category: (c[2] || '').trim(),
          unit: (c[3] || '').trim() || 'عدد',
          is_service: truthy(c[4] || ''),
          sales_price: toNumber(c[5] || '0'),
          barcode: (c[6] || '').trim() || null,
        }))
        setResult(await importItems(token, rows))
      } else {
        const rows: ContactImportRow[] = parsed.map((c) => ({
          name: (c[0] || '').trim(),
          type: mapType(c[1] || ''),
          phone: (c[2] || '').trim() || null,
          email: (c[3] || '').trim() || null,
          entity_type: (c[4] || '').includes('حقوق') ? 'legal' : 'real',
          national_id: (c[5] || '').trim() || null,
          economic_code: (c[6] || '').trim() || null,
          postal_code: (c[7] || '').trim() || null,
          address: (c[8] || '').trim(),
        }))
        setResult(await importContacts(token, rows))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={FileUp}
      title={isItems ? 'ورودِ گروهیِ کالا' : 'ورودِ گروهیِ اشخاص'}
      description="فایلِ اکسل را با فرمتِ CSV ذخیره کنید، یا محتوای آن را اینجا بچسبانید. ردیفِ سرستون اختیاری است."
      actions={
        <button type="button" onClick={downloadTemplate}>
          <Download size={13} /> دانلود قالب نمونه
        </button>
      }
    >
      <div className="invoice-form form-full">
        <label>
          بارگذاری فایل CSV
          <input type="file" accept=".csv,text/csv" onChange={onFile} />
        </label>
        <label>
          یا چسباندنِ محتوا (CSV)
          <textarea
            rows={5}
            value={text}
            onChange={(e) => { setText(e.target.value); setResult(null) }}
            placeholder={template.headers.join('،') + ' ...'}
            style={{ width: '100%', fontFamily: 'monospace', direction: 'ltr' }}
          />
        </label>
      </div>

      {parsed.length > 0 && (
        <p className="hint">
          <Table2 size={13} /> {fa(parsed.length)} ردیف آماده‌ی ثبت است.
        </p>
      )}

      <div className="invoice-form-footer">
        <button type="button" className="btn-primary" onClick={() => void submit()} disabled={busy || parsed.length === 0}>
          <Save size={14} /> ثبتِ گروهی
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="hint" style={{ marginTop: 8 }}>
          <p>✅ {fa(result.created)} مورد ثبت شد. {result.skipped > 0 && `— ${fa(result.skipped)} تکراری رد شد.`}</p>
          {result.errors.length > 0 && (
            <div className="error">
              {fa(result.errors.length)} ردیف خطا داشت:
              <ul>
                {result.errors.slice(0, 20).map((e) => (
                  <li key={e.row}>ردیف {fa(e.row)}: {e.message}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  )
}

// ── تب مانده‌های اول دوره ──────────────────────────────
type AccLine = { account_id: string; debit: string; credit: string }
type StockLine = { item_id: string; warehouse_id: string; qty: string; unit_cost: string }

function OpeningTab({ token }: { token: string }) {
  const [status, setStatus] = useState<OpeningStatus | null>(null)
  const [accounts, setAccounts] = useState<{ id: string; code: string; name: string; is_group: number }[]>([])
  const [items, setItems] = useState<{ id: string; sku: string; name: string; is_service: boolean }[]>([])
  const [warehouses, setWarehouses] = useState<{ id: string; name: string }[]>([])
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [lines, setLines] = useState<AccLine[]>([{ account_id: '', debit: '', credit: '' }])
  const [stock, setStock] = useState<StockLine[]>([])
  const [balancingId, setBalancingId] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setError(null)
    try {
      const [st, accs, its, whs] = await Promise.all([
        fetchOpeningStatus(token),
        fetchAccountsLive(token),
        fetchItemsLive(token),
        fetchWarehousesLive(token),
      ])
      setStatus(st)
      setAccounts(accs)
      setItems(its.filter((i) => !i.is_service))
      setWarehouses(whs)
      const capital = accs.find((a) => a.code === '3101')
      if (capital) setBalancingId(capital.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => { void refresh() }, [])

  const postable = accounts.filter((a) => !a.is_group)
  const stockValue = stock.reduce((s, r) => s + toNumber(r.qty) * toNumber(r.unit_cost), 0)
  const totalDebit = lines.reduce((s, r) => s + toNumber(r.debit), 0) + stockValue
  const totalCredit = lines.reduce((s, r) => s + toNumber(r.credit), 0)
  const diff = totalDebit - totalCredit

  async function submit() {
    setBusy(true)
    setMessage(null)
    setError(null)
    try {
      await createOpeningBalances(token, {
        entry_date: date,
        lines: lines
          .filter((l) => l.account_id && (toNumber(l.debit) > 0 || toNumber(l.credit) > 0))
          .map((l) => ({ account_id: l.account_id, debit: toNumber(l.debit), credit: toNumber(l.credit) })),
        stock: stock
          .filter((s) => s.item_id && s.warehouse_id && toNumber(s.qty) > 0)
          .map((s) => ({ item_id: s.item_id, warehouse_id: s.warehouse_id, qty: toNumber(s.qty), unit_cost: toNumber(s.unit_cost) })),
        balancing_account_id: balancingId || null,
      })
      setMessage('سند افتتاحیه با موفقیت ثبت شد.')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  if (status?.exists) {
    return (
      <SectionCard icon={Wallet} title="مانده‌های اول دوره">
        <p className="hint">
          سند افتتاحیه‌ی این کسب‌وکار قبلاً ثبت شده است (شماره {fa(status.entry_number ?? 0)}، تاریخ{' '}
          {status.entry_date ? formatJalali(status.entry_date) : '—'}). برای جلوگیری از دوباره‌کاری، فقط یک سند
          افتتاحیه مجاز است؛ اصلاحات را از طریق «سند دستی» در صفحه‌ی حسابداری انجام دهید.
        </p>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      icon={Wallet}
      title="مانده‌های اول دوره (سند افتتاحیه)"
      description="مانده‌ی حساب‌ها و موجودیِ انبار را هنگامِ شروعِ کار با کوبیتا وارد کنید. اختلافِ تراز به‌طور خودکار به حسابِ سرمایه بسته می‌شود."
    >
      <div className="invoice-form form-full">
        <label>
          تاریخِ افتتاحیه
          <JalaliDatePicker value={date} onChange={setDate} />
        </label>
        <label>
          حسابِ تراز (سرمایه)
          <select value={balancingId} onChange={(e) => setBalancingId(e.target.value)}>
            <option value="">— بدون تراز خودکار (باید متوازن باشد) —</option>
            {postable.map((a) => (
              <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
            ))}
          </select>
        </label>
      </div>

      <h4 style={{ marginTop: 12 }}>مانده‌ی حساب‌ها</h4>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>حساب</th><th>بدهکار</th><th>بستانکار</th><th></th></tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i}>
                <td>
                  <select value={l.account_id} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, account_id: e.target.value } : x))}>
                    <option value="">— انتخاب حساب —</option>
                    {postable.map((a) => (
                      <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                    ))}
                  </select>
                </td>
                <td><input type="number" min="0" value={l.debit} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, debit: e.target.value, credit: '' } : x))} /></td>
                <td><input type="number" min="0" value={l.credit} onChange={(e) => setLines(lines.map((x, j) => j === i ? { ...x, credit: e.target.value, debit: '' } : x))} /></td>
                <td><button type="button" onClick={() => setLines(lines.filter((_, j) => j !== i))}><Trash2 size={13} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" onClick={() => setLines([...lines, { account_id: '', debit: '', credit: '' }])}>+ افزودن ردیف</button>

      <h4 style={{ marginTop: 16 }}>موجودیِ اول دوره (اختیاری)</h4>
      <p className="hint">ارزشِ موجودی خودکار به‌عنوانِ بدهکارِ «موجودی کالا» به سند اضافه می‌شود — حسابِ موجودی را دستی وارد نکنید.</p>
      {warehouses.length > 0 && (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>کالا</th><th>انبار</th><th>تعداد</th><th>بهای واحد</th><th>ارزش</th><th></th></tr>
              </thead>
              <tbody>
                {stock.map((s, i) => (
                  <tr key={i}>
                    <td>
                      <select value={s.item_id} onChange={(e) => setStock(stock.map((x, j) => j === i ? { ...x, item_id: e.target.value } : x))}>
                        <option value="">— انتخاب کالا —</option>
                        {items.map((it) => (<option key={it.id} value={it.id}>{it.sku} — {it.name}</option>))}
                      </select>
                    </td>
                    <td>
                      <select value={s.warehouse_id} onChange={(e) => setStock(stock.map((x, j) => j === i ? { ...x, warehouse_id: e.target.value } : x))}>
                        <option value="">— انبار —</option>
                        {warehouses.map((w) => (<option key={w.id} value={w.id}>{w.name}</option>))}
                      </select>
                    </td>
                    <td><input type="number" min="0" value={s.qty} onChange={(e) => setStock(stock.map((x, j) => j === i ? { ...x, qty: e.target.value } : x))} /></td>
                    <td><input type="number" min="0" value={s.unit_cost} onChange={(e) => setStock(stock.map((x, j) => j === i ? { ...x, unit_cost: e.target.value } : x))} /></td>
                    <td className="money-cell">{fa(toNumber(s.qty) * toNumber(s.unit_cost))}</td>
                    <td><button type="button" onClick={() => setStock(stock.filter((_, j) => j !== i))}><Trash2 size={13} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button type="button" onClick={() => setStock([...stock, { item_id: '', warehouse_id: warehouses[0]?.id ?? '', qty: '', unit_cost: '' }])}>+ افزودن موجودی</button>
        </>
      )}

      <div className="opening-totals" style={{ marginTop: 12 }}>
        <span>جمع بدهکار: <b>{fa(totalDebit)}</b></span>
        {'  '}| جمع بستانکار: <b>{fa(totalCredit)}</b>
        {'  '}| {diff === 0 ? <b style={{ color: 'var(--success, green)' }}>متوازن ✓</b> : <b style={{ color: 'var(--danger, crimson)' }}>اختلاف: {fa(Math.abs(diff))}</b>}
        {diff !== 0 && balancingId && <span className="hint"> (به سرمایه بسته می‌شود)</span>}
      </div>

      <div className="invoice-form-footer">
        <button type="button" className="btn-primary" onClick={() => void submit()} disabled={busy}>
          <Save size={14} /> ثبتِ سند افتتاحیه
        </button>
      </div>
      {message && <div className="hint">{message}</div>}
      {error && <div className="error">{error}</div>}
    </SectionCard>
  )
}

export function OnboardingPage({ token }: { token: string }) {
  return (
    <div className="page">
      <PageHeader
        icon={Rocket}
        title="راه‌اندازی و ورود اطلاعات"
        description="کسب‌وکارتان را سریع راه‌اندازی کنید: فهرستِ کالا و اشخاص را گروهی وارد کنید و مانده‌های اول دوره را ثبت کنید."
      />
      <Tabs
        tabs={[
          { key: 'items', label: 'ورود گروهی کالا', icon: FileUp, content: <ImportTab token={token} kind="items" /> },
          { key: 'contacts', label: 'ورود گروهی اشخاص', icon: FileUp, content: <ImportTab token={token} kind="contacts" /> },
          { key: 'opening', label: 'مانده اول دوره', icon: Wallet, content: <OpeningTab token={token} /> },
        ]}
      />
    </div>
  )
}
