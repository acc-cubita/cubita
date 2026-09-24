/**
 * مجوزهای «کوبیتا سازمانی» — صدور، صدورِ آفلاین، تمدید، انتقال و ابطال.
 *
 * دو چیز را صفحه صریح می‌گوید چون بی‌آن اشتباه برداشت می‌شوند:
 * - **کدِ فعال‌سازی فقط یک‌بار دیده می‌شود** (در دیتابیس فقط هشش هست). گم شد → کدِ تازه.
 * - **ابطال سرورِ آفلاینِ مشتری را خاموش نمی‌کند.** توکنی که آنجا نشسته خودکفاست و تا
 *   انقضا کار می‌کند؛ ابطال فقط جلوی صدورِ تازه را می‌گیرد.
 */
import { useMemo, useState } from 'react'
import { ClipboardCopy, KeyRound, Plus, RefreshCw, Search } from 'lucide-react'

import {
  createLicense,
  fetchLicense,
  fetchLicenses,
  issueLicenseOffline,
  regenerateLicenseCode,
  revokeLicense,
  transferLicense,
  updateLicense,
  type EnterpriseLicense,
  type EnterpriseLicenseDetail,
  type EnterpriseLicenseEvent,
  type StaffMe,
} from '../api'
import { textMatches } from '../lib/faText'
import { formatJalali } from '../lib/jalali'
import {
  AsyncBlock,
  Card,
  Chip,
  Dialog,
  Field,
  FieldGrid,
  Note,
  PageHeader,
  Stat,
  TableScroll,
  faInt,
  useAsync,
} from '../ui/kit'

type Msg = { kind: 'ok' | 'bad'; text: string } | null

function can(me: StaffMe, action: string): boolean {
  //: همان معناشناسیِ `staff_roles.has_permission`. گاردِ واقعی سرور است.
  for (const key of ['licenses', '*']) {
    const actions = me.permissions[key]
    if (actions && (actions.includes(action) || actions.includes('*'))) return true
  }
  return false
}

const DAY = 86_400_000

function isExpired(l: EnterpriseLicense): boolean {
  return !!l.expires_at && Date.parse(l.expires_at) + l.grace_days * DAY < Date.now()
}

function statusChip(l: EnterpriseLicense) {
  if (l.status === 'revoked') return <Chip text="باطل" tone="bad" />
  if (isExpired(l)) return <Chip text="منقضی" tone="bad" />
  if (l.bound) return <Chip text="فعال روی دستگاه" tone="ok" />
  return <Chip text="منتظرِ فعال‌سازی" tone="warn" />
}

const EVENT_LABEL: Record<EnterpriseLicenseEvent['kind'], string> = {
  create: 'صدور',
  update: 'ویرایش',
  activate: 'فعال‌سازیِ آنلاین',
  issue: 'صدورِ آفلاین',
  refuse: 'ردِ فعال‌سازی',
  transfer: 'آزادسازی برای دستگاهِ تازه',
  revoke: 'ابطال',
  code: 'کدِ تازه',
}

const REFUSE_REASON: Record<string, string> = {
  other_machine: 'رایانه‌ی دیگر',
  revoked: 'مجوزِ باطل',
  expired: 'مجوزِ منقضی',
}

async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // کلیپ‌بورد در دسترس نبود؛ متن در کادر هست و دستی هم کپی می‌شود.
  }
}

function SecretBox({ label, value, hint }: { label: string; value: string; hint: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="ad-secret">
      <Field label={label} hint={hint}>
        <textarea dir="ltr" readOnly rows={value.length > 60 ? 5 : 1} value={value} className="ad-mono" />
      </Field>
      <button
        type="button"
        className="ad-btn"
        onClick={() => void copy(value).then(() => setCopied(true))}
      >
        <ClipboardCopy size={15} /> {copied ? 'کپی شد' : 'کپی'}
      </button>
    </div>
  )
}

