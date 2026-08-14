import { useEffect, useState } from 'react'
import { Award, Save, Trash2, Plus, Percent, Medal } from 'lucide-react'
import {
  createTier,
  deleteTier,
  fetchLoyaltySettings,
  fetchTierMembers,
  fetchTiers,
  setLoyaltySettings,
  updateTier,
  type LoyaltySettings,
  type LoyaltyTier,
  type TierMember,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'
import { Pager, usePagination } from './Pager'

const fa = (n: number | string) => Math.round(Number(n)).toLocaleString('fa-IR')

// ردیفِ سطح با ویرایشِ درجا؛ ذخیره فقط هنگامِ «از دست دادنِ فوکوس» (blur) تا هر تایپ یک درخواست نشود.
function TierRow({
  token,
  tier,
  onSaved,
  onRemove,
}: {
  token: string
  tier: LoyaltyTier
  onSaved: () => Promise<void>
  onRemove: () => void
}) {
  const [threshold, setThreshold] = useState(String(Number(tier.threshold)))
  const [discount, setDiscount] = useState(String(Number(tier.discount_percent)))

  async function commit() {
    const th = Number(threshold) || 0
    const dc = Number(discount) || 0
    if (th === Number(tier.threshold) && dc === Number(tier.discount_percent)) return
    await updateTier(token, tier.id, { name: tier.name, threshold: th, discount_percent: dc, sort_order: tier.sort_order })
    await onSaved()
  }

  return (
    <tr>
      <td data-label="سطح"><span className="entity-name">{tier.name}</span></td>
      <td data-label="آستانه" className="money-cell">
        <NumberInput value={threshold} onChange={setThreshold} onBlur={() => void commit()} style={{ width: 120 }} />
      </td>
      <td data-label="تخفیف" className="money-cell">
        <span className="tier-pct">
          <NumberInput value={discount} onChange={setDiscount} onBlur={() => void commit()} allowDecimal style={{ width: 60 }} />
          <Percent size={12} />
        </span>
      </td>
      <td>
        <button type="button" className="icon-btn-danger" onClick={onRemove} aria-label="حذف"><Trash2 size={13} /></button>
      </td>
    </tr>
  )
}

export function LoyaltyTiersPanel({ token }: { token: string }) {
  const [settings, setSettings] = useState<LoyaltySettings | null>(null)
  const [tiers, setTiers] = useState<LoyaltyTier[]>([])
  const [members, setMembers] = useState<TierMember[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', threshold: '', discount_percent: '' })
  const membersPg = usePagination(members, 10)

  async function refresh() {
    const [s, t, m] = await Promise.all([fetchLoyaltySettings(token), fetchTiers(token), fetchTierMembers(token)])
    setSettings(s)
    setTiers(t)
    setMembers(m)
  }
  useEffect(() => {
    void refresh()
  }, [])

  // ذخیره‌ی تنظیمات همیشه شیءِ کامل را می‌فرستد تا فیلدهای بخشِ دیگر (کسبِ خودکار، تولد) صفر نشوند.
  async function saveSettings(patch: Partial<LoyaltySettings>) {
    if (!settings) return
    const next = { ...settings, ...patch }
    setSettings(next)
    await setLoyaltySettings(token, {
      is_enabled: next.is_enabled,
      amount_per_point: Number(next.amount_per_point) || 0,
      tier_basis: next.tier_basis,
      tier_discount_auto: next.tier_discount_auto,
      birthday_gift_points: next.birthday_gift_points,
    })
  }

  async function addTier(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.name.trim()) {
      setMsg('نامِ سطح الزامی است.')
      return
    }
    try {
      await createTier(token, {
        name: form.name.trim(),
        threshold: Number(form.threshold) || 0,
        discount_percent: Number(form.discount_percent) || 0,
      })
      setForm({ name: '', threshold: '', discount_percent: '' })
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function remove(id: string) {
    await deleteTier(token, id)
    await refresh()
  }

  const basis = settings?.tier_basis ?? 'points'
  const basisWord = basis === 'points' ? 'امتیازِ فعال' : 'خریدِ ۱۲ ماهِ اخیر (ریال)'

  return (
    <>
      <SectionCard icon={Medal} title="مبنای سطح‌بندی" description="سطحِ هر مشتری بر پایه‌ی کدام معیار تعیین شود؟">
        <div className="benefit-toolbar">
          <label>
            مبنا
            <select value={basis} onChange={(e) => void saveSettings({ tier_basis: e.target.value as 'points' | 'spend' })}>
              <option value="points">امتیازِ فعال</option>
              <option value="spend">خریدِ سالانه (ریال)</option>
            </select>
          </label>
          <label className="cal-check-inline">
            <input
              type="checkbox"
              checked={settings?.tier_discount_auto ?? false}
              onChange={(e) => void saveSettings({ tier_discount_auto: e.target.checked })}
            />
            پیشنهادِ خودکارِ تخفیفِ سطح روی فاکتورِ فروش
          </label>
        </div>
      </SectionCard>

      <div className="workspace-split">
        <SectionCard icon={Plus} title="سطحِ جدید" description={`آستانه بر حسبِ ${basisWord}.`}>
          <form className="invoice-form form-full" onSubmit={addTier}>
            <label>
              نامِ سطح
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="برنز، نقره، طلا، …" required />
            </label>
            <div className="field-row">
              <label>
                آستانه ({basis === 'points' ? 'امتیاز' : 'ریال'})
                <NumberInput value={form.threshold} onChange={(v) => setForm({ ...form, threshold: v })} />
              </label>
              <label>
                تخفیف (٪)
                <NumberInput value={form.discount_percent} onChange={(v) => setForm({ ...form, discount_percent: v })} />
              </label>
            </div>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> افزودنِ سطح</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={Award} title="سطوحِ باشگاه" description={`${fa(tiers.length)} سطح — از پایین به بالا`}>
          {tiers.length === 0 ? (
            <EmptyState icon={Award} text="سطحی تعریف نشده. مثلاً برنز/نقره/طلا اضافه کنید." />
          ) : (
            <div className="entity-table-wrap">
              <table className="entity-table tiers-table">
                <thead>
                  <tr>
                    <th>سطح</th>
                    <th>آستانه</th>
                    <th>تخفیف</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {tiers.map((t) => (
                    <TierRow key={t.id} token={token} tier={t} onSaved={refresh} onRemove={() => void remove(t.id)} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>

      <SectionCard icon={Medal} title="اعضای سطوح" description={`${fa(members.length)} مشتری در سطوح — بر پایه‌ی ${basisWord}`}>
        {members.length === 0 ? (
          <EmptyState icon={Medal} text="هنوز مشتری‌ای به سطحی نرسیده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table">
              <thead>
                <tr>
                  <th>مشتری</th>
                  <th>سطح</th>
                  <th>{basis === 'points' ? 'امتیاز' : 'خریدِ سالانه'}</th>
                  <th>تخفیف</th>
                </tr>
              </thead>
              <tbody>
                {membersPg.pageItems.map((m) => (
                  <tr key={m.contact_id}>
                    <td data-label="مشتری">
                      <div className="entity-cell">
                        <div className="entity-avatar tone-customer">{m.contact_name.trim().charAt(0) || '؟'}</div>
                        <div className="entity-name">{m.contact_name}</div>
                      </div>
                    </td>
                    <td data-label="سطح"><span className="status-badge tone-success"><Medal size={12} /> {m.tier_name}</span></td>
                    <td data-label="مقدار" className="money-cell">{fa(m.value)}</td>
                    <td data-label="تخفیف" className="money-cell">{fa(m.discount_percent)}٪</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager page={membersPg.page} pageCount={membersPg.pageCount} onChange={membersPg.setPage} />
          </div>
        )}
      </SectionCard>
    </>
  )
}
