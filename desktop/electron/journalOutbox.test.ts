import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import type { OutboxEntry } from '../src/electron.d'
const state = vi.hoisted(() => ({ row: null as OutboxEntry | null, updates: 0 }))
vi.mock('./db.js', () => ({ getLocalDb: () => ({ prepare: (sql: string) => ({
  get: (id: string) => state.row?.local_id === id ? { ...state.row } : undefined,
  run: (...args: unknown[]) => {
    const synced = /SET synced = 1/.test(sql)
    const id = args[synced ? 2 : 1], old = args[synced ? 3 : 2]
    if (!state.row || state.row.local_id !== id || state.row.payload !== old || state.row.synced) return { changes: 0 }
    state.updates++
    if (synced) { state.row.synced = 1; state.row.server_id = String(args[0]); state.row.server_number = Number(args[1]) }
    else state.row.payload = String(args[0])
    state.row.sync_error = null
    return { changes: 1 }
  },
}) }) }))
vi.mock('./sync.js', () => ({ pushOneJournal: vi.fn() }))
import { beginJournalEdit, cancelJournalEdit, clearJournalEditors, saveJournalEdit } from './journalOutbox'
import { tryLockOutboxSend, unlockOutboxSend } from './outboxLocks'
import { pushOneJournal } from './sync'

const payload = { entry_date: '2026-09-28', description: 'اصلی', lines: [{ account_id: 'a', debit: 100, credit: 0 }, { account_id: 'b', debit: 0, credit: 100 }] }
const config = { apiBaseUrl: 'http://company:8420', getToken: () => 't' }
const fetchMock = vi.fn()
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })
beforeEach(() => {
  clearJournalEditors(); state.updates = 0
  state.row = { local_id: 'same-id', payload: JSON.stringify(payload), synced: 0, server_id: null, server_number: null, sync_error: 'old error', created_at: 'original-time' }
  fetchMock.mockReset().mockImplementation(async () => json({ state: 'editable' })); vi.stubGlobal('fetch', fetchMock)
  vi.mocked(pushOneJournal).mockReset().mockResolvedValue({ pushed: 0, failed: 1 })
})
afterEach(() => { clearJournalEditors(); unlockOutboxSend('outbox_journal_entries', 'same-id'); vi.unstubAllGlobals() })
async function editing() {
  const result = await beginJournalEdit(config, 'same-id')
  if (result.state !== 'editing') throw new Error('not editable')
  return result.edit
}
describe('ویرایش امن همان ردیف SQLite', () => {
  it('پاسخ HTML یا JSON خراب با پیام فارسی رد می‌شود و صف دست‌نخورده است', async () => {
    fetchMock.mockImplementation(async () => new Response('<html>proxy</html>'))
    await expect(beginJournalEdit(config, 'same-id')).rejects.toThrow(/پاسخ وضعیت سند/)
    expect(state.updates).toBe(0); expect(state.row!.payload).toBe(JSON.stringify(payload))
  })
  it('قفل هنگام ویرایش، ذخیره همان local_id و created_at و retry فقط همان سند', async () => {
    const edit = await editing()
    expect(tryLockOutboxSend('outbox_journal_entries', edit.local_id)).toBe(false)
    expect(edit.payload).toBe(JSON.stringify(payload))
    const fixed = { ...payload, entry_date: '2026-09-29', description: 'اصلاح‌شده' }
    expect((await saveJournalEdit(config, edit.local_id, edit.lease, fixed)).state).toBe('queued')
    expect(state.row).toMatchObject({ local_id: 'same-id', created_at: 'original-time', payload: JSON.stringify(fixed), sync_error: null })
    expect(state.updates).toBe(1); expect(pushOneJournal).toHaveBeenCalledExactlyOnceWith(config, 'same-id')
    expect(tryLockOutboxSend('outbox_journal_entries', 'same-id')).toBe(true)
  })
  it('پاسخ ثبت گم‌شده فقط reconcile می‌شود و قابل ویرایش نیست', async () => {
    fetchMock.mockResolvedValue(json({ state: 'synced', server_id: 'registered', server_number: 7 }))
    expect((await beginJournalEdit(config, 'same-id')).state).toBe('synced')
    expect(state.row).toMatchObject({ synced: 1, server_id: 'registered', server_number: 7, payload: JSON.stringify(payload) })
    expect(pushOneJournal).not.toHaveBeenCalled()
  })
  it('شبکه قطع، سرور قدیمی و سند مشابه قدیمی هیچ payload را تغییر نمی‌دهند', async () => {
    for (const response of [json({ state: 'ambiguous' }), json({}, 404)]) {
      fetchMock.mockResolvedValue(response)
      await expect(beginJournalEdit(config, 'same-id')).rejects.toThrow(/صف/)
      expect(state.updates).toBe(0)
    }
    fetchMock.mockRejectedValue(new TypeError('fetch failed'))
    await expect(beginJournalEdit(config, 'same-id')).rejects.toThrow(/شبکه/)
    expect(state.row?.payload).toBe(JSON.stringify(payload))
    expect(tryLockOutboxSend('outbox_journal_entries', 'same-id')).toBe(true)
  })
  it('در حال ارسال یا دارای lease دیگر، ویرایش رد می‌شود', async () => {
    expect(tryLockOutboxSend('outbox_journal_entries', 'same-id')).toBe(true)
    await expect(beginJournalEdit(config, 'same-id')).rejects.toThrow(/در حال ارسال/)
    unlockOutboxSend('outbox_journal_entries', 'same-id')
    const edit = await editing()
    await expect(saveJournalEdit(config, edit.local_id, 'wrong', payload)).rejects.toThrow(/جلسه/)
    cancelJournalEdit('wrong-id', edit.lease)
    expect((await saveJournalEdit(config, edit.local_id, edit.lease, payload)).state).toBe('queued')
  })
  it('تغییر نشست، انصراف حین HTTP و تغییر payload بین بازکردن و ذخیره محفوظ می‌مانند', async () => {
    const edit = await editing()
    await expect(saveJournalEdit({ ...config, getToken: () => 'other-user' }, edit.local_id, edit.lease, payload)).rejects.toThrow(/نشست/)
    let resolve!: (response: Response) => void
    fetchMock.mockImplementation(() => new Promise((done) => { resolve = done }))
    const saving = saveJournalEdit(config, edit.local_id, edit.lease, { ...payload, description: 'جدید' })
    clearJournalEditors(); resolve(json({ state: 'editable' }))
    await expect(saving).rejects.toThrow(/جلسه/); expect(state.updates).toBe(0)
    fetchMock.mockResolvedValue(json({ state: 'editable' }))
    const next = await editing(); state.row!.payload = JSON.stringify({ ...payload, description: 'other writer' })
    await expect(saveJournalEdit(config, next.local_id, next.lease, payload)).rejects.toThrow(/تغییر/)
    expect(state.row!.payload).toContain('other writer')
  })
  it('در فاصله بازکردن و ذخیره اگر سرور ثبت کرده باشد، اصلاح جایگزین ثبت نمی‌شود', async () => {
    const edit = await editing()
    fetchMock.mockResolvedValue(json({ state: 'synced', server_id: 'registered', server_number: 9 }))
    const result = await saveJournalEdit(config, edit.local_id, edit.lease, { ...payload, description: 'جدید' })
    expect(result.state).toBe('synced'); expect(result.message).toContain('جایگزین')
    expect(state.row!.payload).toBe(JSON.stringify(payload)); expect(pushOneJournal).not.toHaveBeenCalled()
  })
})
