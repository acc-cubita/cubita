import { useMemo, useState } from 'react'
import { Download, FileUp, Save, Table2 } from 'lucide-react'
import {
  importContacts,
  importItems,
  type ContactImportRow,
  type ImportResult,
  type ItemImportRow,
} from '../api'
import { downloadCsv, parseCsv, toNumber } from '../lib/csv'
import { SectionCard } from './SectionCard'

/**
 * ورودِ گروهیِ کالا یا اشخاص از CSV.
 *
 * این پنل پیش‌تر تبِ صفحه‌ی «فرآیند راه‌اندازی» بود — جایی که کاربر فقط یک‌بار، آن هم
 * اگر می‌دانست وجود دارد، سراغش می‌رفت. ولی ورودِ گروهی کارِ *همان ماژول* است: فهرستِ
 * کالا به انبار تعلق دارد و فهرستِ اشخاص به طرف‌حساب‌ها. پس پنل مشترک است و هر ماژول
 * آن را به‌عنوانِ یک تبِ خودش نشان می‌دهد. مجوزِ سمتِ سرور هم همین را می‌گوید:
 * `/api/import/items` با مجوزِ «انبار» و `/api/import/contacts` با مجوزِ «فروش» گیت
 * می‌شود، نه با ماژولِ راه‌اندازی.
 */

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

const truthy = (s: string) =>
  ['بله', 'خدمات', 'خدماتی', 'true', '1', 'yes'].includes((s || '').trim().toLowerCase())

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

export function BulkImportPanel({ token, kind }: { token: string; kind: 'items' | 'contacts' }) {
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
