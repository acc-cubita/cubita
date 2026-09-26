import { describe, expect, it } from 'vitest'

import type { PnlPreviewRow } from '../api'
import { PNL_TONE, destinationLine, dimsText, pnlRowKey, pnlState } from './pnlClose'

const row = (extra: Partial<PnlPreviewRow> = {}): PnlPreviewRow => ({
  account_id: 'a1',
  account_code: '4101',
  account_name: 'فروش',
  account_type: 'income',
  analytic_id: null,
  analytic_code: null,
  analytic_name: null,
  cost_center_id: null,
  cost_center_name: null,
  debit: '500',
  credit: '0',
  side: 'debit',
  amount: '500',
  description: 'بستن حساب درآمد',
  ...extra,
})

describe('بستن سود و زیان — منطقِ برگه', () => {
  it('کلیدِ ردیف حساب و هر دو بُعد را دارد — یک حساب با دو تفصیلی دو ردیف است', () => {
    expect(pnlRowKey(row())).toBe('a1||')
    expect(pnlRowKey(row({ analytic_id: 'x', cost_center_id: 'c' }))).toBe('a1|x|c')
  })

  it('بُعدها زیرِ حساب: تفصیلی با کد، بعد مرکز؛ بی‌بُعد هیچ', () => {
    expect(dimsText(row())).toBeNull()
    expect(dimsText(row({ analytic_code: 'A1', analytic_name: 'آلفا', cost_center_name: 'تهران' }))).toBe('تفصیلی: A1 آلفا · مرکز: تهران')
    expect(dimsText(row({ cost_center_name: 'تهران' }))).toBe('مرکز: تهران')
  })

  it('خطِ مقصد: سود بستانکار، زیان بدهکار، بی سود و زیان بی خط', () => {
    expect(destinationLine({ net_profit: '300' })).toEqual({ debit: 0, credit: 300 })
    expect(destinationLine({ net_profit: '-70' })).toEqual({ debit: 70, credit: 0 })
    expect(destinationLine({ net_profit: '0' })).toBeNull()
  })

  it('حالِ نوار: بی ردیف، ناتراز، سود، زیان، برابر', () => {
    expect(pnlState({ rows: [], difference: '0', net_profit: '0' })).toBe('none')
    expect(pnlState({ rows: [row()], difference: '5', net_profit: '300' })).toBe('off')
    expect(pnlState({ rows: [row()], difference: '0', net_profit: '300' })).toBe('profit')
    expect(pnlState({ rows: [row()], difference: '0', net_profit: '-1' })).toBe('loss')
    expect(pnlState({ rows: [row()], difference: '0', net_profit: '0' })).toBe('even')
    expect([PNL_TONE.profit, PNL_TONE.loss, PNL_TONE.none]).toEqual(['ok', 'err', 'empty'])
  })
})
