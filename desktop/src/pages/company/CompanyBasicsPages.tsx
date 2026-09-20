import { useEffect, useMemo, useState } from 'react'
import {
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
import {
  ActionBar,
  CountBadge,
  FormField,
  FormGrid,
  FormStatus,
  ListToolbar,
  RowAction,
  SearchField,
} from '../../components/form/FormKit'
import { firstMissing } from '../../components/form/firstMissing'
import { EmptyState } from '../../components/EmptyState'
import { SearchSelect } from '../../components/SearchSelect'

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
    const missing = firstMissing([[name, 'cg-name', 'نامِ گروه را وارد کنید.']])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
      <form noValidate onSubmit={(e) => void submit(e)}>
        <SectionCard
          icon={Tags}
          title={editing ? `ویرایشِ گروه «${editing.name}»` : 'گروه تازه'}
          tip="نام الزامی است؛ کد اختیاری و فقط برای مرتب‌سازی و ارجاع است."
        >
          <FormGrid>
            <FormField id="cg-name" label="نام گروه" required>
              {(id) => (
                <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
              )}
            </FormField>
            <FormField label="کد" optional>
              {(id) => <input id={id} value={code} onChange={(e) => setCode(e.target.value)} maxLength={30} />}
            </FormField>
            <FormField label="توضیحات" optional>
              {(id) => <input id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}
            </FormField>
            <div className="ef-checks">
              <label className="ef-check-tip">
                <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                فعال — گروهِ غیرفعال در فرم‌ها پیشنهاد نمی‌شود
              </label>
            </div>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg} />}>
          {editing && (
            <button type="button" className="ef-btn-secondary" onClick={reset} disabled={busy}>
              <X size={15} /> انصراف
            </button>
          )}
          <button type="submit" className="btn-primary" disabled={busy}>
            {editing ? <Save size={16} /> : <Plus size={16} />} {editing ? 'ذخیرهٔ تغییرات' : 'افزودن گروه'}
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={Tags}
        title="گروه‌های موجود"
        badge={rows ? <CountBadge accent>{fa(rows.length)} گروه</CountBadge> : undefined}
        description="برای ویرایش روی هر ردیف کلیک کنید."
      >
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState icon={Tags} text="هنوز گروهی نساخته‌اید — اولین گروه را از فرمِ بالا اضافه کنید." />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
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
                      <span className={`status-badge ${r.is_active ? 'tone-success' : 'tone-muted'}`}>
                        {r.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td data-label="توضیحات">{r.notes || '—'}</td>
                    <td className="card-actions ef-col-min">
                      <div className="row-actions ef-row-actions">
                        <RowAction
                          icon={Trash2}
                          label="حذف"
                          danger
                          disabled={busy}
                          onClick={() => void remove(r)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
      </div>
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
    const missing = firstMissing([[name, 'geo-name', 'نامِ محل را وارد کنید.']])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
      <form noValidate onSubmit={(e) => void submit(e)}>
        <SectionCard
          icon={MapPin}
          title={editing ? `ویرایشِ «${editing.name}»` : 'محل تازه'}
          tip="«زیرمجموعه‌ی» خالی یعنی این محل ریشه است؛ طرف‌حساب به برگِ درخت وصل می‌شود."
        >
          <FormGrid>
            <FormField id="geo-name" label="نام" required>
              {(id) => (
                <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
              )}
            </FormField>
            <FormField label="سطح" required>
              {(id) => (
                <SearchSelect id={id} value={kind} onChange={(e) => setKind(e.target.value)}>
                  {GEO_ORDER.map((k) => (
                    <option key={k} value={k}>
                      {GEO_KIND_LABELS[k]}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField label="کد" optional>
              {(id) => <input id={id} value={code} onChange={(e) => setCode(e.target.value)} maxLength={30} />}
            </FormField>
            <FormField label="زیرمجموعه‌ی" optional>
              {(id) => (
                <SearchSelect id={id} value={parent} onChange={(e) => setParent(e.target.value)}>
                  <option value="">— ریشه —</option>
                  {parentOptions.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.path}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <div className="ef-checks">
              <label className="ef-check-tip">
                <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                فعال
              </label>
            </div>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg} />}>
          {editing && (
            <button type="button" className="ef-btn-secondary" onClick={reset} disabled={busy}>
              <X size={15} /> انصراف
            </button>
          )}
          <button type="submit" className="btn-primary" disabled={busy}>
            {editing ? <Save size={16} /> : <Plus size={16} />} {editing ? 'ذخیرهٔ تغییرات' : 'افزودن محل'}
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={MapPin}
        title="محل‌های ثبت‌شده"
        badge={rows ? <CountBadge accent>{fa(rows.length)} محل</CountBadge> : undefined}
        description="مرتب بر اساسِ مسیرِ درخت؛ برای ویرایش روی هر ردیف کلیک کنید."
      >
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={MapPin}
            text="هنوز محلی ثبت نشده — از ریشه شروع کنید: مثلاً «ایران» به‌عنوانِ کشور، بعد استان‌ها زیرِ آن."
          />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th>مسیر</th>
                  <th>سطح</th>
                  <th>کد</th>
                  <th>طرف‌حساب</th>
                  <th>وضعیت</th>
                  <th className="ef-col-min">عملیات</th>
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
                      <span className={`status-badge ${r.is_active ? 'tone-success' : 'tone-muted'}`}>
                        {r.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td className="card-actions ef-col-min">
                      <div className="row-actions ef-row-actions">
                        <RowAction
                          icon={Trash2}
                          label="حذف"
                          danger
                          disabled={busy}
                          onClick={() => void remove(r)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
      </div>
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
    const missing = firstMissing([
      [contactId, 'rp-contact', 'طرف حساب را انتخاب کنید.'],
      [name, 'rp-name', 'نامِ فرد را وارد کنید.'],
    ])
    if (missing) {
      setMsg({ text: missing, kind: 'err' })
      return
    }
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
      <div className="ef-form">
      <form noValidate onSubmit={(e) => void submit(e)}>
        <SectionCard
          icon={Contact2}
          title={editing ? `ویرایشِ «${editing.name}»` : 'فردِ تازه'}
          tip="«نفرِ اصلی» در هر طرف‌حساب یکی است؛ با علامت‌زدنِ فردِ تازه، قبلی خودکار از این حالت درمی‌آید."
        >
          <FormGrid>
            <FormField id="rp-contact" label="طرف حساب" required>
              {(id) => (
                <SearchSelect id={id} value={contactId} onChange={(e) => setContactId(e.target.value)}>
                  <option value="">— انتخاب کنید —</option>
                  {contacts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </SearchSelect>
              )}
            </FormField>
            <FormField id="rp-name" label="نام" required>
              {(id) => (
                <input id={id} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
              )}
            </FormField>
            <FormField label="سمت" optional>
              {(id) => (
                <input
                  id={id}
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="مدیر خرید"
                  maxLength={120}
                />
              )}
            </FormField>
            <FormField label="تلفن" optional>
              {(id) => (
                <input id={id} value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={30} dir="ltr" />
              )}
            </FormField>
            <FormField label="ایمیل" optional>
              {(id) => (
                <input id={id} value={email} onChange={(e) => setEmail(e.target.value)} maxLength={150} dir="ltr" />
              )}
            </FormField>
            <div className="ef-checks">
              <label className="ef-check-tip">
                <input type="checkbox" checked={primary} onChange={(e) => setPrimary(e.target.checked)} />
                نفرِ اصلیِ تماس
              </label>
            </div>
          </FormGrid>
        </SectionCard>
        <ActionBar status={<FormStatus msg={msg} />}>
          {editing && (
            <button type="button" className="ef-btn-secondary" onClick={reset} disabled={busy}>
              <X size={15} /> انصراف
            </button>
          )}
          <button type="submit" className="btn-primary" disabled={busy}>
            {editing ? <Save size={16} /> : <Plus size={16} />} {editing ? 'ذخیرهٔ تغییرات' : 'افزودن فرد'}
          </button>
        </ActionBar>
      </form>

      <SectionCard
        icon={Contact2}
        title="فهرستِ افراد"
        badge={rows ? <CountBadge accent>{fa(shown.length)} نفر</CountBadge> : undefined}
        description="برای ویرایش روی هر ردیف کلیک کنید."
      >
        <ListToolbar>
          <SearchField
            value={filter}
            onChange={setFilter}
            placeholder="جست‌وجو در نام، سمت، تلفن…"
            label="جست‌وجوی افراد"
          />
        </ListToolbar>
        {rows == null ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : shown.length === 0 ? (
          <EmptyState
            icon={Contact2}
            text={filter ? 'چیزی با این عبارت پیدا نشد.' : 'هنوز فردی ثبت نشده — از فرمِ بالا اولین فرد را اضافه کنید.'}
          />
        ) : (
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th>نام</th>
                  <th>طرف حساب</th>
                  <th>سمت</th>
                  <th>تلفن</th>
                  <th>ایمیل</th>
                  <th className="ef-col-min">عملیات</th>
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
                    <td className="card-actions ef-col-min">
                      <div className="row-actions ef-row-actions">
                        <RowAction
                          icon={Trash2}
                          label="حذف"
                          danger
                          disabled={busy}
                          onClick={() => void remove(r)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
      </div>
    </div>
  )
}
