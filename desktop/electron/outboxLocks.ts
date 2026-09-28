// قفل در main است، نه در دکمه: هم‌گام‌سازی خودکار و دو پنجره هم نباید با ویرایش رقابت کنند.
const sending = new Set<string>()
const editing = new Map<string, { token: string; payload: string }>()
const keyOf = (table: string, id: string) => `${table}:${id}`

export function tryLockOutboxSend(table: string, id: string): boolean {
  const key = keyOf(table, id)
  if (sending.has(key) || (table === 'outbox_journal_entries' && editing.has(id))) return false
  sending.add(key)
  return true
}
export function unlockOutboxSend(table: string, id: string): void { sending.delete(keyOf(table, id)) }

export function lockJournalEdit(id: string, token: string, payload: string): void {
  if (sending.has(keyOf('outbox_journal_entries', id)) || editing.has(id)) {
    throw new Error('این سند در حال ارسال یا ویرایش است؛ پس از پایان عملیات دوباره «ویرایش سند» را بزنید.')
  }
  editing.set(id, { token, payload })
}
export function journalEditLease(id: string, token: string): { payload: string } {
  const lease = editing.get(id)
  if (!lease || lease.token !== token) throw new Error('جلسهٔ ویرایش معتبر نیست؛ سند را دوباره از صف باز کنید.')
  return lease
}
export function releaseJournalEdit(id: string, token: string): void {
  if (editing.get(id)?.token === token) editing.delete(id)
}

export function clearJournalEditLocks(): void { editing.clear() }
