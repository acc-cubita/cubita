import { useEffect, useRef, useState } from 'react'
import { fetchItemUnits, fetchItemConversionRules, previewItemQuantity,
  type ItemUnitRecord, type ItemConversionRule, type QuantityConversionSnapshot, type UnitObservation } from '../api'
import { SearchSelect } from './SearchSelect'
import { NumberInput } from './NumberInput'
import { toFaDigits } from '../lib/jalali'

export interface TransactionUnitPatch {
  unitId?: string
  unitName?: string
  observations?: UnitObservation[]
  baseQtyPreview?: string
}

/** The server owns graph resolution and rounding. This control only collects input. */
export function TransactionUnitPicker({ token, itemId, qty, unitId, observations = [], context, onChange }: {
  token: string; itemId: string; qty: string; unitId?: string; observations?: UnitObservation[]
  context: 'purchase' | 'sale' | 'inventory' | 'production'; onChange: (patch: TransactionUnitPatch) => void
}) {
  const [units, setUnits] = useState<ItemUnitRecord[]>([])
  const [rules, setRules] = useState<ItemConversionRule[]>([])
  const [preview, setPreview] = useState<QuantityConversionSnapshot | null>(null)
  const [error, setError] = useState('')
  const callback = useRef(onChange)
  callback.current = onChange
  useEffect(() => {
    let cancelled = false
    setUnits([]); setRules([]); setPreview(null); setError('')
    if (!itemId) return
    Promise.all([fetchItemUnits(token, itemId), fetchItemConversionRules(token, itemId)])
      .then(([members, conversions]) => {
        if (!cancelled) { setUnits(members); setRules(conversions.filter((r) => r.is_active && r.mode === 'variable')) }
      }).catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'دریافت واحدهای کالا ناموفق بود')
      })
    return () => { cancelled = true }
  }, [token, itemId])
  const allowed = units.filter((u) => u.is_active && u[`${context}_allowed`])
  const selected = unitId || allowed.find((u) => u.is_base)?.unit_id || ''
  const observationKey = JSON.stringify(observations)
  useEffect(() => {
    let cancelled = false
    setPreview(null)
    callback.current({ baseQtyPreview: undefined })
    if (!itemId || !selected || !qty) return
    const timer = window.setTimeout(() => {
      previewItemQuantity(token, itemId, { qty, unit_id: selected, context,
        observations: JSON.parse(observationKey) as UnitObservation[] })
        .then((result) => {
          if (cancelled) return
          setError(''); setPreview(result)
          callback.current({ baseQtyPreview: result.target_qty })
        }).catch((err: unknown) => {
          if (cancelled) return
          setError(err instanceof Error ? err.message : 'تبدیل مقدار ناموفق بود')
          callback.current({ baseQtyPreview: undefined })
        })
    }, 250)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [token, itemId, qty, selected, context, observationKey])
  if (!itemId) return null
  function observe(rule: ItemConversionRule, field: 'from_qty' | 'to_qty', value: string) {
    const existing = observations.find((o) => o.rule_id === rule.id) || { rule_id: rule.id, from_qty: '', to_qty: '' }
    const next = { ...existing, [field]: value }
    callback.current({ observations: [...observations.filter((o) => o.rule_id !== rule.id), next], baseQtyPreview: undefined })
  }
  return <div className="transaction-unit-picker">
    <SearchSelect aria-label="واحد معامله" value={selected} onChange={(event) => {
      const unit = allowed.find((u) => u.unit_id === event.target.value)
      callback.current({ unitId: event.target.value, unitName: unit?.unit_name,
        observations: [], baseQtyPreview: undefined })
    }}>
      {!selected && <option value="">واحد را انتخاب کنید</option>}
      {unitId && !allowed.some((u) => u.unit_id === unitId) && <option value={unitId} disabled>
        {units.find((u) => u.unit_id === unitId)?.unit_name || 'واحد قبلی'} (برای این عملیات مجاز نیست)
      </option>}
      {allowed.map((unit) => <option key={unit.unit_id} value={unit.unit_id}>{unit.unit_name}{unit.is_base ? ' (پایه)' : ''}</option>)}
    </SearchSelect>
    {rules.length > 0 && <details><summary>نسبت واقعی این معامله</summary>
      {rules.map((rule) => {
        const observed = observations.find((o) => o.rule_id === rule.id)
        return <div className="field-row" key={rule.id}>
          <label>{units.find((u) => u.unit_id === rule.from_unit_id)?.unit_name || 'واحد مبدأ'}
            <NumberInput allowDecimal value={observed?.from_qty || ''} onChange={(value) => observe(rule, 'from_qty', value)} />
          </label>
          <label>{units.find((u) => u.unit_id === rule.to_unit_id)?.unit_name || 'واحد مقصد'}
            <NumberInput allowDecimal value={observed?.to_qty || ''} onChange={(value) => observe(rule, 'to_qty', value)} />
          </label>
        </div>
      })}
    </details>}
    {preview && <p className="hint">مقدار انبار: {toFaDigits(preview.target_qty)} {preview.target_unit_name || ''}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </div>
}
