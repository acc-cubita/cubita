import { useCallback, useState } from 'react'
import { CheckCircle2, ShieldCheck, TriangleAlert, XCircle } from 'lucide-react'
import {
  fetchIntegrityReport,
  type IntegrityCheck,
  type IntegrityReport,
  type IntegrityRow,
  type ReportFilters,
} from '../../api'
import { AccountLedgerDrawer } from '../../components/AccountLedgerDrawer'
import { JournalEntryDrawer } from '../../components/JournalEntryDrawer'
import { ReportFilterBar } from '../../components/ReportFilterBar'
import { SavedViewBar } from '../../components/SavedViewBar'
import { SectionCard } from '../../components/SectionCard'
import { AsyncBlock, Metric, OpsPage, RangeBar, fa, faAmount, faInt, useAsync, useRange } from './kit'

/**
 * بررسیِ یکپارچگیِ دفتر — §۲۷.
 *
 * **گزارش است، نه گارد.** هیچ‌چیز این‌جا مسدود نمی‌شود؛ همان تصمیمی که «خلافِ
 * ماهیت» گرفت. سندِ نامتوازن را نمی‌شود با بستنِ راهِ ثبت درست کرد — آن سند از
 * قبل ثبت شده است. کاری که این‌جا می‌شود پیدا کردن و **بردنِ کاربر به خودِ سند**
 * است؛ گزارشی که بگوید «اشکالی هست» ولی نگوید کجا، کارِ حسابدار را بیشتر می‌کند.
 *
 * چهار بررسی از پنج بررسی خطا هستند و یکی هشدار. هشدار نتیجه را قرمز نمی‌کند،
 * چون سندِ بی‌ردیف هیچ مبلغی را جابه‌جا نکرده — دیده می‌شود ولی دفتر را ناسالم
 * نمی‌کند.
 */
