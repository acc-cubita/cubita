import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { Undo2, Send, RotateCw, ChevronDown, ChevronLeft, Info } from 'lucide-react'
import {
  fetchMpRetailerOrders, fetchMpRetailerReturns, requestMpReturn,
  type MpOrder, type MpReturn, type MpReturnStatus,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
import { NumberInput } from './NumberInput'
import { Pager, usePagination } from './Pager'
import { formatJalali } from '../lib/jalali'

const faMoney = (v: string | number) => Math.round(Number(v)).toLocaleString('fa-IR')
const faNum = (v: string | number) => Number(v).toLocaleString('fa-IR')
const errMsg = (e: unknown) => (e instanceof Error ? e.message : 'خطای ناشناخته')

const RET_BADGE: Record<MpReturnStatus, { label: string; tone: string }> = {
  requested: { label: 'در انتظارِ تأیید', tone: 'tone-warning' },
  approved: { label: 'تأییدشده', tone: 'tone-success' },
  rejected: { label: 'ردشده', tone: 'tone-danger' },
}

/** مرجوعیِ سمتِ فروشگاه — درخواست روی سفارشِ تأییدشده + فهرستِ مرجوعی‌های من. */
export function MpRetailerReturns({ token }: { token: string }) {
  const [orders, setOrders] = useState<MpOrder[]>([])
  const [returns, setReturns] = useState<MpReturn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [orderId, setOrderId] = useState('')
  const [qtys, setQtys] = useState<Record<string, string>>({})
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [os, rs] = await Promise.all([fetchMpRetailerOrders(token), fetchMpRetailerReturns(token)])
      setOrders(os)
      setReturns(rs)
    } catch (e) { setError(errMsg(e)) }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])

  const confirmedOrders = useMemo(() => orders.filter((o) => o.status === 'confirmed'), [orders])
  const selected = useMemo(() => confirmedOrders.find((o) => o.id === orderId) ?? null, [confirmedOrders, orderId])
  const pg = usePagination(returns, 10)

  async function submit() {
    setMsg(null)
    if (!selected) { setMsg('یک سفارشِ تأییدشده را انتخاب کنید.'); return }
    const lines = selected.lines
      .filter((ln) => ln.id && Number(qtys[ln.id]) > 0)
      .map((ln) => ({ order_line_id: ln.id as string, qty: Number(qtys[ln.id as string]) }))
    if (lines.length === 0) { setMsg('برای حداقل یک قلم مقدارِ مرجوعی وارد کنید.'); return }
    setBusy(true)
    try {
      await requestMpReturn(token, { order_id: selected.id, lines, reason: reason.trim() })
      setOrderId(''); setQtys({}); setReason('')
      setMsg('درخواستِ مرجوعی ثبت شد؛ منتظرِ تأییدِ پخش‌کننده بمانید.')
      await refresh()
    } catch (e) { setMsg(errMsg(e)) }
    finally { setBusy(false) }
  }

  return (
    <div className="workspace-split">
      <SectionCard icon={Undo2} title="درخواستِ مرجوعی" description="روی یک سفارشِ تأییدشده، اقلام و تعدادِ مرجوعی را مشخص کنید. با تأییدِ پخش‌کننده، کالا از انبارتان کم و بدهی‌تان اصلاح می‌شود.">
        {error && <div className="error">{error}</div>}
        <label>سفارش (تأییدشده)
          <select value={orderId} onChange={(e) => { setOrderId(e.target.value); setQtys({}) }}>
            <option value="">— انتخابِ سفارش —</option>
            {confirmedOrders.map((o) => (
              <option key={o.id} value={o.id}>سفارش #{faNum(o.order_number)} — {o.distributor_name} — {faMoney(o.total)} ریال</option>
            ))}
          </select>
        </label>

        {selected && (
          <>
            {selected.return_policy && (
              <div className="mp-policy-box"><Info size={14} /> <span>سیاستِ مرجوعی: {selected.return_policy}
                {selected.return_window_days > 0 ? ` (مهلت: ${faNum(selected.return_window_days)} روز)` : ''}</span></div>
            )}
            <div className="entity-table-wrap">
              <table className="entity-table">
                <thead><tr><th>قلم</th><th>سفارش‌شده</th><th>مرجوعی</th></tr></thead>
                <tbody>
                  {selected.lines.map((ln) => (
                    <tr key={ln.id ?? ln.title}>
                      <td className="entity-name">{ln.title}</td>
                      <td>{faNum(ln.qty)}</td>
                      <td style={{ maxWidth: 120 }}>
                        <NumberInput allowDecimal value={qtys[ln.id ?? ''] ?? ''} onChange={(v) => setQtys((q) => ({ ...q, [ln.id ?? '']: v }))} placeholder="۰" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <label>دلیلِ مرجوعی (اختیاری)
              <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="مثلاً کالای معیوب" />
            </label>
            <div className="invoice-form-footer">
              <button type="button" className="btn-primary" disabled={busy} onClick={() => void submit()}><Send size={14} /> ثبتِ درخواستِ مرجوعی</button>
            </div>
          </>
        )}
        {msg && <div className="hint">{msg}</div>}
      </SectionCard>

      <SectionCard icon={Undo2} title="مرجوعی‌های من" description={`${faNum(returns.length)} مرجوعی`}
        actions={<button type="button" onClick={() => void refresh()}><RotateCw size={13} /> تازه‌سازی</button>}>
        {returns.length === 0 ? (
          <EmptyState icon={Undo2} text="هنوز مرجوعی‌ای ثبت نکرده‌اید." />
        ) : (
          <div className="entity-table-wrap">
            <table className="entity-table cards-on-mobile">
              <thead><tr><th style={{ width: 24 }}></th><th>مرجوعی</th><th>پخش‌کننده</th><th>مبلغ</th><th>وضعیت</th></tr></thead>
              <tbody>
                {pg.pageItems.map((r) => {
                  const open = expanded === r.id
                  const badge = RET_BADGE[r.status]
                  return (
                    <Fragment key={r.id}>
                      <tr className="invoice-row" onClick={() => setExpanded(open ? null : r.id)}>
                        <td className="card-hide">{open ? <ChevronDown size={14} /> : <ChevronLeft size={14} />}</td>
                        <td data-label="مرجوعی">#{faNum(r.return_number)}</td>
                        <td className="entity-name card-title" data-label="پخش‌کننده">{r.distributor_name}</td>
                        <td data-label="مبلغ" className="money-cell">{faMoney(r.total)}</td>
                        <td data-label="وضعیت"><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
                      </tr>
                      {open && (
                        <tr className="invoice-detail-row">
                          <td className="card-full" colSpan={5}>
                            <div className="invoice-detail">
                              {r.reason && <div className="invoice-detail-desc">دلیل: {r.reason}</div>}
                              {r.response_note && <div className="invoice-detail-desc">پاسخِ پخش‌کننده: {r.response_note}</div>}
                              <div className="invoice-detail-desc">سفارش #{faNum(r.order_number)} · {formatJalali(r.created_at)}</div>
                              <table className="invoice-detail-table">
                                <thead><tr><th>قلم</th><th>تعداد</th><th>جمع</th></tr></thead>
                                <tbody>
                                  {r.lines.map((ln, i) => (
                                    <tr key={i}><td className="entity-name">{ln.title}</td><td>{faNum(ln.qty)}</td><td>{faMoney(ln.line_total)}</td></tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
            <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
          </div>
        )}
      </SectionCard>
    </div>
  )
}
