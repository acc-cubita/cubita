import { useEffect, useRef, useState } from 'react'
import { ScanLine, Upload, Wand2, Link2, Unlink } from 'lucide-react'
import type { BankAccountCache } from '../electron.d'
import {
  autoMatchStatement,
  fetchReconciliationSummary,
  fetchStatementLines,
  importStatementLines,
  matchStatementLine,
  unmatchStatementLine,
  type BankStatementLineRecord,
  type ReconciliationSummary,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { formatJalali } from '../lib/jalali'

function parseStatementCsv(text: string): { line_date: string; amount: number; description: string }[] {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)

  const result: { line_date: string; amount: number; description: string }[] = []
  for (const row of rows) {
    const cols = row.split(',').map((c) => c.trim().replace(/^"|"$/g, ''))
    if (cols.length < 2) continue
    const [dateRaw, amountRaw, ...descParts] = cols
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateRaw)) continue // ردیف هدر یا نامعتبر را رد کن
    const amount = Number(amountRaw)
    if (!Number.isFinite(amount) || amount === 0) continue
    result.push({ line_date: dateRaw, amount, description: descParts.join(',') })
  }
  return result
}

export function ReconciliationPanel({ token, bankAccounts }: { token: string; bankAccounts: BankAccountCache[] }) {
  const [bankAccountId, setBankAccountId] = useState('')
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null)
  const [matchedLines, setMatchedLines] = useState<BankStatementLineRecord[]>([])
  const [selectedLineId, setSelectedLineId] = useState('')
  const [selectedTxnId, setSelectedTxnId] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const effectiveBankAccountId = bankAccountId || bankAccounts[0]?.id || ''

  async function refresh() {
    if (!effectiveBankAccountId) return
    try {
      const [summaryRes, allLines] = await Promise.all([
        fetchReconciliationSummary(token, effectiveBankAccountId),
        fetchStatementLines(token, effectiveBankAccountId),
      ])
      setSummary(summaryRes)
      setMatchedLines(allLines.filter((l) => l.matched_transaction_id !== null))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  useEffect(() => {
    void refresh()
    setSelectedLineId('')
    setSelectedTxnId('')
  }, [effectiveBankAccountId])

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !effectiveBankAccountId) return
    setMessage(null)
    try {
      const text = await file.text()
      const lines = parseStatementCsv(text)
      if (lines.length === 0) {
        setMessage('هیچ ردیف معتبری در فایل پیدا نشد. فرمت مورد انتظار: تاریخ (YYYY-MM-DD)، مبلغ، شرح')
        return
      }
      await importStatementLines(token, effectiveBankAccountId, lines)
      setMessage(`${lines.length.toLocaleString('fa-IR')} ردیف از صورت‌حساب وارد شد.`)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleAutoMatch() {
    if (!effectiveBankAccountId) return
    setMessage(null)
    try {
      const res = await autoMatchStatement(token, effectiveBankAccountId)
      setMessage(`${res.matched_count.toLocaleString('fa-IR')} ردیف به‌طور خودکار تطبیق داده شد.`)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleManualMatch() {
    if (!selectedLineId || !selectedTxnId) {
      setMessage('یک ردیف صورت‌حساب و یک تراکنش سیستم را انتخاب کنید.')
      return
    }
    setMessage(null)
    try {
      await matchStatementLine(token, selectedLineId, selectedTxnId)
      setSelectedLineId('')
      setSelectedTxnId('')
      setMessage('تطبیق دستی انجام شد.')
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  async function handleUnmatch(lineId: string) {
    setMessage(null)
    try {
      await unmatchStatementLine(token, lineId)
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'خطای ناشناخته')
    }
  }

  return (
    <SectionCard
      icon={ScanLine}
      title="تطبیق بانکی"
      description="صورت‌حساب رسمی بانک را وارد کنید (فایل CSV با ستون‌های تاریخ، مبلغ، شرح) و با تراکنش‌های ثبت‌شده در سیستم تطبیق دهید."
      actions={
        <label className="btn-file">
          <Upload size={13} /> وارد کردن صورت‌حساب (CSV)
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" onChange={(e) => void handleFileChange(e)} hidden />
        </label>
      }
    >
      {bankAccounts.length === 0 ? (
        <p className="hint">برای تطبیق بانکی، ابتدا یک‌بار «هم‌گام‌سازی» کنید تا حساب‌های بانکی در دسترس باشند.</p>
      ) : (
        <>
          <label>
            حساب بانکی
            <select value={effectiveBankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
              {bankAccounts.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>

          {summary && (
            <>
              <div className="stat-grid" style={{ marginTop: 12, marginBottom: 12 }}>
                <div className="stat-card">
                  <div className="stat-card-top">
                    <span className="stat-card-label">جمع صورت‌حساب واردشده</span>
                  </div>
                  <div className="stat-card-value">{Number(summary.statement_total).toLocaleString('fa-IR')}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-card-top">
                    <span className="stat-card-label">ردیف‌های تطبیق‌شده</span>
                  </div>
                  <div className="stat-card-value">{summary.matched_count.toLocaleString('fa-IR')}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-card-top">
                    <span className="stat-card-label">تطبیق‌نشده</span>
                  </div>
                  <div className="stat-card-value">{summary.unmatched_statement_lines.length.toLocaleString('fa-IR')}</div>
                </div>
              </div>

              <div className="invoice-form-footer" style={{ marginBottom: 12 }}>
                <button type="button" onClick={() => void handleAutoMatch()}>
                  <Wand2 size={13} /> تطبیق خودکار
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={!selectedLineId || !selectedTxnId}
                  onClick={() => void handleManualMatch()}
                >
                  <Link2 size={13} /> تطبیق دستی ردیف انتخابی
                </button>
              </div>
              {message && <div className="hint">{message}</div>}

              {summary.unmatched_statement_lines.length === 0 && summary.unreconciled_system_transactions.length === 0 ? (
                <EmptyState icon={ScanLine} text="همه‌چیز تطبیق‌شده — موردی برای بررسی نیست." />
              ) : (
                <div className="overview-columns">
                  <div>
                    <h3>ردیف‌های صورت‌حساب بدون تطبیق</h3>
                    <div className="table-scroll">
                    <table className="cards-on-mobile">
                      <thead>
                        <tr>
                          <th></th>
                          <th>تاریخ</th>
                          <th>مبلغ</th>
                          <th>شرح</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.unmatched_statement_lines.map((line) => (
                          <tr key={line.id}>
                            <td data-label="انتخاب">
                              <input
                                type="radio"
                                name="stmt-line"
                                checked={selectedLineId === line.id}
                                onChange={() => setSelectedLineId(line.id)}
                              />
                            </td>
                            <td data-label="تاریخ">{formatJalali(line.line_date)}</td>
                            <td data-label="مبلغ">{Number(line.amount).toLocaleString('fa-IR')}</td>
                            <td className="card-title" data-label="شرح">{line.description}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  </div>

                  <div>
                    <h3>تراکنش‌های سیستم بدون تطبیق</h3>
                    <div className="table-scroll">
                    <table className="cards-on-mobile">
                      <thead>
                        <tr>
                          <th></th>
                          <th>تاریخ</th>
                          <th>مبلغ</th>
                          <th>شرح</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.unreconciled_system_transactions.map((txn) => (
                          <tr key={txn.id}>
                            <td data-label="انتخاب">
                              <input
                                type="radio"
                                name="sys-txn"
                                checked={selectedTxnId === txn.id}
                                onChange={() => setSelectedTxnId(txn.id)}
                              />
                            </td>
                            <td data-label="تاریخ">{formatJalali(txn.transaction_date)}</td>
                            <td data-label="مبلغ">{Number(txn.amount).toLocaleString('fa-IR')}</td>
                            <td className="card-title" data-label="شرح">{txn.description}</td>
                            <td className="card-hide"></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  </div>
                </div>
              )}

              {matchedLines.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16 }}>ردیف‌های تطبیق‌شده</h3>
                  <div className="table-scroll">
                  <table className="cards-on-mobile">
                    <thead>
                      <tr>
                        <th>تاریخ</th>
                        <th>مبلغ</th>
                        <th>شرح</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {matchedLines.map((line) => (
                        <tr key={line.id}>
                          <td data-label="تاریخ">{formatJalali(line.line_date)}</td>
                          <td data-label="مبلغ">{Number(line.amount).toLocaleString('fa-IR')}</td>
                          <td className="card-title" data-label="شرح">{line.description}</td>
                          <td className="card-actions">
                            <button
                              type="button"
                              className="icon-btn-danger"
                              onClick={() => void handleUnmatch(line.id)}
                              aria-label="لغو تطبیق"
                            >
                              <Unlink size={14} /> لغو تطبیق
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </>
              )}
            </>
          )}
        </>
      )}
    </SectionCard>
  )
}
