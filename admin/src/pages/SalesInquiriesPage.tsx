/**
 * درخواست‌های خرید و مشاوره — صفِ فرمِ «تماس برای خرید»ِ cubita.ir.
 *
 * پلن‌های قیمت‌دار از سایت برداشته شدند (۱۴۰۵/۰۷/۰۳)؛ خریدارِ هر چهار محصول این فرم را پر می‌کند و
 * کارشناسِ فروش این‌جا تماس می‌گیرد، وضعیت را جلو می‌برد و یادداشت می‌گذارد. هر تغییر در ردِ کارهای
 * ستاد ثبت می‌شود (سمتِ سرور).
 */
import { useState } from 'react'
import { PhoneCall, RefreshCw } from 'lucide-react'

import {
  fetchSalesInquiries,
  updateSalesInquiry,
  type SalesInquiry,
  type SalesProduct,
  type SalesStatus,
  type StaffMe,
} from '../api'
import { formatJalali, toFaDigits } from '../lib/jalali'
import { AsyncBlock, Card, Chip, Dialog, Field, Note, PageHeader, Stat, TableScroll, faInt, useAsync } from '../ui/kit'

type Msg = { kind: 'ok' | 'bad'; text: string } | null

const PRODUCT_LABEL: Record<SalesProduct, string> = {
  cloud: 'کوبیتا ابری (وب)',
  desktop: 'نسخه‌ی دسکتاپ',
  enterprise: 'کوبیتا سازمانی',
  mobile: 'اپ موبایل',
  unsure: 'هنوز نمی‌داند',
}
const STATUS_LABEL: Record<SalesStatus, string> = {
  new: 'تازه',
  contacted: 'تماس گرفته شد',
  won: 'فروخته شد',
  lost: 'منتفی',
}
const STATUS_TONE: Record<SalesStatus, 'ok' | 'warn' | 'bad' | 'mute'> = {
  new: 'warn',
  contacted: 'mute',
  won: 'ok',
  lost: 'bad',
}

function canEdit(me: StaffMe): boolean {
  //: همان معناشناسیِ `staff_roles.has_permission`. گاردِ واقعی سرور است.
  for (const key of ['sales', '*']) {
    const actions = me.permissions[key]
    if (actions && (actions.includes('edit') || actions.includes('*'))) return true
  }
  return false
}

