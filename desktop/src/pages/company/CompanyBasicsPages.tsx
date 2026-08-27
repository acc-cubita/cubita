import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Contact2,
  MapPin,
  Plus,
  Save,
  Star,
  Tags,
  Trash2,
  X,
} from 'lucide-react'
import {
  GEO_KIND_LABELS,
  createContactGroup,
  createGeoLocation,
  createRelatedPerson,
  deleteContactGroup,
  deleteGeoLocation,
  deleteRelatedPerson,
  fetchContactGroups,
  fetchContacts,
  fetchGeoLocations,
  fetchRelatedPersons,
  updateContactGroup,
  updateGeoLocation,
  updateRelatedPerson,
  type ContactGroupRecord,
  type ContactRecord,
  type GeoLocationRecord,
  type RelatedPersonRecord,
} from '../../api'
import { PageHeader } from '../../components/PageHeader'
import { SectionCard } from '../../components/SectionCard'
import { EmptyState } from '../../components/EmptyState'

/**
 * داده‌های پایه‌ی «شرکت»: گروهِ طرف‌حساب، محلِ جغرافیایی، فردِ مرتبط.
 *
 * هر سه یک الگو دارند — فرمِ کوچکِ بالا برای ساختن/ویرایش، فهرستِ زیرش — پس در یک
 * فایل کنارِ هم نشسته‌اند تا الگو یک‌جا دیده شود و سه‌بار بازنویسی نشود.
 *
 * حذف عمداً سخت‌گیر است: سرور ردیفِ در حالِ استفاده را با ۴۰۹ رد می‌کند و همان پیام
 * این‌جا نشان داده می‌شود. راهِ درست «غیرفعال‌کردن» است — دسته‌بندیِ صدها طرف‌حساب
 * نباید با یک کلیک بی‌صدا پاک شود.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

type Msg = { text: string; kind: 'ok' | 'err' } | null

function Note({ msg }: { msg: Msg }) {
  if (!msg) return null
  return (
    <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
      {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <div>{msg.text}</div>
    </div>
  )
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'خطای ناشناخته'
}

// ── گروهِ طرف‌حساب ────────────────────────────────────────────────────────────

export function ContactGroupPage({ token }: { token: string }) {
  const [rows, setRows] = useState<ContactGroupRecord[] | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<ContactGroupRecord | null>(null)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [notes, setNotes] = useState('')
  const [active, setActive] = useState(true)

  async function refresh() {
    try {
      setRows(await fetchContactGroups(token))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function reset() {
    setEditing(null)
    setName('')
    setCode('')
    setNotes('')
    setActive(true)
  }

  function startEdit(row: ContactGroupRecord) {
    setEditing(row)
    setName(row.name)
    setCode(row.code)
    setNotes(row.notes)
    setActive(row.is_active)
    setMsg(null)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    setMsg(null)
    try {
      const payload = { name: name.trim(), code: code.trim(), notes, is_active: active }
      if (editing) await updateContactGroup(token, editing.id, payload)
      else await createContactGroup(token, payload)
      setMsg({ text: editing ? 'گروه به‌روزرسانی شد.' : `گروه «${name.trim()}» ساخته شد.`, kind: 'ok' })
      reset()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(row: ContactGroupRecord) {
    if (!window.confirm(`گروه «${row.name}» حذف شود؟`)) return
    setBusy(true)
    setMsg(null)
    try {
      await deleteContactGroup(token, row.id)
      setMsg({ text: 'گروه حذف شد.', kind: 'ok' })
      if (editing?.id === row.id) reset()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={Tags}
        title="گروه جدید"
        description="طرف‌حساب‌ها را دسته کنید (عمده‌فروش، خرده‌فروش، همکار…) تا گزارش‌های فروش و مطالبات به تفکیکِ گروه معنا پیدا کنند."
      />
      <Note msg={msg} />

      <SectionCard
        icon={Tags}
        title={editing ? `ویرایشِ گروه «${editing.name}»` : 'گروه تازه'}
        description="نام الزامی است؛ کد اختیاری و فقط برای مرتب‌سازی و ارجاع است."
        actions={
          editing ? (
            <button type="button" onClick={reset} disabled={busy}>
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        <form onSubmit={(e) => void submit(e)} className="cmp-form">
          <label>
            <span>نام گروه</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          </label>
          <label>
            <span>کد</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={30} />
          </label>
          <label className="cmp-form-wide">
            <span>توضیحات</span>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <label className="cmp-check">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            <span>فعال — گروهِ غیرفعال در فرم‌ها پیشنهاد نمی‌شود</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
              {editing ? <Save size={13} /> : <Plus size={13} />} {editing ? 'ذخیره' : 'افزودن گروه'}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard icon={Tags} title="گروه‌های موجود" description="برای ویرایش روی هر ردیف کلیک کنید.">
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Tags} text="هنوز گروهی نساخته‌اید — اولین گروه را از فرمِ بالا اضافه کنید." />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>کد</th>
                  <th>نام</th>
                  <th>طرف‌حساب</th>
                  <th>وضعیت</th>
                  <th>توضیحات</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => startEdit(r)} className="row-clickable">
                    <td data-label="کد">{r.code || '—'}</td>
                    <td className="card-title" data-label="نام">{r.name}</td>
                    <td data-label="طرف‌حساب">{fa(r.contact_count)}</td>
                    <td data-label="وضعیت">
                      <span className={`badge ${r.is_active ? 'success' : ''}`}>
                        {r.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td data-label="توضیحات">{r.notes || '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="icon-btn-danger"
                        disabled={busy}
                        onClick={(e) => {
                          e.stopPropagation()
                          void remove(r)
                        }}
                      >
                        <Trash2 size={13} /> حذف
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── محلِ جغرافیایی ───────────────────────────────────────────────────────────

const GEO_ORDER = ['country', 'province', 'city', 'district']

export function GeoLocationsPage({ token }: { token: string }) {
  const [rows, setRows] = useState<GeoLocationRecord[] | null>(null)
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<GeoLocationRecord | null>(null)
  const [name, setName] = useState('')
  const [kind, setKind] = useState('city')
  const [code, setCode] = useState('')
  const [parent, setParent] = useState('')
  const [active, setActive] = useState(true)

  async function refresh() {
    try {
      setRows(await fetchGeoLocations(token))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function reset() {
    setEditing(null)
    setName('')
    setKind('city')
    setCode('')
    setParent('')
    setActive(true)
  }

  function startEdit(row: GeoLocationRecord) {
    setEditing(row)
    setName(row.name)
    setKind(row.kind)
    setCode(row.code)
    setParent(row.parent_id ?? '')
    setActive(row.is_active)
    setMsg(null)
  }

  // والدِ ممکن: هر محلی جز خودش. حلقه را سرور هم رد می‌کند، ولی نشان‌دادنِ گزینه‌ای
  // که قطعاً رد می‌شود یعنی دعوت به خطا.
  const parentOptions = useMemo(
    () => (rows ?? []).filter((r) => r.id !== editing?.id),
    [rows, editing],
  )

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    setMsg(null)
    try {
      const payload = {
        name: name.trim(),
        kind,
        code: code.trim(),
        parent_id: parent || null,
        is_active: active,
      }
      if (editing) await updateGeoLocation(token, editing.id, payload)
      else await createGeoLocation(token, payload)
      setMsg({ text: editing ? 'محل به‌روزرسانی شد.' : `«${name.trim()}» اضافه شد.`, kind: 'ok' })
      reset()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(row: GeoLocationRecord) {
    if (!window.confirm(`«${row.path}» حذف شود؟`)) return
    setBusy(true)
    setMsg(null)
    try {
      await deleteGeoLocation(token, row.id)
      setMsg({ text: 'محل حذف شد.', kind: 'ok' })
      if (editing?.id === row.id) reset()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page panels">
      <PageHeader
        icon={MapPin}
        title="محل‌های جغرافیایی"
        description="درختِ کشور ← استان ← شهر ← منطقه. طرف‌حساب به برگِ این درخت وصل می‌شود تا گزارشِ منطقه‌ای بی‌ابهام باشد."
      />
      <Note msg={msg} />

      <SectionCard
        icon={MapPin}
        title={editing ? `ویرایشِ «${editing.name}»` : 'محل تازه'}
        description="«زیرمجموعه‌ی» خالی یعنی این محل ریشه است."
        actions={
          editing ? (
            <button type="button" onClick={reset} disabled={busy}>
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        <form onSubmit={(e) => void submit(e)} className="cmp-form">
          <label>
            <span>نام</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
          </label>
          <label>
            <span>سطح</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {GEO_ORDER.map((k) => (
                <option key={k} value={k}>
                  {GEO_KIND_LABELS[k]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>کد</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={30} />
          </label>
          <label className="cmp-form-wide">
            <span>زیرمجموعه‌ی</span>
            <select value={parent} onChange={(e) => setParent(e.target.value)}>
              <option value="">— ریشه —</option>
              {parentOptions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.path}
                </option>
              ))}
            </select>
          </label>
          <label className="cmp-check">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            <span>فعال</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
              {editing ? <Save size={13} /> : <Plus size={13} />} {editing ? 'ذخیره' : 'افزودن محل'}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard icon={MapPin} title="محل‌های ثبت‌شده" description="مرتب بر اساسِ مسیرِ درخت.">
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={MapPin}
            text="هنوز محلی ثبت نشده — از ریشه شروع کنید: مثلاً «ایران» به‌عنوانِ کشور، بعد استان‌ها زیرِ آن."
          />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>مسیر</th>
                  <th>سطح</th>
                  <th>کد</th>
                  <th>طرف‌حساب</th>
                  <th>وضعیت</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => startEdit(r)} className="row-clickable">
                    <td className="card-title" data-label="مسیر">{r.path}</td>
                    <td data-label="سطح">{GEO_KIND_LABELS[r.kind] ?? r.kind}</td>
                    <td data-label="کد">{r.code || '—'}</td>
                    <td data-label="طرف‌حساب">{fa(r.contact_count)}</td>
                    <td data-label="وضعیت">
                      <span className={`badge ${r.is_active ? 'success' : ''}`}>
                        {r.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="icon-btn-danger"
                        disabled={busy}
                        onClick={(e) => {
                          e.stopPropagation()
                          void remove(r)
                        }}
                      >
                        <Trash2 size={13} /> حذف
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

// ── افرادِ مرتبط ─────────────────────────────────────────────────────────────

export function RelatedPeoplePage({ token }: { token: string }) {
  const [rows, setRows] = useState<RelatedPersonRecord[] | null>(null)
  const [contacts, setContacts] = useState<ContactRecord[]>([])
  const [msg, setMsg] = useState<Msg>(null)
  const [busy, setBusy] = useState(false)
  const [filter, setFilter] = useState('')
  const [editing, setEditing] = useState<RelatedPersonRecord | null>(null)
  const [contactId, setContactId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [primary, setPrimary] = useState(false)

  async function refresh() {
    try {
      setRows(await fetchRelatedPersons(token))
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    }
  }

  useEffect(() => {
    void refresh()
    void fetchContacts(token)
      .then((c) => setContacts(c.filter((x) => x.is_active)))
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function reset() {
    setEditing(null)
    setName('')
    setRole('')
    setPhone('')
    setEmail('')
    setPrimary(false)
  }

  function startEdit(row: RelatedPersonRecord) {
    setEditing(row)
    setContactId(row.contact_id)
    setName(row.name)
    setRole(row.role)
    setPhone(row.phone)
    setEmail(row.email)
    setPrimary(row.is_primary)
    setMsg(null)
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!contactId || !name.trim()) return
    setBusy(true)
    setMsg(null)
    try {
      const payload = {
        contact_id: contactId,
        name: name.trim(),
        role: role.trim(),
        phone: phone.trim(),
        email: email.trim(),
        is_primary: primary,
      }
      if (editing) await updateRelatedPerson(token, editing.id, payload)
      else await createRelatedPerson(token, payload)
      setMsg({ text: editing ? 'به‌روزرسانی شد.' : `«${name.trim()}» اضافه شد.`, kind: 'ok' })
      reset()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function remove(row: RelatedPersonRecord) {
    if (!window.confirm(`«${row.name}» حذف شود؟`)) return
    setBusy(true)
    try {
      await deleteRelatedPerson(token, row.id)
      setMsg({ text: 'حذف شد.', kind: 'ok' })
      if (editing?.id === row.id) reset()
      await refresh()
    } catch (err) {
      setMsg({ text: errText(err), kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const shown = useMemo(() => {
    const q = filter.trim()
    if (!q) return rows ?? []
    return (rows ?? []).filter((r) =>
      [r.name, r.role, r.phone, r.contact_name].some((v) => v.includes(q)),
    )
  }, [rows, filter])

  return (
    <div className="page panels">
      <PageHeader
        icon={Contact2}
        title="افراد مرتبط"
        description="آدم‌های واقعیِ پشتِ هر طرف‌حساب — مدیر خرید، حسابدار، راننده. شماره‌شان به‌جای فیلدِ توضیحات، جای خودش می‌نشیند و جست‌وجوپذیر است."
      />
      <Note msg={msg} />

      <SectionCard
        icon={Contact2}
        title={editing ? `ویرایشِ «${editing.name}»` : 'فردِ تازه'}
        description="«نفرِ اصلی» در هر طرف‌حساب یکی است؛ با علامت‌زدنِ فردِ تازه، قبلی خودکار از این حالت درمی‌آید."
        actions={
          editing ? (
            <button type="button" onClick={reset} disabled={busy}>
              <X size={13} /> انصراف
            </button>
          ) : undefined
        }
      >
        <form onSubmit={(e) => void submit(e)} className="cmp-form">
          <label className="cmp-form-wide">
            <span>طرف حساب</span>
            <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
              <option value="">— انتخاب کنید —</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>نام</span>
            <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
          </label>
          <label>
            <span>سمت</span>
            <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="مدیر خرید" maxLength={120} />
          </label>
          <label>
            <span>تلفن</span>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={30} />
          </label>
          <label>
            <span>ایمیل</span>
            <input value={email} onChange={(e) => setEmail(e.target.value)} maxLength={150} />
          </label>
          <label className="cmp-check">
            <input type="checkbox" checked={primary} onChange={(e) => setPrimary(e.target.checked)} />
            <span>نفرِ اصلیِ تماس</span>
          </label>
          <div className="invoice-form-footer">
            <button type="submit" className="btn-primary" disabled={busy || !contactId || !name.trim()}>
              {editing ? <Save size={13} /> : <Plus size={13} />} {editing ? 'ذخیره' : 'افزودن'}
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard
        icon={Contact2}
        title="فهرستِ افراد"
        actions={
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="جست‌وجو در نام، سمت، تلفن…"
          />
        }
      >
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : shown.length === 0 ? (
          <EmptyState
            icon={Contact2}
            text={filter ? 'چیزی با این عبارت پیدا نشد.' : 'هنوز فردی ثبت نشده — از فرمِ بالا اولین فرد را اضافه کنید.'}
          />
        ) : (
          <div className="table-scroll">
            <table className="cards-on-mobile">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>طرف حساب</th>
                  <th>سمت</th>
                  <th>تلفن</th>
                  <th>ایمیل</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.id} onClick={() => startEdit(r)} className="row-clickable">
                    <td className="card-title" data-label="نام">
                      {r.is_primary && <Star size={12} className="cmp-star" />} {r.name}
                    </td>
                    <td data-label="طرف حساب">{r.contact_name}</td>
                    <td data-label="سمت">{r.role || '—'}</td>
                    <td data-label="تلفن">{r.phone || '—'}</td>
                    <td data-label="ایمیل">{r.email || '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="icon-btn-danger"
                        disabled={busy}
                        onClick={(e) => {
                          e.stopPropagation()
                          void remove(r)
                        }}
                      >
                        <Trash2 size={13} /> حذف
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