export function IntegrityPage({ token }: { token: string }) {
  const range = useRange('year')
  const [filters, setFilters] = useState<ReportFilters>({})
  const [entryId, setEntryId] = useState<string | null>(null)
  const [drill, setDrill] = useState<{ id: string; code: string; name: string } | null>(null)

  const scope: ReportFilters = { ...filters, dateFrom: range.from, dateTo: range.to }
  const report = useAsync<IntegrityReport>(
    () => fetchIntegrityReport(token, scope),
    [token, range.from, range.to, JSON.stringify(filters)],
  )
  const data = report.data

  //: ردیف‌های بررسی فقط کد و نام را متن دارند؛ برای بازکردنِ دفتر باید همان دو را
  //: از خودِ برچسب جدا کرد. سرور شناسه را می‌دهد، پس این تجزیه فقط برای نمایشِ
  //: کشو است و اگر شکلِ برچسب عوض شود، بدترین حالت یک عنوانِ خام است نه خطا.
  const openAccount = useCallback((row: IntegrityRow) => {
    if (!row.account_id) return
    const [code, ...rest] = row.label.split(' — ')
    setDrill({ id: row.account_id, code, name: rest.join(' — ') || code })
  }, [])

  return (
    <OpsPage
      icon={ShieldCheck}
      title="بررسی یکپارچگی"
      description="دفتر را از چند زاویه می‌سنجد و ناسازگاری‌ها را نشان می‌دهد. چیزی مسدود نمی‌شود؛ تصمیم با شماست."
      head={
        <div>
          <RangeBar
            range={range}
            extra={<ReportFilterBar token={token} filters={filters} onChange={setFilters} />}
          />
          <SavedViewBar
            token={token}
            viewKey="accounting.integrity"
            filters={filters}
            range={range}
            setFilters={setFilters}
          />
          {data && (
            <div className="cc-summary">
              <Metric
                icon={data.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                label="نتیجه"
                value={data.ok ? 'سالم' : 'نیازمندِ رسیدگی'}
                tone={data.ok ? 'in' : 'out'}
              />
              <Metric icon={<ShieldCheck size={14} />} label="جمعِ بدهکار" value={fa(data.total_debit)} />
              <Metric icon={<ShieldCheck size={14} />} label="جمعِ بستانکار" value={fa(data.total_credit)} />
              <Metric
                icon={<TriangleAlert size={14} />}
                label="اختلاف"
                value={faAmount(data.difference)}
                tone={Number(data.difference) === 0 ? undefined : 'out'}
              />
            </div>
          )}
        </div>
      }
    >
      <AsyncBlock
        loading={report.loading}
        error={report.error}
        empty={!data}
        emptyText="بررسی هنوز اجرا نشده است."
      >
        {(data?.checks ?? []).map((check) => (
          <CheckCard key={check.key} check={check} onEntry={setEntryId} onAccount={openAccount} />
        ))}
      </AsyncBlock>

      {entryId && (
        <JournalEntryDrawer token={token} entryId={entryId} onClose={() => setEntryId(null)} />
      )}
      {drill && (
        //: کشوی دفتر همان دامنه‌ی بررسی را می‌گیرد، وگرنه کاربر عددی را باز
        //: می‌کرد و دفتری می‌دید که با آن نمی‌خواند.
        <AccountLedgerDrawer
          token={token}
          account={drill}
          filters={scope}
          onClose={() => setDrill(null)}
        />
      )}
    </OpsPage>
  )
}

function CheckCard({
  check,
  onEntry,
  onAccount,
}: {
  check: IntegrityCheck
  onEntry: (id: string) => void
  onAccount: (row: IntegrityRow) => void
}) {
  const bad = !check.ok
  return (
    <SectionCard
      icon={check.ok ? CheckCircle2 : check.severity === 'error' ? XCircle : TriangleAlert}
      title={check.title}
      description={check.description}
      actions={
        //: همان سه رنگِ وضعیتِ سند (دائم/موقت/باطل) دوباره به کار می‌روند — سالم،
        //: هشدار، خطا. رنگِ تازه ساختن یعنی کاربر باید زبانِ دومی یاد بگیرد.
        <span
          className={`acc-chip acc-chip--${
            !bad ? 'final' : check.severity === 'error' ? 'void' : 'draft'
          }`}
        >
          {check.ok ? 'بدونِ یافته' : `${faInt(check.count)} مورد`}
        </span>
      }
    >
      {check.ok ? (
        <p className="muted">این بررسی چیزی پیدا نکرد.</p>
      ) : (
        <div className="table-scroll">
          <table className="cards-on-mobile acc-table">
            <thead>
              <tr>
                <th>مورد</th>
                <th>توضیح</th>
                <th>بدهکار</th>
                <th>بستانکار</th>
                <th>اختلاف</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {check.rows.map((row, i) => (
                <tr key={`${check.key}-${row.entry_id ?? row.account_id ?? i}`}>
                  <td className="card-title" data-label="مورد">{row.label}</td>
                  <td className="card-wide" data-label="توضیح">{row.detail || '—'}</td>
                  <td className="num" data-label="بدهکار">{faAmount(row.debit)}</td>
                  <td className="num" data-label="بستانکار">{faAmount(row.credit)}</td>
                  <td className="num" data-label="اختلاف">{faAmount(row.difference)}</td>
                  <td className="card-actions">
                    {row.entry_id && (
                      <button type="button" onClick={() => onEntry(row.entry_id as string)}>
                        نمایشِ سند
                      </button>
                    )}
                    {row.account_id && (
                      <button type="button" onClick={() => onAccount(row)}>
                        دفترِ حساب
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {check.truncated && (
            <p className="muted">
              {`${faInt(check.rows.length)} مورد از ${faInt(check.count)} نشان داده شده؛ برای دیدنِ بقیه بازه یا فیلتر را محدودتر کنید.`}
            </p>
          )}
        </div>
      )}
    </SectionCard>
  )
}
