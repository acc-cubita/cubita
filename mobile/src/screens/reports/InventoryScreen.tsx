import { useQuery } from '@tanstack/react-query'
import { View } from 'react-native'
import { fetchInventoryReport } from '../../api/reports'
import { MoneyRow, ReportScaffold, Section, TotalRow } from '../../ui/report'
import { AppText } from '../../ui'
import { colors, faNum, spacing } from '../../theme'

export function InventoryScreen() {
  const q = useQuery({ queryKey: ['inventory-report'], queryFn: fetchInventoryReport })
  const d = q.data
  return (
    <ReportScaffold loading={q.isLoading} fetching={q.isFetching} error={q.error} onRefresh={q.refetch}>
      <Section title="خلاصه">
        <MoneyRow label="تعدادِ اقلام" amount={d?.item_count ?? 0} />
        <TotalRow label="ارزشِ کلِ موجودی" amount={d?.total_value ?? 0} />
      </Section>

      <Section title="اقلام">
        {d?.rows.length ? (
          d.rows.map((r) => (
            <View key={r.item_id} style={{ paddingVertical: spacing.xs }}>
              <MoneyRow label={r.name} amount={r.stock_value} />
              <AppText variant="caption" color={colors.textMuted}>
                موجودی: {faNum(r.qty_on_hand)} {r.unit}
              </AppText>
            </View>
          ))
        ) : (
          <AppText variant="body" color={colors.textMuted}>
            موردی نیست
          </AppText>
        )}
      </Section>
    </ReportScaffold>
  )
}
