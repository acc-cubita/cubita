import { useQuery } from '@tanstack/react-query'
import { fetchIncomeStatement } from '../../api/reports'
import { MoneyRow, ReportScaffold, Section, TotalRow } from '../../ui/report'
import { AppText } from '../../ui'
import { colors } from '../../theme'

export function IncomeStatementScreen() {
  const q = useQuery({ queryKey: ['income-statement'], queryFn: fetchIncomeStatement })
  const d = q.data
  return (
    <ReportScaffold loading={q.isLoading} fetching={q.isFetching} error={q.error} onRefresh={q.refetch}>
      <Section title="درآمدها">
        {d?.income.length ? (
          d.income.map((a) => <MoneyRow key={a.account_id} label={a.account_name} amount={a.balance} />)
        ) : (
          <AppText variant="body" color={colors.textMuted}>موردی نیست</AppText>
        )}
        <TotalRow label="جمعِ درآمد" amount={d?.total_income ?? 0} tone="success" />
      </Section>

      <Section title="هزینه‌ها">
        {d?.expenses.length ? (
          d.expenses.map((a) => <MoneyRow key={a.account_id} label={a.account_name} amount={a.balance} />)
        ) : (
          <AppText variant="body" color={colors.textMuted}>موردی نیست</AppText>
        )}
        <TotalRow label="جمعِ هزینه" amount={d?.total_expenses ?? 0} tone="danger" />
      </Section>

      <Section title="نتیجه">
        <TotalRow
          label="سودِ خالص"
          amount={d?.net_profit ?? 0}
          tone={Number(d?.net_profit ?? 0) >= 0 ? 'success' : 'danger'}
        />
      </Section>
    </ReportScaffold>
  )
}
