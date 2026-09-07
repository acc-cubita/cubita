import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { useQuery } from '@tanstack/react-query'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '../auth/AuthContext'
import { fetchAlerts, fetchSalesDashboard, fetchSalesSummary } from '../api/reports'
import { isApiError } from '../api/client'
import type { AlertItem } from '../api/types'
import { canAccess } from '../auth/access'
import type { HomeStackParams } from '../navigation/types'
import { AppText, Button, Card } from '../ui'
import { MonthlyTrendChart } from '../ui/MonthlyTrendChart'
import { colors, faMoney, faNum, radius, spacing } from '../theme'

// داشبوردِ مدیر: شاخص‌ها + روندِ فروش + هشدارها + پرفروش‌ها. آنلاین‌محور با react-query.
export function HomeScreen() {
  const { me } = useAuth()
  const nav = useNavigation<NativeStackNavigationProp<HomeStackParams>>()

  const summaryQ = useQuery({ queryKey: ['sales-summary'], queryFn: fetchSalesSummary })
  const dashQ = useQuery({ queryKey: ['sales-dashboard'], queryFn: () => fetchSalesDashboard(12) })
  const alertsQ = useQuery({ queryKey: ['alerts'], queryFn: fetchAlerts })

  const refreshing = summaryQ.isFetching || dashQ.isFetching || alertsQ.isFetching
  const refetchAll = () => {
    void summaryQ.refetch()
    void dashQ.refetch()
    void alertsQ.refetch()
  }

  const s = summaryQ.data
  const err = [summaryQ.error, dashQ.error, alertsQ.error].find(Boolean)

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refetchAll} tintColor={colors.accent} />
        }
      >
        <View style={styles.header}>
          <AppText variant="body" color={colors.textMuted}>
            سلام {me?.name ?? ''} 👋
          </AppText>
          <AppText variant="title">{me?.tenant_name ?? 'کوبیتا'}</AppText>
        </View>

        {me?.is_trial ? (
          <Card style={{ borderColor: colors.accent, backgroundColor: colors.accentSoft }}>
            <AppText variant="label" color={colors.accent}>
              {me.trial_expired
                ? 'دوره‌ی آزمایشی تمام شده — برای ادامه یک پلن تهیه کنید.'
                : `دوره‌ی آزمایشی — ${faNum(me.trial_days_left ?? 0)} روز مانده`}
            </AppText>
          </Card>
        ) : null}

        {err ? (
          <Card style={{ borderColor: colors.danger }}>
            <AppText variant="label" color={colors.danger}>
              {isApiError(err) ? err.message : 'خطا در دریافتِ اطلاعات'}
            </AppText>
            <View style={{ marginTop: spacing.md }}>
              <Button label="تلاش دوباره" variant="ghost" onPress={refetchAll} />
            </View>
          </Card>
        ) : null}

        {canAccess(me, 'newInvoice') ? (
          <QuickAction
            label="فاکتورِ فروش"
            icon="receipt-outline"
            tone={colors.accent}
            onPress={() => nav.navigate('NewInvoice')}
            wide
          />
        ) : null}

        {canAccess(me, 'treasury') ? (
          <View style={styles.quickRow}>
            <QuickAction
              label="ثبتِ دریافت"
              icon="arrow-down-circle"
              tone={colors.success}
              onPress={() => nav.navigate('Treasury', { type: 'receipt' })}
            />
            <QuickAction
              label="ثبتِ پرداخت"
              icon="arrow-up-circle"
              tone={colors.danger}
              onPress={() => nav.navigate('Treasury', { type: 'payment' })}
            />
          </View>
        ) : null}

        <View style={styles.kpiRow}>
          <KpiCard title="فروشِ کل" value={s ? faMoney(s.total_with_tax) : '—'} hint="ریال (با مالیات)" />
          <KpiCard title="سود ناخالص" value={s ? faMoney(s.gross_profit) : '—'} hint={s ? `حاشیه ${faNum(s.margin_pct)}٪` : ''} tone="success" />
        </View>
        <View style={styles.kpiRow}>
          <KpiCard title="فروشِ ۳۰ روز" value={s ? faMoney(s.last_30_with_tax) : '—'} hint="ریال" />
          <KpiCard title="تعداد فاکتور" value={s ? faNum(s.invoice_count) : '—'} hint={s ? `میانگین ${faMoney(s.avg_invoice)}` : ''} />
        </View>

        {dashQ.data && dashQ.data.monthly.length > 0 ? (
          <Card>
            <MonthlyTrendChart data={dashQ.data.monthly} />
          </Card>
        ) : null}

        <AlertsCard
          items={alertsQ.data?.items ?? []}
          total={alertsQ.data?.total ?? 0}
          onPress={() => nav.navigate('Alerts')}
        />

        {dashQ.data && dashQ.data.top_items.length > 0 ? (
          <Card>
            <AppText variant="heading" style={{ marginBottom: spacing.sm }}>
              پرفروش‌ترین کالاها
            </AppText>
            {dashQ.data.top_items.slice(0, 5).map((it) => (
              <View key={it.item_id} style={styles.row}>
                <AppText variant="body" numberOfLines={1} style={{ flex: 1 }}>
                  {it.name}
                </AppText>
                <AppText variant="label" color={colors.accent}>
                  {faMoney(it.revenue)}
                </AppText>
              </View>
            ))}
          </Card>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  )
}

