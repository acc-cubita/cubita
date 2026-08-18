import { StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { AppText } from '../ui'
import { colors, spacing } from '../theme'

// صفحه‌ی موقتِ تب‌هایی که در مایلستون‌های بعدی پر می‌شوند (گزارش/بازار/اشخاص).
export function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <AppText variant="title">{title}</AppText>
      </View>
      <View style={styles.center}>
        <AppText variant="body" color={colors.textMuted} style={{ textAlign: 'center' }}>
          {note}
        </AppText>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { padding: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
})
