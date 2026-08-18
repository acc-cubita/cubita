import { ScrollView, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import Constants from 'expo-constants'
import { useAuth } from '../auth/AuthContext'
import { AppText, Button, Card } from '../ui'
import { colors, spacing } from '../theme'

// تنظیمات/بیشتر: پروفایل، وضعیتِ بیومتریک، خروج، نسخه.
export function MoreScreen() {
  const { me, signOut, biometricAvailable } = useAuth()

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <AppText variant="title">بیشتر</AppText>

        <Card>
          <AppText variant="heading">{me?.name ?? ''}</AppText>
          <Row label="ایمیل" value={me?.email ?? '—'} />
          <Row label="کسب‌وکار" value={me?.tenant_name ?? '—'} />
          <Row label="نقش" value={me?.role_name ?? '—'} />
        </Card>

        <Card>
          <Row
            label="قفلِ بیومتریک"
            value={biometricAvailable ? 'فعال (هنگامِ باز کردن)' : 'در دسترس نیست'}
          />
          <Row label="نسخه‌ی اپ" value={Constants.expoConfig?.version ?? '۱.۰.۰'} />
        </Card>

        <Button label="خروج از حساب" variant="danger" onPress={signOut} />
      </ScrollView>
    </SafeAreaView>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <AppText variant="body" color={colors.textMuted}>
        {label}
      </AppText>
      <AppText variant="body" weight="semibold">
        {value}
      </AppText>
    </View>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, gap: spacing.md },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },
})
