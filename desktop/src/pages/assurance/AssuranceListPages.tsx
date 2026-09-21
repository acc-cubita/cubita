import { useMemo, useState } from 'react'
import { AlertTriangle, ClipboardCheck, History, ListChecks } from 'lucide-react'

import { SectionCard } from '../../components/SectionCard'
import { SearchSelect } from '../../components/SearchSelect'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { KardexDrawer } from '../../components/KardexDrawer'
import { CountBadge, FormField, ListToolbar, RowAction, SearchField } from '../../components/form/FormKit'
import { formatJalali } from '../../lib/jalali'
import {
  fetchAssuranceFindings,
  fetchAssuranceRuns,
  type AssuranceFindingRecord,
  type AssuranceRunRecord,
} from '../../api'
import { AsyncBlock, OpsPage, faInt, useAsync } from '../accounting/kit'

const fa = (v: number | string | null | undefined) =>
  v === null || v === undefined ? '—' : Number(v).toLocaleString('fa-IR')

const TRIGGER_LABELS: Record<string, string> = {
  approval: 'هنگامِ تأیید',
  manual: 'درخواستِ کاربر',
  staff: 'پشتیبانی',
}

const GRADE_LABELS: Record<string, string> = {
  healthy: 'سالم',
  warning: 'نیازمندِ رسیدگی',
  critical: 'بحرانی',
}

const GRADE_TONE: Record<string, string> = {
  healthy: 'tone-success',
  warning: 'tone-warning',
  critical: 'tone-danger',
}

/**
 * «یافته‌های حسابرسی» — ردیف‌به‌ردیفِ یک بررسی، با drill-down.
 *
 * سه کشوی موجود بازاستفاده می‌شوند (سند، دفترِ حساب، کاردکس) — همان کاری که
 * صفحه‌ی «بررسی یکپارچگی» می‌کند. ساختنِ کشوی چهارم یعنی دو نمای یک داده.
 */
