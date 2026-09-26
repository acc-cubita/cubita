import { describe, expect, it } from 'vitest'

import type { GeneralLedger, GeneralLedgerLine, JournalEntryRecord } from '../api'
import { daybookColumns, daybookRows, ledgerColumns, ledgerCsv, ledgerPeriod, selectionSums } from './ledgerReport'

const entry = (id: string, lines: Partial<JournalEntryRecord['lines'][number]>[]): JournalEntryRecord =>
  ({
    id,
    number: Number(id),
    entry_date: '2026-09-20',
    description: `سند ${id}`,
    status: 'permanent',
    lines: lines.map((l, i) => ({ id: `${id}-${i}`, account_id: 'a', debit: '0', credit: '0', description: '', ...l })),
  }) as unknown as JournalEntryRecord

const line = (over: Partial<GeneralLedgerLine> = {}): GeneralLedgerLine =>
  ({
    line_id: 'l',
    entry_id: 'e',
    entry_number: 1,
    entry_date: '2026-09-20',
    entry_status: 'permanent',
    source_type: 'manual',
    account_code: '1101',
    account_name: 'صندوق',
    description: 'شرح',
    debit: '0',
    credit: '0',
    balance: '0',
    currency_code: null,
    fx_amount: null,
    fx_rate: null,
    tracking_no: null,
    tracking_date: null,
    ...over,
  }) as GeneralLedgerLine

describe('daybookRows / daybookColumns', () => {
  it('each entry is a group row followed by its lines, in order', () => {
    const rows = daybookRows([entry('1', [{ debit: '5' }, { credit: '5' }]), entry('2', [{ debit: '3' }, { credit: '3' }])])
    expect(rows.map((r) => (r.kind === 'entry' ? `E${r.entry.id}` : `${r.entry.id}.${r.index}`))).toEqual([
      'E1',
      '1.0',
      '1.1',
      'E2',
      '2.0',
      '2.1',
    ])
  })
  it('optional columns appear only when some line has them', () => {
    expect(daybookColumns([entry('1', [{}])])).toEqual({ fx: false, tracking: false })
    expect(daybookColumns([entry('1', [{}]), entry('2', [{ currency_code: 'USD' }])]).fx).toBe(true)
  })
})

describe('ledgerColumns / ledgerPeriod', () => {
  it('account column only for multi-account books', () => {
    expect(ledgerColumns([line()], false).account).toBe(false)
    expect(ledgerColumns([line({ tracking_no: 'T1' })], true)).toEqual({ account: true, fx: false, tracking: true })
  })
  it('period totals come from the server when sent, else from the lines', () => {
    const base = { opening_balance: '0', closing_balance: '0', fx_totals: [], account_id: null, account_code: null, account_name: null }
    const lines = [line({ debit: '10' }), line({ credit: '4' })]
    expect(ledgerPeriod({ ...base, lines } as GeneralLedger)).toEqual({ debit: 10, credit: 4 })
    expect(ledgerPeriod({ ...base, lines, period_debit: '99', period_credit: '1' } as GeneralLedger)).toEqual({ debit: 99, credit: 1 })
  })
})

describe('selectionSums', () => {
  it('debit, credit and net of the picked lines', () => {
    expect(selectionSums([{ debit: '10', credit: '0' }, { debit: '0', credit: '3' }])).toEqual({ debit: 10, credit: 3, net: 7 })
  })
})

describe('ledgerCsv', () => {
  it('starts with the opening balance and keeps optional columns aligned', () => {
    const data = {
      account_id: 'a',
      account_code: '1101',
      account_name: 'صندوق',
      opening_balance: '50',
      closing_balance: '60',
      fx_totals: [],
      lines: [line({ entry_number: 7, debit: '10', balance: '60', currency_code: 'USD', fx_amount: '2' })],
    } as GeneralLedger
    const { headers, rows } = ledgerCsv(data, { account: false, fx: true, tracking: false }, (d) => d)
    expect(headers).toEqual(['شماره سند', 'تاریخ', 'شرح', 'ارز', 'مبلغ ارزی', 'بدهکار', 'بستانکار', 'مانده'])
    expect(rows[0]).toHaveLength(headers.length)
    expect(rows[0].at(-1)).toBe(50)
    expect(rows[1]).toEqual([7, '2026-09-20', 'شرح', 'USD', 2, 10, 0, 60])
  })
})
