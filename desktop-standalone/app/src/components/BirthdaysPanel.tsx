import { useEffect, useState } from 'react'
import { Cake, Save, Gift, CalendarHeart } from 'lucide-react'
import {
  addLoyaltyTxn,
  fetchBirthdays,
  fetchLoyaltySettings,
  setLoyaltySettings,
  updateContact,
  type BirthdayRow,
  type ContactRecord,
  type LoyaltySettings,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { JalaliDatePicker } from './JalaliDatePicker'
import { formatJalali, todayIso } from '../lib/jalali'

const fa = (n: number | string) => Math.round(Number(n)).toLocaleString('fa-IR')

function contactToIn(c: ContactRecord, birthday: string | null) {
  return {
    name: c.name,
    type: c.type,
    phone: c.phone,
    email: c.email,
    address: c.address,
    tax_id: c.tax_id,
    birthday,
    credit_limit: Number(c.credit_limit) || 0,
    default_price_list_id: c.default_price_list_id,
    entity_type: c.entity_type,
    national_id: c.national_id,
    economic_code: c.economic_code,
    postal_code: c.postal_code,
  }
}

export function BirthdaysPanel({
  token,
  contacts,
  onChanged,
}: {
  token: string
  contacts: ContactRecord[]
  onChanged: () => void
}) {
  const [settings, setSettings] = useState<LoyaltySettings | null>(null)
  const [rows, setRows] = useState<BirthdayRow[]>([])
  const [days, setDays] = useState(30)
  const [contactId, setContactId] = useState('')
  const [bday, setBday] = useState(todayIso())
  const [msg, setMsg] = useState<string | null>(null)
  const [gift, setGift] = useState('')

  async function refresh(d = days) {
    const [s, r] = await Promise.all([fetchLoyaltySettings(token), fetchBirthdays(token, d)])
    setSettings(s)
    setGift(Number(s.birthday_gift_points) ? String(s.birthday_gift_points) : '')
    setRows(r)
  }
  useEffect(() => {
    void refresh()
  }, [])

  async function saveBirthday(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!contactId) {
      setMsg('یک مشتری انتخاب کنید.')
      return
    }
    const c = contacts.find((x) => x.id === contactId)
    if (!c) return
    try {
      await updateContact(token, contactId, contactToIn(c, bday))
      setMsg('تاریخِ تولد ثبت شد.')
      setContactId('')
      onChanged()
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function saveGift() {
    if (!settings) return
    const points = Number(gift) || 0
    const next = { ...settings, birthday_gift_points: points }
    setSettings(next)
    await setLoyaltySettings(token, {
      is_enabled: next.is_enabled,
      amount_per_point: Number(next.amount_per_point) || 0,
      tier_basis: next.tier_basis,
      tier_discount_auto: next.tier_discount_auto,
      birthday_gift_points: points,
    })
  }

  async function giveGift(contact_id: string) {
    const points = Number(settings?.birthday_gift_points) || 0
    if (points <= 0) return
    await addLoyaltyTxn(token, { contact_id, points, reason: 'هدیه‌ی تولد', txn_date: todayIso() })
    onChanged()
  }

  const giftPoints = Number(settings?.birthday_gift_points) || 0
  const withBirthday = contacts.filter((c) => c.birthday).length

  return (
    <>
      <SectionCard icon={Gift} title="هدیه‌ی تولد" description="امتیازی که با یک کلیک به مشتری در روزِ تولدش می‌دهید.">
        <div className="benefit-toolbar">
          <label>
            امتیازِ هدیه‌ی تولد
            <NumberInput value={gift} onChange={setGift} placeholder="مثلاً ۵۰" style={{ width: 140 }} />
          </label>
          <button type="button" className="btn-primary" onClick={() => void saveGift()}><Save size={13} /> ذخیره</button>
          <span className="hint">{giftPoints > 0 ? `فعال: ${fa(giftPoints)} امتیاز` : 'غیرفعال'}</span>
        </div>
      </SectionCard>

      <div className="workspace-split">
        <SectionCard icon={Cake} title="ثبتِ تاریخِ تولد" description={`${fa(withBirthday)} مشتری تاریخِ تولد دارند.`}>
          <form className="invoice-form form-full" onSubmit={saveBirthday}>
            <label>
              مشتری
              <select value={contactId} onChange={(e) => setContactId(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}{c.birthday ? ' ✓' : ''}</option>
                ))}
              </select>
            </label>
            <label>
              تاریخِ تولد
              <JalaliDatePicker value={bday} onChange={setBday} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> ثبتِ تولد</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        </SectionCard>

        <SectionCard
          icon={CalendarHeart}
          title="تولدهای پیشِ‌رو"
          description={`${fa(rows.length)} مشتری تا ${fa(days)} روزِ آینده`}
          actions={
            <select value={days} onChange={(e) => { const d = Number(e.target.value); setDays(d); void refresh(d) }}>
              <option value={7}>۷ روز</option>
              <option value={30}>۳۰ روز</option>
              <option value={90}>۹۰ روز</option>
            </select>
          }
        >
          {rows.length === 0 ? (
            <EmptyState icon={CalendarHeart} text="تولدی در این بازه نیست." />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table birthdays-table">
                <thead>
                  <tr>
                    <th>مشتری</th>
                    <th>تولد</th>
                    <th>تا تولد</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((b) => (
                    <tr key={b.contact_id}>
                      <td data-label="مشتری">
                        <div className="entity-cell">
                          <div className="entity-avatar tone-customer">{b.contact_name.trim().charAt(0) || '؟'}</div>
                          <div>
                            <div className="entity-name">{b.contact_name}</div>
                            <div className="entity-sub">{fa(b.turning_age)} ساله می‌شود</div>
                          </div>
                        </div>
                      </td>
                      <td data-label="تولد">{formatJalali(b.next_birthday)}</td>
                      <td data-label="تا تولد">
                        {b.days_until === 0 ? (
                          <span className="status-badge tone-success"><Cake size={12} /> امروز!</span>
                        ) : (
                          <span>{fa(b.days_until)} روز</span>
                        )}
                      </td>
                      <td>
                        {giftPoints > 0 && (
                          <button type="button" onClick={() => void giveGift(b.contact_id)} title={`هدیه‌ی ${fa(giftPoints)} امتیاز`}>
                            <Gift size={13} /> هدیه
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </>
  )
}