export function AssuranceFindingListPage({ token }: { token: string }) {
  const runs = useAsync<AssuranceRunRecord[]>(() => fetchAssuranceRuns(token), [token])
  const [runId, setRunId] = useState('')
  const [checkKey, setCheckKey] = useState('')
  const [severity, setSeverity] = useState('')
  const [query, setQuery] = useState('')

  //: بی‌انتخابِ کاربر، تازه‌ترین بررسی — همان چیزی که آدم اول می‌خواهد ببیند.
  const activeRun = runId || runs.data?.[0]?.id || ''
  const current = runs.data?.find((r) => r.id === activeRun) ?? null

  const findings = useAsync<AssuranceFindingRecord[]>(
    () =>
      activeRun
        ? fetchAssuranceFindings(token, activeRun, {
            check_key: checkKey || undefined,
            severity: severity || undefined,
          })
        : Promise.resolve([]),
    [token, activeRun, checkKey, severity],
  )

  const rows = useMemo(() => {
    const all = findings.data ?? []
    const needle = query.trim()
    if (!needle) return all
    return all.filter((row) => `${row.label} ${row.detail}`.includes(needle))
  }, [findings.data, query])

  const titles = useMemo(() => {
    const map = new Map<string, string>()
    for (const row of current?.summary ?? []) map.set(row.key, row.title)
    return map
  }, [current])

  const [entryId, setEntryId] = useState<string | null>(null)
  //: کشوهای دفترِ حساب و کاردکس کد و نام می‌خواهند و یافته فقط شناسه دارد؛ همان
  //: قراردادِ برچسبِ «کد — نام» که صفحه‌ی «بررسی یکپارچگی» هم از آن استفاده می‌کند.
  //: اگر شکلِ برچسب روزی عوض شود، بدترین حالت یک عنوانِ خام است نه خطا.
  const [account, setAccount] = useState<{ id: string; code: string; name: string } | null>(null)
  const [item, setItem] = useState<{ id: string; sku: string; name: string } | null>(null)

  const split = (row: AssuranceFindingRecord) => {
    const [head, ...rest] = row.label.split(' — ')
    return { head, tail: rest.join(' — ') || head }
  }

  return (
    <OpsPage
      canvas
      icon={ListChecks}
      title="یافته‌های حسابرسی"
      description="هر ردیفی که بررسی‌های خودکار در دفترِ شما پیدا کرده‌اند."
    >
      <SectionCard
        icon={ListChecks}
        title="یافته‌ها"
        badge={<CountBadge accent>{faInt(rows.length)} ردیف</CountBadge>}
        description={
          current
            ? `بررسیِ شماره‌ی ${faInt(current.number)} — ${formatJalali(current.ran_at.slice(0, 10))}`
            : undefined
        }
      >
        <ListToolbar>
          <SearchField value={query} onChange={setQuery} placeholder="جست‌وجو در یافته‌ها" />
          <FormField label="بررسی">
            {(id) => (
              <SearchSelect id={id} value={activeRun} onChange={(e) => setRunId(e.target.value)}>
                {(runs.data ?? []).map((run) => (
                  <option key={run.id} value={run.id}>
                    شماره‌ی {faInt(run.number)} — {formatJalali(run.ran_at.slice(0, 10))}
                  </option>
                ))}
              </SearchSelect>
            )}
          </FormField>
          <FormField label="نوعِ بررسی">
            {(id) => (
              <SearchSelect id={id} value={checkKey} onChange={(e) => setCheckKey(e.target.value)}>
                <option value="">همه‌ی بررسی‌ها</option>
                {(current?.summary ?? [])
                  .filter((row) => row.count > 0)
                  .map((row) => (
                    <option key={row.key} value={row.key}>
                      {row.title}
                    </option>
                  ))}
              </SearchSelect>
            )}
          </FormField>
          <FormField label="شدت">
            {(id) => (
              <SearchSelect id={id} value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="">همه</option>
                <option value="error">خطا</option>
                <option value="warning">هشدار</option>
              </SearchSelect>
            )}
          </FormField>
        </ListToolbar>

        <AsyncBlock
          loading={runs.loading || findings.loading}
          error={runs.error ?? findings.error}
          empty={rows.length === 0}
          emptyText="یافته‌ای با این شرایط نیست."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th>بررسی</th>
                  <th>مورد</th>
                  <th>توضیح</th>
                  <th className="num ef-col-min">مبلغ</th>
                  <th className="ef-col-min">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td data-label="بررسی">
                      <span
                        className={`status-badge ${row.severity === 'error' ? 'tone-danger' : 'tone-warning'}`}
                      >
                        {titles.get(row.check_key) ?? row.check_key}
                      </span>
                    </td>
                    <td className="card-title ef-cell-title" data-label="مورد">
                      {row.label}
                    </td>
                    <td className="card-wide" data-label="توضیح">
                      {row.detail}
                    </td>
                    <td className="num" data-label="مبلغ">
                      {Number(row.difference) ? fa(row.difference) : '—'}
                    </td>
                    <td className="card-actions ef-col-min">
                      <div className="row-actions ef-row-actions">
                        {row.entry_id && (
                          <RowAction
                            icon={ClipboardCheck}
                            label="دیدنِ سند"
                            onClick={() => setEntryId(row.entry_id)}
                          />
                        )}
                        {row.account_id && (
                          <RowAction
                            icon={History}
                            label="دفترِ حساب"
                            onClick={() => {
                              const { head, tail } = split(row)
                              setAccount({ id: row.account_id as string, code: head, name: tail })
                            }}
                          />
                        )}
                        {row.item_id && (
                          <RowAction
                            icon={AlertTriangle}
                            label="کاردکسِ کالا"
                            onClick={() => {
                              const { head, tail } = split(row)
                              setItem({ id: row.item_id as string, sku: head, name: tail })
                            }}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>

      {entryId && <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />}
      {account && (
        <AccountLedgerDrawer token={token} account={account} onClose={() => setAccount(null)} />
      )}
      {item && <KardexDrawer token={token} item={item} onClose={() => setItem(null)} />}
    </OpsPage>
  )
}

/** «تاریخچه بررسی‌ها» — دفترِ اجراها، تا بشود دید نمره در طولِ زمان چه کرد. */
export function AssuranceRunListPage({ token }: { token: string }) {
  const runs = useAsync<AssuranceRunRecord[]>(() => fetchAssuranceRuns(token), [token])
  const rows = runs.data ?? []

  return (
    <OpsPage
      canvas
      icon={History}
      title="تاریخچه بررسی‌ها"
      description="هر بار که بررسی‌های خودکار اجرا شده‌اند، با نمره‌ی همان لحظه."
    >
      <SectionCard
        icon={History}
        title="اجراها"
        badge={<CountBadge accent>{faInt(rows.length)} بررسی</CountBadge>}
        description="هر اجرا عکسی از دفتر در تاریخِ خودش است و بعداً عوض نمی‌شود."
      >
        <AsyncBlock
          loading={runs.loading}
          error={runs.error}
          empty={rows.length === 0}
          emptyText="هنوز بررسی‌ای اجرا نشده است."
        >
          <div className="table-scroll ef-table-wrap">
            <table className="cards-on-mobile ef-table">
              <thead>
                <tr>
                  <th className="ef-col-min">شماره</th>
                  <th>تاریخ</th>
                  <th>اجرا به‌درخواستِ</th>
                  <th className="num ef-col-min">نمره</th>
                  <th className="ef-col-min">درجه</th>
                  <th className="num ef-col-min">خطا</th>
                  <th className="num ef-col-min">هشدار</th>
                  <th className="num ef-col-min">یافته</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((run) => (
                  <tr key={run.id}>
                    <td className="card-title ef-cell-title" data-label="شماره">
                      {faInt(run.number)}
                    </td>
                    <td data-label="تاریخ">{formatJalali(run.ran_at.slice(0, 10))}</td>
                    <td data-label="اجرا به‌درخواستِ">{TRIGGER_LABELS[run.trigger] ?? run.trigger}</td>
                    <td className="num" data-label="نمره">
                      {fa(run.score)}
                    </td>
                    <td data-label="درجه">
                      <span className={`status-badge ${GRADE_TONE[run.grade] ?? 'tone-info'}`}>
                        {GRADE_LABELS[run.grade] ?? run.grade}
                      </span>
                    </td>
                    <td className="num" data-label="خطا">
                      {run.error_count ? faInt(run.error_count) : '—'}
                    </td>
                    <td className="num" data-label="هشدار">
                      {run.warning_count ? faInt(run.warning_count) : '—'}
                    </td>
                    <td className="num" data-label="یافته">
                      {faInt(run.finding_count)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AsyncBlock>
      </SectionCard>
    </OpsPage>
  )
}
