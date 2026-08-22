import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { fetchAlerts } from '../api/reports'
import { isApiError } from '../api/client'
import type { AlertItem } from '../api/types'
import { AppText, Button, Card, Center } from '../ui'
import { colors, faMoney, faNum, radius, spacing } from '../theme'

// صفحه‌ی کاملِ هشدارها — همه‌ی موارد، مرتب بر اساسِ شدت (فوری بالا). از کارتِ خانه یا
// لمسِ اعلانِ Push (route=alerts) به اینجا می‌آییم.

const CATEGORY_LABEL: Record<string, string> = {
  check: 'چک',
  receivable: 'مطالبات',
  credit: 'سقف اعتبار',
  recurring: 'تکرارشونده',
  calendar: 'تقویم',
  stock: 'موجودی',
  installment: 'قسط',
}

const SEVERITY_RANK: Record<string, number> = { danger: 0, warning: 1, info: 2 }

function toneOf(sev: string): string {
  return sev === 'danger' ? colors.danger : sev === 'warning' ? colors.warning : colors.violet
}
function iconOf(sev: string): keyof typeof Ionicons.glyphMap {
  return sev === 'danger' ? 'alert-circle' : sev === 'warning' ? 'warning' : 'information-circle'
}

export function AlertsScreen() {
  const alertsQ = useQuery({ queryKey: ['alerts'], queryFn: fetchAlerts })
  const items = [...(alertsQ.data?.items ?? [])].sort(
    (a, b) => (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9),
  )
  const total = alertsQ.data?.total ?? 0

  if (alertsQ.isError) {
    return (
      <Center>
        <AppText variant="body" color={colors.danger}>
          {isApiError(alertsQ.error) ? alertsQ.error.message : 'خطا در دریافتِ هشدارها'}
        </AppText>
        <Button label="تلاش دوباره" variant="ghost" onPress={() => void alertsQ.refetch()} />
      </Center>
    )
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={alertsQ.isFetching}
          onRefresh={() => void alertsQ.refetch()}
          tintColor={colors.accent}
        />
      }
    >
      {total === 0 ? (
        <Card>
          <View style={styles.emptyRow}>
            <Ionicons name="checkmark-circle" size={22} color={colors.success} />
            <AppText variant="body" color={colors.textMuted}>
              هشداری نیست — همه‌چیز مرتب است.
            </AppText>
          </View>
        </Card>
      ) : (
        <>
          <AppText variant="label" color={colors.textMuted}>
            {faNum(total)} مورد نیازِ رسیدگی
          </AppText>
          {items.map((a, i) => (
            <AlertRow key={`${a.category}-${a.ref_id}-${i}`} item={a} />
          ))}
        </>
      )}
    </ScrollView>
  )
}

function AlertRow({ item }: { item: AlertItem }) {
  const tone = toneOf(item.severity)
  return (
    <Card style={styles.row}>
      <View style={[styles.bar, { backgroundColor: tone }]} />
      <Ionicons name={iconOf(item.severity)} size={20} color={tone} style={{ marginTop: 1 }} />
      <View style={{ flex: 1 }}>
        <View style={styles.titleRow}>
          <AppText variant="body" weight="semibold" numberOfLines={1} style={{ flex: 1 }}>
            {item.title}
          </AppText>
          <View style={styles.chip}>
            <AppText variant="caption" color={colors.textMuted}>
              {CATEGORY_LABEL[item.category] ?? item.category}
            </AppText>
          </View>
        </View>
        <AppText variant="caption" color={colors.textMuted} numberOfLines={2}>
          {item.detail}
        </AppText>
        {item.amount ? (
          <AppText variant="label" color={tone} style={{ marginTop: 2 }}>
            {faMoney(item.amount)} ریال
          </AppText>
        ) : null}
      </View>
    </Card>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, gap: spacing.md },
  emptyRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start', overflow: 'hidden' },
  bar: { position: 'absolute', right: 0, top: 0, bottom: 0, width: 4, borderTopRightRadius: radius.lg, borderBottomRightRadius: radius.lg },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
})