function CreateDialog({
  token,
  onClose,
  onCreated,
  onUnauthorized,
}: {
  token: string
  onClose: () => void
  onCreated: (code: string, lic: EnterpriseLicense) => void
  onUnauthorized: (e: unknown) => void
}) {
  const [org, setOrg] = useState('')
  const [contact, setContact] = useState('')
  const [seats, setSeats] = useState('5')
  const [days, setDays] = useState('365')
  const [perpetual, setPerpetual] = useState(false)
  const [moadian, setMoadian] = useState(true)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const out = await createLicense(token, {
        org_name: org.trim(),
        contact: contact.trim() || null,
        seats: seats ? Number(seats) : null,
        days: perpetual ? null : Number(days),
        feat: moadian ? ['moadian'] : [],
        note: note.trim() || null,
      })
      onCreated(out.activation_code, out.license)
    } catch (e) {
      onUnauthorized(e)
      setError(e instanceof Error ? e.message : 'مجوز ساخته نشد')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      title="مجوزِ تازه"
      onClose={onClose}
      footer={
        <button type="button" className="ad-btn primary" onClick={submit} disabled={busy || org.trim().length < 2}>
          {busy ? 'در حال ساخت…' : 'ساختِ مجوز'}
        </button>
      }
    >
      <FieldGrid>
        <Field label="نامِ سازمان">
          <input value={org} onChange={(e) => setOrg(e.target.value)} autoFocus />
        </Field>
        <Field label="تماسِ خریدار" hint="تلفن یا ایمیل — برای پشتیبانی.">
          <input value={contact} onChange={(e) => setContact(e.target.value)} />
        </Field>
        <Field label="تعدادِ کاربر" hint="خالی = بی‌سقف.">
          <input type="number" min={1} value={seats} onChange={(e) => setSeats(e.target.value)} />
        </Field>
        <Field label="مدت (روز)" hint="از امروز. پس از انقضا ۱۴ روز مهلت دارد.">
          <input type="number" min={1} value={days} disabled={perpetual} onChange={(e) => setDays(e.target.value)} />
        </Field>
      </FieldGrid>
      <label className="ad-check">
        <input type="checkbox" checked={perpetual} onChange={(e) => setPerpetual(e.target.checked)} />
        دائمی (بدونِ انقضا)
      </label>
      <label className="ad-check">
        <input type="checkbox" checked={moadian} onChange={(e) => setMoadian(e.target.checked)} />
        شاملِ سامانه‌ی مؤدیان
      </label>
      <Field label="یادداشت">
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {error ? <p className="ad-note tone-bad">{error}</p> : null}
    </Dialog>
  )
}

