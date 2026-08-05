import { useEffect, useState } from 'react'
import { Gift, Save, Trash2, Plus, Ticket, ToggleLeft, ToggleRight } from 'lucide-react'
import {
  createReward,
  deleteReward,
  fetchRewards,
  redeemReward,
  updateReward,
  type ContactRecord,
  type LoyaltyReward,
  type RewardKind,
} from '../api'
import { SectionCard } from './SectionCard'
import { NumberInput } from './NumberInput'
import { EmptyState } from './EmptyState'

const fa = (n: number | string) => Math.round(Number(n)).toLocaleString('fa-IR')

const KIND_LABELS: Record<RewardKind, string> = { discount: 'تخفیف', gift: 'هدیه', other: 'سایر' }

function rewardValue(r: LoyaltyReward): string {
  if (r.kind === 'discount') return r.value ? `${fa(r.value)}٪ تخفیف` : 'تخفیف'
  return r.value || KIND_LABELS[r.kind]
}

export function RewardsPanel({
  token,
  contacts,
  onRedeemed,
}: {
  token: string
  contacts: ContactRecord[]
  onRedeemed: () => void
}) {
  const [rewards, setRewards] = useState<LoyaltyReward[]>([])
  const [form, setForm] = useState<{ name: string; points_cost: string; kind: RewardKind; value: string }>({
    name: '',
    points_cost: '',
    kind: 'gift',
    value: '',
  })
  const [msg, setMsg] = useState<string | null>(null)
  const [redeemContact, setRedeemContact] = useState('')
  const [redeemReward_, setRedeemReward] = useState('')
  const [redeemMsg, setRedeemMsg] = useState<string | null>(null)

  async function refresh() {
    setRewards(await fetchRewards(token))
  }
  useEffect(() => {
    void refresh()
  }, [])

  async function addReward(e: React.FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (!form.name.trim() || !(Number(form.points_cost) > 0)) {
      setMsg('نام و امتیازِ لازم (بزرگ‌تر از صفر) الزامی است.')
      return
    }
    try {
      await createReward(token, {
        name: form.name.trim(),
        points_cost: Number(form.points_cost),
        kind: form.kind,
        value: form.value.trim(),
        is_active: true,
      })
      setForm({ name: '', points_cost: '', kind: 'gift', value: '' })
      await refresh()
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function toggleActive(r: LoyaltyReward) {
    await updateReward(token, r.id, { name: r.name, points_cost: r.points_cost, kind: r.kind, value: r.value, is_active: !r.is_active })
    await refresh()
  }
  async function remove(id: string) {
    await deleteReward(token, id)
    await refresh()
  }

  async function redeem(e: React.FormEvent) {
    e.preventDefault()
    setRedeemMsg(null)
    if (!redeemContact || !redeemReward_) {
      setRedeemMsg('مشتری و جایزه را انتخاب کنید.')
      return
    }
    try {
      await redeemReward(token, { contact_id: redeemContact, reward_id: redeemReward_ })
      setRedeemMsg('جایزه بازخرید شد و امتیاز کسر گردید.')
      setRedeemReward('')
      onRedeemed()
    } catch (err) {
      setRedeemMsg(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  const activeRewards = rewards.filter((r) => r.is_active)

  return (
    <>
      <div className="workspace-split">
        <SectionCard icon={Plus} title="جایزه‌ی جدید" description="مثلاً «۵۰۰ امتیاز = تخفیفِ ۱۰٪» یا «۱۰۰۰ امتیاز = هدیه».">
          <form className="invoice-form form-full" onSubmit={addReward}>
            <label>
              نامِ جایزه
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="مثلاً کوپنِ تخفیف" required />
            </label>
            <div className="field-row">
              <label>
                امتیازِ لازم
                <NumberInput value={form.points_cost} onChange={(v) => setForm({ ...form, points_cost: v })} required />
              </label>
              <label>
                نوع
                <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as RewardKind })}>
                  <option value="gift">هدیه</option>
                  <option value="discount">تخفیف (٪)</option>
                  <option value="other">سایر</option>
                </select>
              </label>
            </div>
            <label>
              {form.kind === 'discount' ? 'درصدِ تخفیف' : 'توضیح'}
              <input type="text" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} placeholder={form.kind === 'discount' ? 'مثلاً ۱۰' : 'شرحِ جایزه'} />
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Save size={14} /> افزودنِ جایزه</button>
            </div>
            {msg && <div className="hint">{msg}</div>}
          </form>
        </SectionCard>

        <SectionCard icon={Ticket} title="بازخریدِ جایزه" description="امتیازِ مشتری را در برابرِ یک جایزه خرج کنید.">
          <form className="invoice-form form-full" onSubmit={redeem}>
            <label>
              مشتری
              <select value={redeemContact} onChange={(e) => setRedeemContact(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>
            <label>
              جایزه
              <select value={redeemReward_} onChange={(e) => setRedeemReward(e.target.value)} required>
                <option value="">— انتخاب —</option>
                {activeRewards.map((r) => (
                  <option key={r.id} value={r.id}>{r.name} ({fa(r.points_cost)} امتیاز)</option>
                ))}
              </select>
            </label>
            <div className="invoice-form-footer">
              <button type="submit" className="btn-primary"><Ticket size={14} /> بازخرید</button>
            </div>
            {redeemMsg && <div className="hint">{redeemMsg}</div>}
          </form>
        </SectionCard>
      </div>

      <SectionCard icon={Gift} title="کاتالوگِ جوایز" description={`${fa(rewards.length)} جایزه`}>
        {rewards.length === 0 ? (
          <EmptyState icon={Gift} text="جایزه‌ای تعریف نشده." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table rewards-table">
              <thead>
                <tr>
                  <th>جایزه</th>
                  <th>نوع</th>
                  <th>امتیازِ لازم</th>
                  <th>وضعیت</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rewards.map((r) => (
                  <tr key={r.id} className={r.is_active ? '' : 'row-muted'}>
                    <td data-label="جایزه">
                      <div className="entity-name">{r.name}</div>
                      <div className="entity-sub">{rewardValue(r)}</div>
                    </td>
                    <td data-label="نوع"><span className="status-badge tone-default">{KIND_LABELS[r.kind]}</span></td>
                    <td data-label="امتیازِ لازم" className="money-cell"><strong>{fa(r.points_cost)}</strong></td>
                    <td data-label="وضعیت">
                      <button type="button" className="link-btn" onClick={() => void toggleActive(r)}>
                        {r.is_active ? <><ToggleRight size={15} /> فعال</> : <><ToggleLeft size={15} /> غیرفعال</>}
                      </button>
                    </td>
                    <td>
                      <button type="button" className="icon-btn-danger" onClick={() => void remove(r.id)} aria-label="حذف"><Trash2 size={13} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}
