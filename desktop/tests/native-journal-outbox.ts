// Electron و SQLite واقعی؛ پوشه موقت و HTTP محلی آزمایشی، بدون داده نصب‌شده کاربر.
import { app } from 'electron'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { initLocalDb, getLocalDb } from '../electron/db'
import { queueJournalEntry, pushOutbox } from '../electron/sync'
import { beginJournalEdit, saveJournalEdit, cancelJournalEdit, clearJournalEditors } from '../electron/journalOutbox'

const qaDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cubita-outbox-qa-'))
app.setPath('userData', qaDir)
const registered = new Map<string, { id: string; number: number; payload: unknown }>()
let loseReply = false
let editable = true
const posts: { key: string; payload: Record<string, unknown> }[] = []
const server = createServer(async (request, response) => {
  let raw = ''; for await (const chunk of request) raw += chunk
  const data = JSON.parse(raw) as Record<string, any>
  response.setHeader('Content-Type', 'application/json')
  if (request.url?.endsWith('/outbox-status')) {
    const saved = registered.get(data.local_id)
    response.end(JSON.stringify(saved ? { state: 'synced', server_id: saved.id, server_number: saved.number } : { state: editable ? 'editable' : 'ambiguous' }))
    return
  }
  const key = String(request.headers['idempotency-key']); posts.push({ key, payload: data })
  if (data.entry_date === '2025-07-08') { response.statusCode = 400; response.end('{"detail":"تاریخ 2025-07-08 در هیچ سال مالی تعریف‌شده‌ای نیست"}'); return }
  const saved = registered.get(key) ?? { id: `registered-${registered.size + 1}`, number: registered.size + 1, payload: data }
  registered.set(key, saved)
  if (loseReply) { request.socket.destroy(); return }
  response.statusCode = 201; response.end(JSON.stringify(saved))
})

void (async () => {
  await app.whenReady(); initLocalDb()
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address(); assert(address && typeof address !== 'string')
  const config = { apiBaseUrl: `http://127.0.0.1:${address.port}`, getToken: () => 'qa-only' }
  const original = { entry_date: '2025-07-08', description: 'اصلی', lines: [{ account_id: 'a', debit: 100, credit: 0 }, { account_id: 'b', debit: 0, credit: 100 }] }
  const id = queueJournalEntry(original)
  const row = () => getLocalDb().prepare('SELECT * FROM outbox_journal_entries WHERE local_id = ?').get(id) as Record<string, any>
  const created = row().created_at
  assert.deepEqual(await pushOutbox(config), { pushed: 0, failed: 1 }); assert.match(row().sync_error, /2025-07-08/)
  const opening = await beginJournalEdit(config, id); assert.equal(opening.state, 'editing')
  if (opening.state !== 'editing') throw new Error('no edit')
  assert.deepEqual(await pushOutbox(config), { pushed: 0, failed: 0 })
  cancelJournalEdit(id, opening.edit.lease); assert.equal(row().payload, JSON.stringify(original))
  const retry = await beginJournalEdit(config, id); if (retry.state !== 'editing') throw new Error('no edit')
  const fixed = { ...original, entry_date: '2026-09-28', description: 'اصلاح' }
  const result = await saveJournalEdit(config, id, retry.edit.lease, fixed)
  assert.equal(result.state, 'synced'); assert.equal(row().created_at, created); assert.equal(row().payload, JSON.stringify(fixed)); assert.equal(row().synced, 1)
  assert.equal(getLocalDb().prepare('SELECT count(*) AS count FROM outbox_journal_entries').get()?.count, 1)
  assert.deepEqual(posts.map((post) => post.key), [id, id]); assert.equal(registered.size, 1)
  await assert.rejects(beginJournalEdit(config, id), /ارسال شده/)

  const lost = queueJournalEntry({ ...fixed, description: 'پاسخ گم‌شده' }); loseReply = true
  assert.deepEqual(await pushOutbox(config), { pushed: 0, failed: 1 })
  assert.equal((await beginJournalEdit(config, lost)).state, 'synced'); assert.equal(registered.size, 2)
  loseReply = false; editable = false
  const legacy = queueJournalEntry(original)
  await assert.rejects(beginJournalEdit(config, legacy), /نسخهٔ قدیمی/)
  assert.equal(getLocalDb().prepare('SELECT payload FROM outbox_journal_entries WHERE local_id = ?').get(legacy)?.payload, JSON.stringify(original))
  clearJournalEditors(); getLocalDb().close(); server.close()
  console.log('PASS: native Electron SQLite same-row edit, lock/cancel/retry, acknowledgement loss and legacy ambiguity; isolated temporary data only')
  app.exit(0)
})().catch((error) => { console.error(error); server.close(); app.exit(1) })
