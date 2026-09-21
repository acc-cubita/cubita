/**
 * کارتابلِ حسابرسی — صفِ درخواست‌های همه‌ی کسب‌وکارها.
 *
 * صف‌محور است نه حساب‌محور، و به همین دلیل صفحه‌ی مستقلی است و تبی در «مدیریت
 * اکانت‌ها» نیست: کارِ روزانه‌ی اینجا «کدام درخواست منتظرِ من است» است، نه
 * «این مشتری چه وضعی دارد».
 */
import { useMemo, useState } from 'react'
import { ClipboardCheck, RefreshCw } from 'lucide-react'

import {
  approveEngagement,
  assignAuditor,
  closeEngagement,
  extendEngagement,
  fetchEngagements,
  rejectEngagement,
  runEngagement,
  type StaffEngagement,
} from '../api'
import { formatJalali } from '../lib/jalali'
import {
  AsyncBlock,
  Card,
  Chip,
  Dialog,
  Field,
  FieldGrid,
  Note,
  PageHeader,
  Stat,
  TableScroll,
  faInt,
  useAsync,
} from '../ui/kit'

const BUCKETS: { key: string; label: string; statuses: string[]; empty: string }[] = [
  {
    key: 'waiting',
    label: 'منتظرِ تصمیم',
    statuses: ['requested'],
    empty: 'درخواستِ تازه‌ای نیست.',
  },
  {
    key: 'open',
    label: 'پرونده‌های باز',
    statuses: ['approved', 'active'],
    empty: 'پرونده‌ی بازی نیست.',
  },
  {
    key: 'done',
    label: 'بسته و ردشده',
    statuses: ['closed', 'rejected'],
    empty: 'سابقه‌ای نیست.',
  },
]

function statusChip(s: string) {
  const map: Record<string, { text: string; tone: 'ok' | 'warn' | 'bad' | 'mute' }> = {
    requested: { text: 'درخواست‌شده', tone: 'warn' },
    approved: { text: 'تأییدشده', tone: 'ok' },
    active: { text: 'در جریان', tone: 'ok' },
    closed: { text: 'بسته', tone: 'mute' },
    rejected: { text: 'ردشده', tone: 'bad' },
  }
  const v = map[s] ?? { text: s, tone: 'mute' as const }
  return <Chip text={v.text} tone={v.tone} />
}

function daysLeft(iso: string | null): number | null {
  if (!iso) return null
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000)
}