function KpiCard({
  title,
  value,
  hint,
  tone,
}: {
  title: string
  value: string
  hint?: string
  tone?: 'success'
}) {
  return (
    <Card style={styles.kpi}>
      <AppText variant="label" color={colors.textMuted}>
        {title}
      </AppText>
      <AppText variant="heading" color={tone === 'success' ? colors.success : colors.text} style={{ marginTop: spacing.xs }} numberOfLines={1}>
        {value}
      </AppText>
      {hint ? (
        <AppText variant="caption" color={colors.textFaint} numberOfLines={1}>
          {hint}
        </AppText>
      ) : null}
    </Card>
  )
}

function QuickAction({
  label,
  icon,
  tone,
  onPress,
  wide,
}: {
  label: string
  icon: keyof typeof Ionicons.glyphMap
  tone: string
  onPress: () => void
  /** دکمه‌ی تمام‌عرض (کنشِ اصلی) به‌جای نیمِ ردیف. */
  wide?: boolean
}) {
  return (
    <Pressable
      onPress={onPress}
      android_ripple={{ color: colors.surfaceAlt }}
      style={[styles.quickBtn, wide && styles.quickBtnWide]}
    >
      <Ionicons name={icon} size={22} color={tone} />
      <AppText variant="label" weight="semibold">
        {label}
      </AppText>
    </Pressable>
  )
}

function AlertsCard({ items, total, onPress }: { items: AlertItem[]; total: number; onPress: () => void }) {
  const toneOf = (sev: string) =>
    sev === 'danger' ? colors.danger : sev === 'warning' ? colors.warning : colors.violet
  return (
    <Pressable onPress={onPress} android_ripple={{ color: colors.surfaceAlt }}>
      <Card>
        <View style={styles.alertHead}>
          <View style={styles.alertHeadStart}>
            <AppText variant="heading">هشدارها</AppText>
            {total > 0 ? (
              <View style={styles.alertCount}>
                <AppText variant="label" color={colors.onAccent}>
                  {faNum(total)}
                </AppText>
              </View>
            ) : null}
          </View>
          <View style={styles.seeAll}>
            <AppText variant="label" color={colors.textMuted}>
              مشاهده‌ی همه
            </AppText>
            <Ionicons name="chevron-back" size={16} color={colors.textMuted} />
          </View>
        </View>
        {items.length === 0 ? (
          <AppText variant="body" color={colors.textMuted} style={{ marginTop: spacing.sm }}>
            هشداری نیست — همه‌چیز مرتب است ✅
          </AppText>
        ) : (
          items.slice(0, 5).map((a, i) => (
            <View key={`${a.category}-${a.ref_id}-${i}`} style={styles.alertRow}>
              <Ionicons name="ellipse" size={9} color={toneOf(a.severity)} style={{ marginTop: 6 }} />
              <View style={{ flex: 1 }}>
                <AppText variant="body" weight="semibold" numberOfLines={1}>
                  {a.title}
                </AppText>
                <AppText variant="caption" color={colors.textMuted} numberOfLines={1}>
                  {a.detail}
                </AppText>
              </View>
            </View>
          ))
        )}
      </Card>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, gap: spacing.md },
  header: { gap: 2, marginBottom: spacing.sm },
  kpiRow: { flexDirection: 'row', gap: spacing.md },
  kpi: { flex: 1 },
  quickRow: { flexDirection: 'row', gap: spacing.md },
  quickBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  quickBtnWide: { flex: 0, borderColor: colors.accent },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  alertHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  alertHeadStart: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  seeAll: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  alertCount: {
    minWidth: 24,
    height: 22,
    paddingHorizontal: 8,
    borderRadius: 999,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  alertRow: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start', paddingVertical: spacing.sm },
})
