/**
 * منطقِ صفحه‌ی «اسناد تکرارشونده»: متنِ تناوب، اعتبارِ قالب پیش از ارسال، بار و ذخیره، و ترتیبِ فهرست.
 */
import { describe, expect, it } from 'vitest'

import type { RecurringEntry } from '../api'
import {
  blankForm,
  blankLine,
  formFromEntry,
  freqText,
  lineTotals,
  sortTemplates,
  templateMatches,
  templateProblem,
  toPayload,
  type RecurringLineDraft,
} from './recurringSheet'

const line = (account_id: string, debit: string, credit: string, description = ''): RecurringLineDraft => ({
  account_id,
  description,
  debit,
  credit,
})
const form = { ...blankForm('2026-09-25'), title: 'اجاره‌ی دفتر' }
const balanced = [line('rent', '50000000', ''), line('bank', '', '50000000')]

const entry = (over: Partial<RecurringEntry>): RecurringEntry => ({
  id: 'x',
  title: 't',
  description: '',
  frequency: 'monthly',
  interval: 1,
  start_date: '2026-09-01',
  end_date: null,
  next_run_date: '2026-10-01',
  last_run_date: null,
  is_active: true,
  cost_center_id: null,
  created_at: null,
  is_due: false,
  amount: '100',
  lines: [],
  ...over,
})

describe('تناوب', () => {
  it('یک‌بار در هر دوره نامِ خودش را دارد؛ بیشتر «هر n واحد»', () => {
    expect(freqText('monthly', 1)).toBe('ماهانه')
    expect(freqText('monthly', 3)).toBe('هر ۳ ماه')
    expect(freqText('weekly', 2)).toBe('هر ۲ هفته')
  })
})

describe('اعتبارِ قالب پیش از ارسال', () => {
  it('قالبِ درست هیچ خطایی ندارد؛ ردیفِ کاملاً خالی نادیده گرفته می‌شود', () => {
    expect(templateProblem(form, [...balanced, blankLine()])).toBeNull()
  })

  it('عنوان، فاصله و تاریخ‌ها', () => {
    expect(templateProblem({ ...form, title: ' ' }, balanced)).toBe('عنوانِ قالب را بنویسید.')
    expect(templateProblem({ ...form, interval: '0' }, balanced)).toContain('هر چند دوره')
    expect(templateProblem({ ...form, interval: '1.5' }, balanced)).toContain('هر چند دوره')
    expect(templateProblem({ ...form, end_date: '2026-09-01' }, balanced)).toBe('تاریخِ پایان پیش از تاریخِ شروع است.')
    expect(templateProblem({ ...form, end_date: '2027-09-01' }, balanced)).toBeNull()
  })

  it('ردیفِ نیمه‌کاره با شماره‌اش گفته می‌شود', () => {
    expect(templateProblem(form, [...balanced, line('fee', '', '')])).toBe('ردیفِ ۳ مبلغ ندارد.')
    expect(templateProblem(form, [line('', '10', ''), ...balanced])).toBe('ردیفِ ۱ حساب ندارد.')
    //: فقط شرح هم ردیف را «شروع‌شده» می‌کند.
    expect(templateProblem(form, [...balanced, { ...blankLine(), description: 'کارمزد' }])).toBe('ردیفِ ۳ حساب ندارد.')
  })

  it('دست‌کم دو ردیف و متوازن', () => {
    expect(templateProblem(form, [line('rent', '5', '')])).toContain('دو ردیف')
    expect(templateProblem(form, [line('rent', '5', ''), line('bank', '', '4')])).toContain('متوازن نیست')
  })
})

describe('بار و ذخیره', () => {
  it('ذخیره: ردیف‌های پر با شرح، عددِ فاصله، پایانِ خالی یعنی null', () => {
    const p = toPayload({ ...form, interval: '2', description: ' شرح ' }, [...balanced, blankLine()])
    expect(p).toMatchObject({ title: 'اجاره‌ی دفتر', description: 'شرح', interval: 2, end_date: null, cost_center_id: null })
    expect(p.lines).toEqual([
      { account_id: 'rent', debit: 50000000, credit: 0, description: '' },
      { account_id: 'bank', debit: 0, credit: 50000000, description: '' },
    ])
  })

  it('بارِ قالبِ ثبت‌شده: مبلغِ صفر خالی، پایانِ null خالی، شرحِ ردیف می‌ماند', () => {
    const { form: f, lines } = formFromEntry(
      entry({
        title: 'بیمه',
        interval: 3,
        end_date: null,
        lines: [
          { id: '1', account_id: 'a', account_code: '6101', account_name: 'بیمه', debit: '1200.00', credit: '0.00', description: 'قسط' },
          { id: '2', account_id: 'b', account_code: '1102', account_name: 'بانک', debit: '0.00', credit: '1200.00', description: '' },
        ],
      }),
    )
    expect(f).toMatchObject({ title: 'بیمه', interval: '3', end_date: '' })
    expect(lines).toEqual([line('a', '1200', '', 'قسط'), line('b', '', '1200')])
    expect(lineTotals(lines)).toEqual({ debit: 1200, credit: 1200 })
  })
})

describe('فهرستِ قالب‌ها', () => {
  it('سررسیدشده بالا، بعد فعال به سررسیدِ نزدیک‌تر، غیرفعال ته', () => {
    const out = sortTemplates([
      entry({ id: 'off', is_active: false, next_run_date: '2026-01-01' }),
      entry({ id: 'later', next_run_date: '2026-12-01' }),
      entry({ id: 'due', is_due: true, next_run_date: '2026-09-20' }),
      entry({ id: 'soon', next_run_date: '2026-10-01' }),
    ])
    expect(out.map((e) => e.id)).toEqual(['due', 'soon', 'later', 'off'])
  })

  it('جست‌وجو در عنوان، شرح و حساب‌های ردیف', () => {
    const e = entry({
      title: 'اجاره',
      description: 'دفترِ مرکزی',
      lines: [{ id: '1', account_id: 'a', account_code: '6101', account_name: 'هزینه اجاره', debit: '1', credit: '0', description: '' }],
    })
    expect(templateMatches(e, '')).toBe(true)
    expect(templateMatches(e, 'مرکزی')).toBe(true)
    expect(templateMatches(e, '6101')).toBe(true)
    expect(templateMatches(e, 'بیمه')).toBe(false)
  })
})
