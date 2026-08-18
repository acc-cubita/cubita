import { useQuery } from '@tanstack/react-query'
import { fetchBalanceSheet } from '../../api/reports'
import { MoneyRow, ReportScaffold, Section, TotalRow } from '../../ui/report'
import { AppText } from '../../ui'
import { colors } from '../../theme'
import type { AccountBalance } from '../../api/types'

function group(title: string, rows: AccountBalance[] | undefined, total: string | undefined, tone?: 'success' | 'danger' | 'accent') {
  return (
    <Section title={title}>
      {rows && rows.length ? (
        rows.map((a) => <MoneyRow key={a.account_id} label={a.account_name} amount={a.balance} />)
      ) : (
        <AppText variant="body" color={colors.textMuted}>موردی نیست</AppText>
      )}
      <TotalRow label="جمع" amount={total ?? 0} tone={tone} />
    </Section>
  )
}

export function BalanceSheetScreen() {
  const q = useQuery({ queryKey: ['balance-sheet'], queryFn: fetchBalanceSheet })
  const d = q.data
  return (
    <ReportScaffold loading={q.isLoading} fetching={q.isFetching} error={q.error} onRefresh={q.refetch}>
      {group('دارایی‌ها', d?.assets, d?.total_assets, 'accent')}
      {group('بدهی‌ها', d?.liabilities, d?.total_liabilities, 'danger')}
      {group('حقوقِ صاحبانِ سرمایه', d?.equity, d?.total_equity, 'success')}
      <Section title="سودِ دوره‌ی جاری">
        <TotalRow
          label="سود/زیانِ دوره"
          amount={d?.current_period_profit ?? 0}
          tone={Number(d?.current_period_profit ?? 0) >= 0 ? 'success' : 'danger'}
        />
      </Section>
    </ReportScaffold>
  )
}
