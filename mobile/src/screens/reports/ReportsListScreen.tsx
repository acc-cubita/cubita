import { Pressable, ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useNavigation } from '@react-navigation/native'
import type { NativeStackNavigationProp } from '@react-navigation/native-stack'
import { Ionicons } from '@expo/vector-icons'
import { AppText } from '../../ui'
import { colors, radius, spacing } from '../../theme'
import type { ReportsStackParams } from '../../navigation/types'

type Nav = NativeStackNavigationProp<ReportsStackParams, 'ReportsList'>
type IconName = keyof typeof Ionicons.glyphMap

const REPORTS: { icon: IconName; title: string; subtitle: string; go: (n: Nav) => void }[] = [
  { icon: 'trending-up', title: 'سود و زیان', subtitle: 'درآمد، هزینه و سودِ خالص', go: (n) => n.navigate('IncomeStatement') },
  { icon: 'library', title: 'ترازنامه', subtitle: 'دارایی، بدهی و حقوقِ صاحبان', go: (n) => n.navigate('BalanceSheet') },
  { icon: 'time', title: 'مطالبات', subtitle: 'تحلیلِ سنیِ طلب از مشتریان', go: (n) => n.navigate('Aging', { kind: 'receivable' }) },
  { icon: 'time-outline', title: 'بدهی‌ها', subtitle: 'تحلیلِ سنیِ بدهی به تأمین‌کنندگان', go: (n) => n.navigate('Aging', { kind: 'payable' }) },
  { icon: 'cube', title: 'ارزشِ موجودی', subtitle: 'موجودی و بهای تمام‌شده‌ی انبار', go: (n) => n.navigate('Inventory') },
]

export function ReportsListScreen() {
  const nav = useNavigation<Nav>()
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <AppText variant="title">گزارش‌ها</AppText>
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        {REPORTS.map((r) => (
          <Pressable
            key={r.title}
            onPress={() => r.go(nav)}
            android_ripple={{ color: colors.surfaceAlt }}
            style={({ pressed }) => [styles.item, pressed && { opacity: 0.85 }]}
          >
            <View style={styles.iconBox}>
              <Ionicons name={r.icon} size={22} color={colors.accent} />
            </View>
            <View style={{ flex: 1 }}>
              <AppText variant="heading">{r.title}</AppText>
              <AppText variant="caption" color={colors.textMuted}>
                {r.subtitle}
              </AppText>
            </View>
            <Ionicons name="chevron-back" size={20} color={colors.textFaint} />
          </Pressable>
        ))}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.lg, paddingBottom: spacing.sm },
  content: { padding: spacing.lg, paddingTop: 0, gap: spacing.md },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  iconBox: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
