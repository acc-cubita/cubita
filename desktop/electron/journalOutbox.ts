import { randomUUID } from 'node:crypto'
import { getLocalDb } from './db.js'
import { lockJournalEdit, journalEditLease, releaseJournalEdit, clearJournalEditLocks } from './outboxLocks.js'
import { pushOneJournal } from './sync.js'
import { parseQueuedJournalDraft } from '../src/lib/journalOutboxDraft.js'
import { outboxErrorText } from '../src/lib/outboxError.js'
import type { OutboxEntry, JournalOutboxSaveResult } from '../src/electron.d.js'

interface Config { apiBaseUrl: string; getToken: () => string | null }
type RemoteState = { state: 'editable' | 'ambiguous' } | { state: 'synced'; server_id: string; server_number: number }
const editOwners = new Map<string, { token: string; url: string }>()
const rowOf = (id: string) => getLocalDb().prepare('SELECT * FROM outbox_journal_entries WHERE local_id = ?').get(id) as OutboxEntry | undefined

async function remoteStatus(config: Config, localId: string, payload: string): Promise<RemoteState> {
  const token = config.getToken()
  if (!token) throw new Error('برای ویرایش سند دوباره وارد حساب شوید؛ اطلاعات صف حفظ شده است.')
  let response: Response
  try {
    response = await fetch(`${config.apiBaseUrl}/api/journal-entries/outbox-status`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ local_id: localId, payload: JSON.parse(payload) }), signal: AbortSignal.timeout(10_000),
    })
  } catch { throw new Error('برای اطمینان از ثبت‌نشدن سند، اتصال به سرور لازم است؛ شبکه را وصل کنید و دوباره «ویرایش سند» را بزنید. صف حفظ شده است.') }
  if (response.status === 404 || response.status === 405) {
    throw new Error('این سرور هنوز ویرایش امن صف را پشتیبانی نمی‌کند؛ ابتدا سرور را به نسخهٔ جدید به‌روز کنید. صف حفظ شده است.')
  }
  if (!response.ok) throw new Error(outboxErrorText(await response.text()))
  let result: RemoteState
  try { result = await response.json() as RemoteState }
  catch { throw new Error('پاسخ وضعیت سند از سرور معتبر نیست؛ صف تغییر نکرد. اتصال و نسخهٔ سرور را بررسی کنید.') }
  if (result?.state === 'editable' || result?.state === 'ambiguous') return result
  if (result?.state === 'synced' && typeof result.server_id === 'string' && Number.isInteger(result.server_number)) return result
  throw new Error('وضعیت سند از سرور خوانده نشد؛ ویرایش انجام نشد. اتصال و نسخهٔ سرور را بررسی کنید.')
}

function reconcile(localId: string, payload: string, remote: RemoteState): boolean {
  if (remote.state === 'ambiguous') {
    throw new Error('ممکن است این سند قبلاً با نسخهٔ قدیمی روی سرور ثبت شده باشد؛ پیش از اصلاح، «حسابداری ← فهرست ← اسناد حسابداری» را با مدیر بررسی کنید. صف تغییر نکرد.')
  }
  if (remote.state !== 'synced') return false
  const updated = getLocalDb().prepare('UPDATE outbox_journal_entries SET synced = 1, server_id = ?, server_number = ?, sync_error = NULL WHERE local_id = ? AND payload = ? AND synced = 0')
    .run(remote.server_id, remote.server_number, localId, payload)
  if (updated.changes !== 1) throw new Error('وضعیت صف تغییر کرده است؛ سند را دوباره از صف بخوانید. داده‌ای بازنویسی نشد.')
  return true
}

export async function beginJournalEdit(config: Config, localId: string) {
  const row = rowOf(localId)
  if (!row || row.synced) throw new Error('این سند ارسال شده یا در صف نیست؛ سند ثبت‌شده را از فهرست اسناد بررسی کنید.')
  parseQueuedJournalDraft(row.payload)
  const lease = randomUUID()
  lockJournalEdit(localId, lease, row.payload)
  editOwners.set(lease, { token: config.getToken() ?? '', url: config.apiBaseUrl })
  try {
    const remote = await remoteStatus(config, localId, row.payload)
    journalEditLease(localId, lease)
    if (reconcile(localId, row.payload, remote)) {
      cancelJournalEdit(localId, lease)
      return { state: 'synced' as const, message: 'این سند قبلاً روی سرور ثبت شده بود؛ وضعیت صف اصلاح شد. برای بررسی، فهرست اسناد را باز کنید.' }
    }
    return { state: 'editing' as const, edit: { local_id: localId, lease, payload: row.payload } }
  } catch (error) { cancelJournalEdit(localId, lease); throw error }
}

export function cancelJournalEdit(localId: string, lease: string): void {
  try { journalEditLease(localId, lease) } catch { return }
  releaseJournalEdit(localId, lease)
  editOwners.delete(lease)
}

export function clearJournalEditors(): void { clearJournalEditLocks(); editOwners.clear() }

export async function saveJournalEdit(config: Config, localId: string, lease: string, payload: unknown): Promise<JournalOutboxSaveResult> {
  const locked = journalEditLease(localId, lease)
  const owner = editOwners.get(lease)
  if (owner?.token !== config.getToken() || owner.url !== config.apiBaseUrl) throw new Error('نشست یا سرور عوض شده است؛ ویرایش را ببندید و سند را دوباره از صف باز کنید.')
  const row = rowOf(localId)
  if (!row || row.synced || row.payload !== locked.payload) throw new Error('وضعیت سند تغییر کرده؛ ویرایش را ببندید و صف را دوباره بخوانید. اطلاعات قبلی بازنویسی نشد.')
  const next = JSON.stringify(payload)
  parseQueuedJournalDraft(next)
  const remote = await remoteStatus(config, localId, row.payload)
  journalEditLease(localId, lease)
  if (reconcile(localId, row.payload, remote)) {
    cancelJournalEdit(localId, lease)
    return { state: 'synced', message: 'سند قبلاً روی سرور ثبت شده بود؛ اصلاحات جایگزین سند ثبت‌شده نشد و وضعیت صف به‌روز شد.' }
  }
  const result = getLocalDb().prepare('UPDATE outbox_journal_entries SET payload = ?, sync_error = NULL WHERE local_id = ? AND payload = ? AND synced = 0')
    .run(next, localId, locked.payload)
  if (result.changes !== 1) throw new Error('ذخیرهٔ اصلاحات انجام نشد؛ صف را دوباره بخوانید. سند تازه‌ای ساخته نشد.')
  cancelJournalEdit(localId, lease)
  const sent = await pushOneJournal(config, localId)
  return sent.pushed
    ? { state: 'synced', message: 'همان سند اصلاح و به سرور ارسال شد؛ سند تکراری ساخته نشد.' }
    : { state: 'queued', message: 'اصلاحات روی همان سند ذخیره شد، اما ارسال کامل نشد؛ علت را در صف ببینید و «هم‌گام‌سازی» را بزنید.' }
}
