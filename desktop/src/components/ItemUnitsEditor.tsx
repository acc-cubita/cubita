import { useEffect, useState } from 'react'
import { addItemUnit, deactivateItemConversionRule, fetchItemConversionRules, fetchItemUnits,
  previewItemQuantity, saveItemConversionRule, updateItemUnit,
  type ItemConversionRule, type ItemRecord, type ItemUnitRecord, type UnitRecord } from '../api'
import { NumberInput } from './NumberInput'
import { SearchSelect } from './SearchSelect'
import { toFaDigits } from '../lib/jalali'

const flags = [
  ['purchase_allowed', 'خرید'], ['sale_allowed', 'فروش'], ['inventory_allowed', 'انبار'],
  ['production_allowed', 'تولید'], ['decimal_allowed', 'اعشار'], ['is_active', 'فعال'],
] as const

export function ItemUnitsEditor({ token, item, masterUnits, onClose }: {
  token: string; item: ItemRecord; masterUnits: UnitRecord[]; onClose: () => void
}) {
  const [units, setUnits] = useState<ItemUnitRecord[]>([])
  const [rules, setRules] = useState<ItemConversionRule[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [newUnit, setNewUnit] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [factor, setFactor] = useState('')
  const [mode, setMode] = useState<'fixed' | 'variable'>('fixed')
  const [editing, setEditing] = useState<string>()
  const [qty, setQty] = useState('1')
  const [previewUnit, setPreviewUnit] = useState('')
  const [preview, setPreview] = useState('')

  async function load() {
    const [members, conversions] = await Promise.all([fetchItemUnits(token, item.id), fetchItemConversionRules(token, item.id)])
    setUnits(members); setRules(conversions)
  }
  useEffect(() => {
    let live = true
    void Promise.all([fetchItemUnits(token, item.id), fetchItemConversionRules(token, item.id)])
      .then(([members, conversions]) => { if (live) { setUnits(members); setRules(conversions) } })
      .catch((err: unknown) => { if (live) setError(err instanceof Error ? err.message : 'دریافت واحدهای کالا ناموفق بود؛ دوباره باز کنید') })
    return () => { live = false }
  }, [token, item.id])
  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError(''); setPreview('')
    try { await action(); await load() }
    catch (err) { setError(err instanceof Error ? err.message : 'ذخیرهٔ واحد ناموفق بود؛ دوباره تلاش کنید') }
    finally { setBusy(false) }
  }
  const name = (id: string) => units.find(u => u.unit_id === id)?.unit_name ?? masterUnits.find(u => u.id === id)?.name ?? 'واحد حذف‌شده'
  const options = units.filter(u => u.is_active).map(u => <option key={u.unit_id} value={u.unit_id}>{u.unit_name}</option>)

  return <section className="panel" aria-label={`واحدهای ${item.name}`}>
    <div className="panel-toolbar"><h3>واحدها و تبدیل‌های «{item.name}»</h3><button type="button" onClick={onClose}>بستن</button></div>
    <p>موجودی با واحد پایه ثبت می‌شود. نسبت ثابت متعلق به همین کالا است؛ نسبت متغیر به مقدار واقعی بار یا معامله نیاز دارد.</p>
    {error && <p role="alert" className="error-text">{error}</p>}
    <fieldset disabled={busy}>
      <legend>واحدهای مجاز</legend>
      {units.length === 0 && <p className="mod-list-empty">واحدی ثبت نشده است؛ ابتدا واحد پایهٔ کالا را در شناسنامه ذخیره کنید.</p>}
      <div className="check-actions">
        <SearchSelect aria-label="واحد تازه" value={newUnit} onChange={e => setNewUnit(e.target.value)}><option value="">انتخاب واحد</option>
          {masterUnits.filter(u => u.is_active && !units.some(m => m.unit_id === u.id)).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
        </SearchSelect>
        <button type="button" disabled={!newUnit} onClick={() => void run(async () => { await addItemUnit(token, item.id, newUnit); setNewUnit('') })}>افزودن واحد</button>
      </div>
      <div className="table-scroll"><table className="data-table cards-on-mobile"><thead><tr><th>واحد</th>{flags.map(([key, label]) => <th key={key}>{label}</th>)}</tr></thead>
        <tbody>{units.map(u => <tr key={u.unit_id}><td data-label="واحد">{u.unit_name}{u.is_base ? ' (پایه)' : ''}</td>
          {flags.map(([key, label]) => <td key={key} data-label={label}><input type="checkbox" aria-label={`${label} ${u.unit_name}`} checked={u[key]}
            disabled={u.is_base && (key === 'is_active' || key === 'inventory_allowed')}
            onChange={e => void run(() => updateItemUnit(token, item.id, u.unit_id, { [key]: e.target.checked }))} /></td>)}
        </tr>)}</tbody></table></div>
    </fieldset>
    <fieldset disabled={busy}>
      <legend>نسبت‌های تبدیل</legend>
      {rules.map(r => <div className="check-actions" key={r.id}>
        <span>۱ {name(r.from_unit_id)} = {r.mode === 'variable' ? 'متغیر' : toFaDigits(r.factor ?? '')} {name(r.to_unit_id)} · نسخهٔ {r.version.toLocaleString('fa-IR')}{r.is_active ? '' : ' · غیرفعال'}</span>
        <button type="button" onClick={() => { setEditing(r.id); setFrom(r.from_unit_id); setTo(r.to_unit_id); setMode(r.mode); setFactor(r.factor ?? '') }}>ویرایش</button>
        {r.is_active && <button type="button" onClick={() => void run(() => deactivateItemConversionRule(token, item.id, r.id))}>غیرفعال‌سازی</button>}
      </div>)}
      <div className="form-grid">
        <label>از واحد<SearchSelect disabled={!!editing} value={from} onChange={e => setFrom(e.target.value)}><option value="">انتخاب کنید</option>{options}</SearchSelect></label>
        <label>به واحد<SearchSelect disabled={!!editing} value={to} onChange={e => setTo(e.target.value)}><option value="">انتخاب کنید</option>{options}</SearchSelect></label>
        <label>نوع نسبت<SearchSelect disabled={!!editing} value={mode} onChange={e => setMode(e.target.value as 'fixed' | 'variable')}><option value="fixed">ثابت</option><option value="variable">متغیر</option></SearchSelect></label>
        {mode === 'fixed' && <label>تعداد واحد مقصد در یک واحد مبدأ<NumberInput allowDecimal value={factor} onChange={setFactor} /></label>}
      </div>
      <button type="button" disabled={!from || !to || from === to || (mode === 'fixed' && !factor)} onClick={() => void run(async () => {
        await saveItemConversionRule(token, item.id, { from_unit_id: from, to_unit_id: to, mode, factor: mode === 'fixed' ? factor : null }, editing)
        setEditing(undefined); setFrom(''); setTo(''); setFactor('')
      })}>{editing ? 'ذخیره و فعال‌کردن نسبت' : 'ثبت نسبت'}</button>
      {editing && <button type="button" onClick={() => { setEditing(undefined); setFrom(''); setTo(''); setFactor('') }}>لغو ویرایش</button>}
    </fieldset>
    <fieldset disabled={busy}>
      <legend>پیش‌نمایش تبدیل به واحد پایه</legend>
      <div className="form-grid"><label>مقدار<NumberInput allowDecimal value={qty} onChange={setQty} /></label><label>واحد<SearchSelect value={previewUnit} onChange={e => setPreviewUnit(e.target.value)}><option value="">انتخاب کنید</option>{options}</SearchSelect></label></div>
      <button type="button" disabled={!previewUnit || !qty} onClick={() => void run(async () => {
        const result = await previewItemQuantity(token, item.id, { qty, unit_id: previewUnit, context: 'inventory' })
        // Keep the server's decimal string; JavaScript must not recompute the ratio.
        setPreview(`${result.target_qty} ${name(result.target_unit_id)}`)
      })}>محاسبه</button>
      {preview && <p role="status">مقدار پایه: {toFaDigits(preview)}</p>}
    </fieldset>
  </section>
}
