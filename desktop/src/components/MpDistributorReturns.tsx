import { Fragment, useCallback, useEffect, useState } from 'react'
import { Undo2, Check, Ban, RotateCw, ChevronDown, ChevronLeft } from 'lucide-react'
import {
  approveMpReturn, fetchMpDistributorReturns, rejectMpReturn,
  type MpReturn, type MpReturnStatus,
} from '../api'
import { SectionCard } from './SectionCard'
import { EmptyState } from './EmptyState'
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

/** مرجوعی‌های دریافتیِ پخش‌کننده — تأیید (پستِ دوطرفه‌ی برگشت) یا رد. */
export function MpDistributorReturns({ token }: { token: string }) {
  const [rows, setRows] = useState<MpReturn[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try { setRows(await fetchMpDistributorReturns(token)) }
    catch (e) { setError(errMsg(e)) }
  }, [token])
  useEffect(() => { void refresh() }, [refresh])
  const pg = usePagination(rows, 10)

  async function approve(r: MpReturn) {
    if (!window.confirm(`مرجوعی #${faNum(r.return_number)} تأیید شود؟ کالا به انبارِ شما برمی‌گردد و طلبتان کم می‌شود.`)) return
    setBusy(r.id); setError(null)
    try { await approveMpReturn(token, r.id); await refresh() }
    catch (e) { setError(errMsg(e)) } finally { setBusy(null) }
  }
  async function reject(r: MpReturn) {
    const note = window.prompt(`ردِ مرجوعی #${faNum(r.return_number)}\nدلیل (اختیاری):`)
    if (note === null) return
    setBusy(r.id); setError(null)
    try { await rejectMpReturn(token, r.id, note); await refresh() }
    catch (e) { setError(errMsg(e)) } finally { setBusy(null) }
  }

  return (
    <SectionCard
      icon={Undo2}
      title="مرجوعی‌ها"
      description="درخواست‌های مرجوعیِ فروشگاه‌ها. با تأیید، برگشتِ فروش در دفترِ شما و برگشتِ خرید در دفترِ فروشگاه ثبت می‌شود."
      actions={<button type="button" onClick={() => void refresh()}><RotateCw size={13} /> تازه‌سازی</button>}
    >
      {error && <div className="error">{error}</div>}
      {rows.length === 0 ? (
        <EmptyState icon={Undo2} text="مرجوعی‌ای ثبت نشده." />
      ) : (
        <div className="entity-table-wrap">
          <div className="table-scroll">
            <table className="entity-table cards-on-mobile">
              <thead><tr><th style={{ width: 24 }}></th><th>مرجوعی</th><th>فروشگاه</th><th>سفارش</th><th>مبلغ</th><th>وضعیت</th><th></th></tr></thead>
              <tbody>
                {pg.pageItems.map((r) => {
                  const open = expanded === r.id
                  const badge = RET_BADGE[r.status]
                  return (
                    <Fragment key={r.id}>
                      <tr className="invoice-row" onClick={() => setExpanded(open ? null : r.id)}>
                        <td className="card-hide">{open ? <ChevronDown size={14} /> : <ChevronLeft size={14} />}</td>
                        <td data-label="مرجوعی">#{faNum(r.return_number)}</td>
                        <td className="entity-name card-title" data-label="فروشگاه">{r.retailer_name}</td>
                        <td data-label="سفارش">#{faNum(r.order_number)}</td>
                        <td data-label="مبلغ" className="money-cell">{faMoney(r.total)}</td>
                        <td data-label="وضعیت"><span className={`status-badge ${badge.tone}`}>{badge.label}</span></td>
                        <td className="card-actions" onClick={(e) => e.stopPropagation()}>
                          {r.status === 'requested' && (
                            <div className="check-actions">
                              <button type="button" className="btn-primary" disabled={busy === r.id} onClick={() => void approve(r)}><Check size={13} /> تأیید</button>
                              <button type="button" className="icon-btn-danger" disabled={busy === r.id} onClick={() => void reject(r)}><Ban size={13} /> رد</button>
                            </div>
                          )}
                        </td>
                      </tr>
                      {open && (
                        <tr className="invoice-detail-row">
                          <td className="card-full" colSpan={7}>
                            <div className="invoice-detail">
                              {r.reason && <div className="invoice-detail-desc">دلیلِ فروشگاه: {r.reason}</div>}
                              {r.response_note && <div className="invoice-detail-desc">پاسخِ شما: {r.response_note}</div>}
                              <div className="invoice-detail-desc">تاریخ: {formatJalali(r.created_at)}</div>
                              <div className="table-scroll">
                                <table className="invoice-detail-table cards-on-mobile">
                                  <thead><tr><th>قلم</th><th>تعداد</th><th>قیمتِ واحد</th><th>جمع</th></tr></thead>
                                  <tbody>
                                    {r.lines.map((ln, i) => (
                                      <tr key={i}>
                                        <td className="entity-name" data-label="قلم">{ln.title}</td>
                                        <td data-label="تعداد">{faNum(ln.qty)}</td>
                                        <td data-label="قیمتِ واحد">{faMoney(ln.unit_price)}</td>
                                        <td data-label="جمع">{faMoney(ln.line_total)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pager page={pg.page} pageCount={pg.pageCount} onChange={pg.setPage} />
        </div>
      )}
    </SectionCard>
  )
}
