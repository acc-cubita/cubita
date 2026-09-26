import { describe, expect, it } from 'vitest'

import type { BalanceSheet, CashFlow, EquityStatement, IncomeStatement } from '../api'
import {
  balanceSheetCheck,
  balanceSheetRows,
  cashFlowRows,
  equityRows,
  incomeStatementRows,
  statementCsv,
  type StatementRow,
} from './reportSheets'

const acc = (id: string, name: string, balance: number) => ({
  account_id: id,
  account_code: id,
  account_name: name,
  balance: String(balance),
})
const shape = (rows: StatementRow[]) => rows.map((r) => `${r.kind}:${r.label}${'amount' in r ? `=${r.amount}` : ''}`)

describe('incomeStatementRows', () => {
  const is: IncomeStatement = {
    date_from: null,
    date_to: null,
    income: [acc('4101', 'فروش', 900)],
    expenses: [acc('6101', 'حقوق', 300), acc('6102', 'اجاره', 200)],
    total_income: '900',
    total_expenses: '500',
    net_profit: '400',
  }

  it('sections, lines, server subtotals and the net line', () => {
    expect(shape(incomeStatementRows(is))).toEqual([
      'section:درآمدها',
      'line:فروش=900',
      'subtotal:جمعِ درآمدها=900',
      'section:هزینه‌ها',
      'line:حقوق=300',
      'line:اجاره=200',
      'subtotal:جمعِ هزینه‌ها=500',
      'total:سود خالص=400',
    ])
  })

  it('names a loss as a loss and keeps its sign', () => {
    const rows = incomeStatementRows({ ...is, net_profit: '-50' })
    expect(rows.at(-1)).toEqual({ kind: 'total', label: 'زیان خالص', amount: -50 })
  })

  it('lines carry the account for the ledger drill-down', () => {
    expect(incomeStatementRows(is)[1]).toMatchObject({ code: '4101', accountId: '4101' })
  })
})

describe('balanceSheetRows / balanceSheetCheck', () => {
  const bs: BalanceSheet = {
    as_of: '2026-09-26',
    assets: [acc('1101', 'صندوق', 700), acc('1102', 'بانک', -100)],
    liabilities: [acc('2101', 'پرداختنی', 200)],
    equity: [acc('3101', 'سرمایه', 250)],
    total_assets: '600',
    total_liabilities: '200',
    total_equity: '250',
    current_period_profit: '150',
  }

  it('current-period profit is an equity line and is inside the equity subtotal', () => {
    const rows = balanceSheetRows(bs)
    expect(shape(rows).slice(-4)).toEqual([
      'line:سرمایه=250',
      'line:سود/زیانِ دوره‌ی جاری=150',
      'subtotal:جمعِ حقوق صاحبان سرمایه=400',
      'total:جمعِ بدهی‌ها و حقوق صاحبان سرمایه=600',
    ])
    expect(balanceSheetCheck(bs)).toEqual({ ok: true, diff: 0 })
  })

  it('reports the gap when assets ≠ liabilities + equity', () => {
    expect(balanceSheetCheck({ ...bs, total_assets: '610' })).toEqual({ ok: false, diff: 10 })
    expect(balanceSheetCheck({ ...bs, total_assets: '600.4' }).ok).toBe(true)
  })
})

describe('cashFlowRows', () => {
  it('opening, three activities with their net, change and closing', () => {
    const cf: CashFlow = {
      date_from: null,
      date_to: null,
      opening_cash: '100',
      operating: [{ account_id: 'a', account_code: '4101', account_name: 'فروش', amount: '80' }],
      investing: [],
      financing: [{ account_id: 'b', account_code: '3101', account_name: 'سرمایه', amount: '-30' }],
      net_operating: '80',
      net_investing: '0',
      net_financing: '-30',
      net_change: '50',
      closing_cash: '150',
    }
    expect(shape(cashFlowRows(cf))).toEqual([
      'subtotal:ماندهٔ نقد ابتدای دوره=100',
      'section:فعالیت‌های عملیاتی',
      'line:فروش=80',
      'subtotal:خالصِ وجوهِ عملیاتی=80',
      'section:فعالیت‌های سرمایه‌گذاری',
      'subtotal:خالصِ وجوهِ سرمایه‌گذاری=0',
      'section:فعالیت‌های تأمین مالی',
      'line:سرمایه=-30',
      'subtotal:خالصِ وجوهِ تأمین مالی=-30',
      'total:تغییرِ خالصِ نقد=50',
      'total:ماندهٔ نقد پایان دوره=150',
    ])
  })
})

describe('equityRows', () => {
  it('withdrawals are negative so the column adds down to the closing balance', () => {
    const eq = {
      opening_equity: '1000',
      contributions: '300',
      withdrawals: '100',
      other_changes: '50',
      closing_equity: '1250',
    } as EquityStatement
    const rows = equityRows(eq)
    const body = rows.filter((r) => r.kind !== 'total' && 'amount' in r) as { amount: number }[]
    expect(body.reduce((s, r) => s + r.amount, 0)).toBe(1250)
    expect(rows.at(-1)).toMatchObject({ kind: 'total', amount: 1250 })
  })
})

describe('statementCsv', () => {
  it('section rows are titles; lines keep their code; totals keep their number', () => {
    const rows: StatementRow[] = [
      { kind: 'section', label: 'درآمدها' },
      { kind: 'line', label: 'فروش', code: '4101', amount: 900 },
      { kind: 'total', label: 'سود خالص', amount: 900 },
    ]
    expect(statementCsv(rows)).toEqual([
      ['درآمدها', '', ''],
      ['فروش', '4101', 900],
      ['سود خالص', '', 900],
    ])
  })
})
