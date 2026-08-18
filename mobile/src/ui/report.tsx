import { type ReactNode } from 'react'
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { AppText, Button, Card, Center } from './index'
import { isApiError } from '../api/client'
import { colors, faMoney, spacing } from '../theme'

// پوسته‌ی مشترکِ صفحه‌های گزارش: هدر، حالت‌های بارگذاری/خطا، و pull-to-refresh.
export function ReportScaffold({
  loading,
  fetching,
  error,
  onRefresh,
  children,
}: {
  loading: boolean
  fetching: boolean
  error: unknown
  onRefresh: () => void
  children: ReactNode
}) {
  if (loading) {
    return (
      <Center>
        <AppText variant="body" color={colors.textMuted}>
          در حال دریافت…
        </AppText>
      </Center>
    )
  }
  if (error) {
    return (
      <Center>
        <AppText variant="body" color={colors.danger} style={{ textAlign: 'center' }}>
          {isApiError(error) ? error.message : 'خطا در دریافتِ گزارش'}
        </AppText>
        <Button label="تلاش دوباره" variant="ghost" onPress={onRefresh} />
      </Center>
    )
  }
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={fetching} onRefresh={onRefresh} tintColor={colors.accent} />}
    >
      {children}
    </ScrollView>
  )
}

// یک ردیفِ «برچسب + مبلغ».
export function MoneyRow({ label, amount, muted }: { label: string; amount: string | number; muted?: boolean }) {
  return (
    <View style={styles.row}>
      <AppText variant="body" color={muted ? colors.textMuted : colors.text} numberOfLines={1} style={{ flex: 1 }}>
        {label}
      </AppText>
      <AppText variant="body" weight="semibold" color={muted ? colors.textMuted : colors.text}>
        {faMoney(amount)}
      </AppText>
    </View>
  )
}

// ردیفِ جمع/برجسته (بالای کارت یا انتهای بخش).
export function TotalRow({ label, amount, tone }: { label: string; amount: string | number; tone?: 'success' | 'danger' | 'accent' }) {
  const c = tone === 'success' ? colors.success : tone === 'danger' ? colors.danger : colors.accent
  return (
    <View style={[styles.row, styles.total]}>
      <AppText variant="heading">{label}</AppText>
      <AppText variant="heading" color={c}>
        {faMoney(amount)}
      </AppText>
    </View>
  )
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <AppText variant="label" color={colors.textMuted} style={{ marginBottom: spacing.sm }}>
        {title}
      </AppText>
      {children}
    </Card>
  )
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, gap: spacing.md },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  total: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginTop: spacing.xs,
    paddingTop: spacing.md,
  },
})