function DetailDialog({
  token,
  me,
  id,
  onClose,
  onChanged,
  onUnauthorized,
}: {
  token: string
  me: StaffMe
  id: string
  onClose: () => void
  onChanged: () => void
  onUnauthorized: (e: unknown) => void
}) {
  const detail = useAsync(() => fetchLicense(token, id), [token, id])
  const [request, setRequest] = useState('')
  const [issued, setIssued] = useState<string | null>(null)
  const [newCode, setNewCode] = useState<string | null>(null)
  const [extend, setExtend] = useState('365')
  const [seats, setSeats] = useState('')
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)

  async function run(action: () => Promise<unknown>, ok: string) {
    setBusy(true)
    setMsg(null)
    try {
      await action()
      setMsg({ kind: 'ok', text: ok })
      detail.reload()
      onChanged()
    } catch (e) {
      onUnauthorized(e)
      setMsg({ kind: 'bad', text: e instanceof Error ? e.message : 'انجام نشد' })
    } finally {
      setBusy(false)
    }
  }

  const l: EnterpriseLicenseDetail | null = detail.data
  const active = l?.status === 'active'

  return (
    <Dialog title={l ? l.org_name : 'مجوز'} onClose={onClose}>
      <AsyncBlock loading={detail.loading} error={detail.error} empty={false} emptyText="">
        {l ? (
          <>
            <dl className="ad-facts">
              <dt>شناسه</dt>
              <dd dir="ltr" className="ad-mono">{l.lic_id}</dd>
              <dt>وضعیت</dt>
              <dd>{statusChip(l)}</dd>
              <dt>کاربران</dt>
              <dd>{l.seats != null ? faInt(l.seats) : 'بی‌سقف'}</dd>
              <dt>انقضا</dt>
              <dd>{l.expires_at ? formatJalali(l.expires_at) : 'دائمی'}</dd>
              <dt>مؤدیان</dt>
              <dd>{l.feat == null || l.feat.includes('moadian') ? 'دارد' : 'ندارد'}</dd>
              <dt>کدِ فعال‌سازی</dt>
              <dd dir="ltr" className="ad-mono">…{l.code_hint}</dd>
              {l.contact ? (
                <>
                  <dt>تماس</dt>
                  <dd>{l.contact}</dd>
                </>
              ) : null}
            </dl>

            <Note msg={msg} />
            {newCode ? (
              <SecretBox label="کدِ فعال‌سازیِ تازه" value={newCode} hint="فقط همین یک‌بار نمایش داده می‌شود؛ کدِ قبلی باطل شد." />
            ) : null}

            {active && can(me, 'issue') ? (
              <section className="ad-subsection">
                <h4>صدورِ آفلاین</h4>
                <p className="ad-muted">
                  برای سروری که اینترنت ندارد: «کدِ درخواست» را از مشتری بگیرید و این‌جا بچسبانید.
                </p>
                <Field label="کدِ درخواست (CUBREQ1)">
                  <textarea dir="ltr" rows={3} className="ad-mono" value={request} onChange={(e) => setRequest(e.target.value)} />
                </Field>
                <button
                  type="button"
                  className="ad-btn primary"
                  disabled={busy || request.trim().length < 10}
                  onClick={() =>
                    void run(async () => {
                      setIssued((await issueLicenseOffline(token, id, request.trim())).token)
                    }, 'مجوز صادر شد؛ کد را برای مشتری بفرستید.')
                  }
                >
                  صدورِ مجوز
                </button>
                {issued ? <SecretBox label="کدِ مجوز (CUB1)" value={issued} hint="مشتری این را در «مجوز نرم‌افزار» می‌چسباند." /> : null}
              </section>
            ) : null}

            {active && can(me, 'edit') ? (
              <section className="ad-subsection">
                <h4>تمدید و سقف</h4>
                <p className="ad-muted">روی سرورِ مشتری با فعال‌سازیِ دوباره یا صدورِ آفلاینِ تازه اثر می‌کند.</p>
                <div className="ad-inline-form">
                  <Field label="تمدید (روز)">
                    <input type="number" min={1} value={extend} onChange={(e) => setExtend(e.target.value)} />
                  </Field>
                  <button
                    type="button"
                    className="ad-btn"
                    disabled={busy || !Number(extend)}
                    onClick={() => void run(() => updateLicense(token, id, { extend_days: Number(extend) }), 'تمدید شد.')}
                  >
                    تمدید
                  </button>
                  <Field label="تعدادِ کاربر">
                    <input type="number" min={1} value={seats} onChange={(e) => setSeats(e.target.value)} />
                  </Field>
                  <button
                    type="button"
                    className="ad-btn"
                    disabled={busy || !Number(seats)}
                    onClick={() => void run(() => updateLicense(token, id, { seats: Number(seats) }), 'سقفِ کاربران عوض شد.')}
                  >
                    ثبتِ سقف
                  </button>
                </div>
              </section>
            ) : null}

            <div className="ad-dialog-actions">
              {active && l.bound && can(me, 'transfer') ? (
                <button
                  type="button"
                  className="ad-btn"
                  disabled={busy}
                  onClick={() => {
                    if (!window.confirm('مجوز از دستگاهِ فعلی آزاد شود تا روی سرورِ تازه فعال شود؟ سرورِ قبلی تا انقضا کار می‌کند.')) return
                    void run(() => transferLicense(token, id), 'آزاد شد؛ مشتری روی سرورِ تازه فعال کند.')
                  }}
                >
                  انتقال به سرورِ تازه
                </button>
              ) : null}
              {active && can(me, 'edit') ? (
                <button
                  type="button"
                  className="ad-btn"
                  disabled={busy}
                  onClick={() => {
                    if (!window.confirm('کدِ فعال‌سازیِ تازه ساخته شود؟ کدِ قبلی دیگر کار نمی‌کند.')) return
                    void run(async () => {
                      setNewCode((await regenerateLicenseCode(token, id)).activation_code)
                    }, 'کدِ تازه ساخته شد.')
                  }}
                >
                  کدِ فعال‌سازیِ تازه
                </button>
              ) : null}
              {active && can(me, 'revoke') ? (
                <button
                  type="button"
                  className="ad-btn danger"
                  disabled={busy}
                  onClick={() => {
                    if (!window.confirm('مجوز باطل شود؟ صدورِ تازه بسته می‌شود؛ سرورِ آفلاینِ مشتری تا انقضا کار می‌کند.')) return
                    void run(() => revokeLicense(token, id), 'مجوز باطل شد.')
                  }}
                >
                  ابطال
                </button>
              ) : null}
            </div>

            <section className="ad-subsection">
              <h4>تاریخچه</h4>
              {l.events.length === 0 ? (
                <p className="ad-muted">رویدادی ثبت نشده است.</p>
              ) : (
                <ul className="ad-timeline">
                  {l.events.map((e, i) => (
                    <li key={i} className={e.kind === 'refuse' ? 'tone-bad' : undefined}>
                      <strong>{EVENT_LABEL[e.kind] ?? e.kind}</strong>
                      {e.kind === 'refuse' && typeof e.detail?.reason === 'string'
                        ? ` — ${REFUSE_REASON[e.detail.reason] ?? e.detail.reason}`
                        : ''}
                      <span className="ad-muted">
                        {' '}
                        · {formatJalali(e.created_at)} · {e.actor === 'online' ? 'خودِ مشتری' : e.actor}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        ) : null}
      </AsyncBlock>
    </Dialog>
  )
}

export default function LicensesPage({
  token,
  me,
  onUnauthorized,
}: {
  token: string
  me: StaffMe
  onUnauthorized: (e: unknown) => void
}) {
  const list = useAsync(() => fetchLicenses(token), [token])
  const [q, setQ] = useState('')
  const [creating, setCreating] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const [created, setCreated] = useState<{ code: string; org: string } | null>(null)

  const rows = list.data ?? []
  const shown = useMemo(
    () => rows.filter((r) => textMatches(`${r.org_name} ${r.lic_id} ${r.contact ?? ''} ${r.code_hint}`, q)),
    [rows, q],
  )
  const soon = rows.filter(
    (r) => r.status === 'active' && r.expires_at && !isExpired(r) && Date.parse(r.expires_at) - Date.now() < 30 * DAY,
  ).length

  return (
    <>
      <PageHeader
        icon={KeyRound}
        title="مجوزهای سازمانی"
        description="مجوزهای «کوبیتا سازمانی»: صدور، فعال‌سازیِ آفلاین، تمدید، انتقال و ابطال."
        actions={
          <>
            {can(me, 'create') ? (
              <button type="button" className="ad-btn primary" onClick={() => setCreating(true)}>
                <Plus size={15} /> مجوزِ تازه
              </button>
            ) : null}
            <button type="button" className="ad-btn" onClick={() => list.reload()}>
              <RefreshCw size={15} /> تازه‌سازی
            </button>
          </>
        }
      />

      <section className="ad-stats">
        <Stat label="کلِ مجوزها" value={faInt(rows.length)} />
        <Stat label="فعال روی دستگاه" value={faInt(rows.filter((r) => r.status === 'active' && r.bound).length)} tone="ok" />
        <Stat
          label="منتظرِ فعال‌سازی"
          value={faInt(rows.filter((r) => r.status === 'active' && !r.bound && !isExpired(r)).length)}
        />
        <Stat label="انقضا تا ۳۰ روز" value={faInt(soon)} tone={soon > 0 ? 'warn' : 'ok'} />
      </section>

      {created ? (
        <Card description="این کد فقط همین یک‌بار نمایش داده می‌شود. آن را برای خریدار بفرستید؛ روی سرورش در «مجوز نرم‌افزار» ← «فعال‌سازیِ آنلاین» وارد می‌کند.">
          <SecretBox label={`کدِ فعال‌سازیِ «${created.org}»`} value={created.code} hint="اگر گم شد، از جزئیاتِ مجوز «کدِ تازه» بسازید." />
          <button type="button" className="ad-btn" onClick={() => setCreated(null)}>
            بستن
          </button>
        </Card>
      ) : null}

      <Card description="ابطال فقط صدورِ تازه را می‌بندد؛ سرورِ آفلاینِ مشتری تا تاریخِ انقضای مجوزش کار می‌کند.">
        <div className="ad-toolbar">
          <div className="ad-search">
            <Search size={15} />
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="سازمان، شناسه یا تماس"
              aria-label="جست‌وجو"
            />
          </div>
          <span className="ad-count">{faInt(shown.length)} مجوز</span>
        </div>

        <AsyncBlock loading={list.loading} error={list.error} empty={shown.length === 0} emptyText="مجوزی نیست. با «مجوزِ تازه» اولین را بسازید.">
          <TableScroll>
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>سازمان</th>
                  <th>شناسه</th>
                  <th>کاربران</th>
                  <th>انقضا</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.id}>
                    <td className="card-title" data-label="سازمان">
                      {r.org_name}
                    </td>
                    <td data-label="شناسه" dir="ltr" className="ad-mono">
                      {r.lic_id}
                    </td>
                    <td className="num" data-label="کاربران">
                      {r.seats != null ? faInt(r.seats) : 'بی‌سقف'}
                    </td>
                    <td data-label="انقضا">{r.expires_at ? formatJalali(r.expires_at) : 'دائمی'}</td>
                    <td data-label="وضعیت">{statusChip(r)}</td>
                    <td className="card-actions">
                      <button type="button" className="ad-btn small" onClick={() => setOpenId(r.id)}>
                        جزئیات
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </AsyncBlock>
      </Card>

      {creating ? (
        <CreateDialog
          token={token}
          onClose={() => setCreating(false)}
          onUnauthorized={onUnauthorized}
          onCreated={(code, lic) => {
            setCreating(false)
            setCreated({ code, org: lic.org_name })
            list.reload()
          }}
        />
      ) : null}
      {openId ? (
        <DetailDialog
          token={token}
          me={me}
          id={openId}
          onClose={() => setOpenId(null)}
          onChanged={() => list.reload()}
          onUnauthorized={onUnauthorized}
        />
      ) : null}
    </>
  )
}