export default function SalesInquiriesPage({
  token,
  me,
  onUnauthorized,
}: {
  token: string
  me: StaffMe
  onUnauthorized: (e: unknown) => void
}) {
  const [filter, setFilter] = useState<SalesStatus | ''>('')
  const [open, setOpen] = useState<SalesInquiry | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const { data, loading, error, reload } = useAsync(
    () => fetchSalesInquiries(token, filter).catch((e) => (onUnauthorized(e), Promise.reject(e))),
    [token, filter],
  )
  const rows = data?.items ?? []
  const editable = canEdit(me)

  return (
    <>
      <PageHeader
        icon={PhoneCall}
        title="درخواست‌های خرید"
        description="کسانی که در cubita.ir فرمِ «تماس برای خرید» را پر کرده‌اند — با هرکدام تماس بگیرید و وضعیت را جلو ببرید."
        actions={
          <button type="button" className="ad-btn" onClick={reload}>
            <RefreshCw size={15} /> تازه‌سازی
          </button>
        }
      />

      <div className="ad-stats">
        <Stat label="درخواستِ تازه" value={faInt(data?.new_count ?? 0)} />
      </div>

      <Card>
        <div className="ad-toolbar">
          <label className="ad-field-inline">
            وضعیت
            <select value={filter} onChange={(e) => setFilter(e.target.value as SalesStatus | '')}>
              <option value="">همه</option>
              {(Object.keys(STATUS_LABEL) as SalesStatus[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <span className="ad-count">{faInt(rows.length)} درخواست</span>
        </div>
        <Note msg={msg} />

        <AsyncBlock loading={loading} error={error} empty={rows.length === 0} emptyText="درخواستی در این وضعیت نیست.">
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>نام و شرکت</th>
                  <th>محصول</th>
                  <th>تماس</th>
                  <th>زمان</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="نام و شرکت">
                      {r.name}
                      {r.company ? <span className="ad-sub">{r.company}</span> : null}
                    </td>
                    <td data-label="محصول">
                      {PRODUCT_LABEL[r.product]}
                      {r.seats ? <span className="ad-sub">{toFaDigits(r.seats)} کاربر</span> : null}
                    </td>
                    <td data-label="تماس">
                      {r.phone ? (
                        <a href={`tel:${r.phone}`} dir="ltr">
                          {toFaDigits(r.phone)}
                        </a>
                      ) : null}
                      {r.email ? (
                        <a className="ad-sub" href={`mailto:${r.email}`} dir="ltr">
                          {r.email}
                        </a>
                      ) : null}
                    </td>
                    <td data-label="زمان">{formatJalali(r.created_at)}</td>
                    <td data-label="وضعیت">
                      <Chip text={STATUS_LABEL[r.status]} tone={STATUS_TONE[r.status]} />
                    </td>
                    <td className="card-actions">
                      <button type="button" className="ad-btn small" onClick={() => setOpen(r)}>
                        {editable ? 'پیگیری' : 'جزئیات'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </AsyncBlock>
      </Card>

      {open ? (
        <InquiryDialog
          token={token}
          row={open}
          editable={editable}
          onClose={() => setOpen(null)}
          onSaved={(r) => {
            setOpen(null)
            setMsg({ kind: 'ok', text: `درخواستِ «${r.name}» به‌روز شد: ${STATUS_LABEL[r.status]}.` })
            reload()
          }}
          onUnauthorized={onUnauthorized}
        />
      ) : null}
    </>
  )
}

function InquiryDialog({
  token,
  row,
  editable,
  onClose,
  onSaved,
  onUnauthorized,
}: {
  token: string
  row: SalesInquiry
  editable: boolean
  onClose: () => void
  onSaved: (r: SalesInquiry) => void
  onUnauthorized: (e: unknown) => void
}) {
  const [status, setStatus] = useState<SalesStatus>(row.status)
  const [note, setNote] = useState(row.staff_note)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<Msg>(null)
  const dirty = status !== row.status || note.trim() !== row.staff_note

  async function save() {
    setBusy(true)
    setErr(null)
    try {
      onSaved(await updateSalesInquiry(token, row.id, { status, staff_note: note }))
    } catch (e) {
      onUnauthorized(e)
      setErr({ kind: 'bad', text: e instanceof Error ? e.message : 'خطای ناشناخته' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      title={`درخواستِ ${row.name}`}
      onClose={onClose}
      footer={
        editable ? (
          <button type="button" className="ad-btn primary" disabled={!dirty || busy} onClick={() => void save()}>
            {busy ? 'در حال ذخیره…' : 'ذخیره'}
          </button>
        ) : null
      }
    >
      <dl className="ad-dl">
        <dt>محصول</dt>
        <dd>
          {PRODUCT_LABEL[row.product]}
          {row.seats ? ` — ${toFaDigits(row.seats)} کاربر` : ''}
        </dd>
        {row.company ? (
          <>
            <dt>شرکت</dt>
            <dd>{row.company}</dd>
          </>
        ) : null}
        <dt>پیام</dt>
        <dd className="ad-pre">{row.message || '—'}</dd>
        {row.handled_by ? (
          <>
            <dt>آخرین پیگیری</dt>
            <dd>
              {row.handled_by} — {row.handled_at ? formatJalali(row.handled_at) : ''}
            </dd>
          </>
        ) : null}
      </dl>
      {editable ? (
        <>
          <Field label="وضعیت">
            <select value={status} onChange={(e) => setStatus(e.target.value as SalesStatus)}>
              {(Object.keys(STATUS_LABEL) as SalesStatus[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="یادداشتِ پیگیری" hint="فقط ستاد می‌بیند — نتیجه‌ی تماس، قیمتِ پیشنهادی، قرارِ بعدی.">
            <textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </>
      ) : row.staff_note ? (
        <p className="ad-pre">{row.staff_note}</p>
      ) : null}
      <Note msg={err} />
    </Dialog>
  )
}