export default function AssurancePage({
  token,
  onUnauthorized,
}: {
  token: string
  onUnauthorized: (e: unknown) => void
}) {
  const { data, loading, error, reload } = useAsync(() => fetchEngagements(token), [token])
  const [msg, setMsg] = useState<{ kind: 'ok' | 'bad'; text: string } | null>(null)
  const [approving, setApproving] = useState<StaffEngagement | null>(null)

  const rows = data ?? []

  const kpis = useMemo(
    () => ({
      waiting: rows.filter((r) => r.status === 'requested').length,
      open: rows.filter((r) => r.status === 'approved' || r.status === 'active').length,
      expiring: rows.filter((r) => {
        const d = daysLeft(r.access_expires_at)
        return r.status === 'active' && d != null && d <= 7
      }).length,
    }),
    [rows],
  )

  async function act(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn()
      setMsg({ kind: 'ok', text: ok })
      reload()
    } catch (e) {
      onUnauthorized(e)
      setMsg({ kind: 'bad', text: e instanceof Error ? e.message : 'انجام نشد' })
    }
  }

  return (
    <>
      <PageHeader
        icon={ClipboardCheck}
        title="کارتابل حسابرسی"
        description="درخواست‌های حسابرسیِ مشتریان، گمارشِ حسابرس و مدیریتِ دسترسی."
        actions={
          <button type="button" className="ad-btn" onClick={reload}>
            <RefreshCw size={15} /> تازه‌سازی
          </button>
        }
      />

      <section className="ad-stats">
        <Stat label="منتظرِ تصمیم" value={faInt(kpis.waiting)} tone={kpis.waiting ? 'warn' : 'ok'} />
        <Stat label="پرونده‌های باز" value={faInt(kpis.open)} />
        <Stat label="دسترسی تا ۷ روز" value={faInt(kpis.expiring)} tone="warn" />
      </section>

      <Note msg={msg} />

      <AsyncBlock loading={loading} error={error}>
        {BUCKETS.map((bucket) => {
          const list = rows.filter((r) => bucket.statuses.includes(r.status))
          return (
            <Card
              key={bucket.key}
              title={bucket.label}
              actions={<span className="ad-count">{faInt(list.length)} مورد</span>}
            >
              {list.length === 0 ? (
                <p className="ad-empty">{bucket.empty}</p>
              ) : (
                <TableScroll>
                  <table className="cards-on-mobile">
                    <thead>
                      <tr>
                        <th>کسب‌وکار</th>
                        <th>دوره</th>
                        <th>وضعیت</th>
                        <th>حسابرس</th>
                        <th>نمره</th>
                        <th>مهلتِ دسترسی</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {list.map((e) => {
                        const left = daysLeft(e.access_expires_at)
                        return (
                          <tr key={e.id}>
                            <td className="card-title" data-label="کسب‌وکار">
                              {e.tenant_name ?? '—'}
                              <span className="ad-sub" dir="ltr">
                                {e.owner_email ?? '—'}
                              </span>
                            </td>
                            <td data-label="دوره">
                              {formatJalali(e.period_from)} تا {formatJalali(e.period_to)}
                            </td>
                            <td data-label="وضعیت">{statusChip(e.status)}</td>
                            <td data-label="حسابرس">
                              {e.auditor_name ?? '—'}
                              {e.auditor_email ? (
                                <span className="ad-sub" dir="ltr">
                                  {e.auditor_email}
                                </span>
                              ) : null}
                            </td>
                            <td className="num" data-label="نمره">
                              {e.last_score == null ? '—' : faInt(e.last_score)}
                            </td>
                            <td data-label="مهلتِ دسترسی">
                              {left == null ? '—' : `${faInt(left)} روز`}
                            </td>
                            <td className="card-actions">
                              {e.status === 'requested' ? (
                                <>
                                  <button
                                    type="button"
                                    className="ad-btn small primary"
                                    onClick={() => setApproving(e)}
                                  >
                                    تأیید
                                  </button>
                                  <button
                                    type="button"
                                    className="ad-btn small"
                                    onClick={() => {
                                      const reason = window.prompt('دلیلِ رد:')
                                      if (reason) {
                                        act(
                                          () => rejectEngagement(token, e.id, reason),
                                          'درخواست رد شد.',
                                        )
                                      }
                                    }}
                                  >
                                    رد
                                  </button>
                                </>
                              ) : null}

                              {e.status === 'approved' || e.status === 'active' ? (
                                <>
                                  <button
                                    type="button"
                                    className="ad-btn small"
                                    onClick={() =>
                                      act(() => runEngagement(token, e.id), 'بررسی دوباره اجرا شد.')
                                    }
                                  >
                                    اجرای بررسی
                                  </button>
                                  <button
                                    type="button"
                                    className="ad-btn small"
                                    onClick={() =>
                                      act(
                                        () => extendEngagement(token, e.id, 30),
                                        'دسترسیِ حسابرس ۳۰ روز تمدید شد.',
                                      )
                                    }
                                  >
                                    + ۳۰ روز
                                  </button>
                                  <button
                                    type="button"
                                    className="ad-btn small"
                                    onClick={() => {
                                      const email = window.prompt('ایمیلِ حسابرسِ تازه:')
                                      if (email) {
                                        act(
                                          () => assignAuditor(token, e.id, email),
                                          'حسابرسِ تازه گماشته شد.',
                                        )
                                      }
                                    }}
                                  >
                                    تعویضِ حسابرس
                                  </button>
                                  <button
                                    type="button"
                                    className="ad-btn small"
                                    onClick={() => {
                                      const note = window.prompt('یادداشتِ بستنِ پرونده:') ?? ''
                                      act(
                                        () => closeEngagement(token, e.id, note),
                                        'پرونده بسته و دسترسیِ حسابرس باطل شد.',
                                      )
                                    }}
                                  >
                                    بستنِ پرونده
                                  </button>
                                </>
                              ) : null}

                              {e.status === 'rejected' && e.reject_reason ? (
                                <span className="ad-sub">{e.reject_reason}</span>
                              ) : null}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </TableScroll>
              )}
            </Card>
          )
        })}
      </AsyncBlock>

      {approving ? (
        <ApproveDialog
          engagement={approving}
          onClose={() => setApproving(null)}
          onSubmit={(email, days) =>
            act(
              () => approveEngagement(token, approving.id, { auditor_email: email, days }),
              `حسابرسیِ «${approving.tenant_name}» تأیید شد و اولین بررسی اجرا شد.`,
            ).then(() => setApproving(null))
          }
        />
      ) : null}
    </>
  )
}

function ApproveDialog({
  engagement,
  onClose,
  onSubmit,
}: {
  engagement: StaffEngagement
  onClose: () => void
  onSubmit: (email: string, days: number) => void
}) {
  const [email, setEmail] = useState('')
  const [days, setDays] = useState(90)

  return (
    <Dialog
      title={`تأییدِ حسابرسیِ «${engagement.tenant_name}»`}
      onClose={onClose}
      footer={
        <button
          type="button"
          className="ad-btn primary"
          disabled={!email.trim()}
          onClick={() => onSubmit(email.trim(), days)}
        >
          تأیید و اجرای بررسی
        </button>
      }
    >
      <p className="ad-field-hint">
        با تأیید، دسترسیِ موقتِ فقط‌خواندنی برای حسابرس ساخته می‌شود و اولین بررسی
        همان لحظه اجرا می‌شود. حسابرس از سوییچرِ کسب‌وکارِ خودش وارد می‌شود.
      </p>
      <FieldGrid>
        <Field label="ایمیلِ حسابرس" hint="باید کاربرِ موجودِ کوبیتا باشد">
          <input type="email" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="مهلتِ دسترسی (روز)">
          <input
            type="number"
            dir="ltr"
            value={days}
            onChange={(e) => setDays(Number(e.target.value) || 0)}
          />
        </Field>
      </FieldGrid>
    </Dialog>
  )
}
