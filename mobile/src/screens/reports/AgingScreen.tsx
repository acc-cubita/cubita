import { useQuery } from '@tanstack/react-query'
import { View } from 'react-native'
import type { RouteProp } from '@react-navigation/native'
import { useRoute } from '@react-navigation/native'
import { fetchAging } from '../../api/reports'
import { MoneyRow, ReportScaffold, Section, TotalRow } from '../../ui/report'
import { AppText } from '../../ui'
import { colors, spacing } from '../../theme'
import type { ReportsStackParams } from '../../navigation/types'

export function AgingScreen() {
  const { params } = useRoute<RouteProp<ReportsStackParams, 'Aging'>>()
  const kind = params.kind
  const q = useQuery({ queryKey: ['aging', kind], queryFn: () => fetchAging(kind) })
  const d = q.data
  const noun = kind === 'receivable' ? 'طلب' : 'بدهی'

  return (
    <ReportScaffold loading={q.isLoading} fetching={q.isFetching} error={q.error} onRefresh={q.refetch}>
      <Section title="خلاصه‌ی سنی">
        <MoneyRow label="۰ تا ۳۰ روز" amount={d?.total_current ?? 0} />
        <MoneyRow label="۳۱ تا ۶۰ روز" amount={d?.total_31_60 ?? 0} />
        <MoneyRow label="۶۱ تا ۹۰ روز" amount={d?.total_61_90 ?? 0} />
        <MoneyRow label="بیش از ۹۰ روز" amount={d?.total_over_90 ?? 0} muted />
        <TotalRow label={`جمعِ ${noun}`} amount={d?.grand_total ?? 0} />
      </Section>

      <Section title="به تفکیکِ شخص">
        {d?.rows.length ? (
          d.rows.map((r) => (
            <View key={r.contact_id} style={{ paddingVertical: spacing.xs }}>
              <MoneyRow label={r.contact_name} amount={r.total} />
              {Number(r.over_90) > 0 ? (
                <AppText variant="caption" color={colors.danger}>
                  شاملِ معوقِ بالای ۹۰ روز
                </AppText>
              ) : null}
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
