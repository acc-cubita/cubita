import { useEffect, useState } from 'react'
import { StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useAuth } from '../auth/AuthContext'
import { AppText, Button } from '../ui'
import { BrandMark } from '../ui/BrandMark'
import { colors, spacing } from '../theme'

// نشستِ برگشتی: توکن هست ولی پیش از نمایشِ داده، قفلِ بیومتریک باز می‌شود.
export function LockScreen() {
  const { unlock, signOut } = useAuth()
  const [failed, setFailed] = useState(false)

  async function tryUnlock() {
    setFailed(false)
    const ok = await unlock()
    if (!ok) setFailed(true)
  }

  // به‌محضِ باز شدنِ صفحه، خودکار قفل را بپرس.
  useEffect(() => {
    void tryUnlock()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <BrandMark size={72} />
        <AppText variant="heading">کوبیتا قفل است</AppText>
        <AppText variant="body" color={colors.textMuted} style={{ textAlign: 'center' }}>
          برای دیدنِ اطلاعاتِ کسب‌وکار، هویتِ خود را تأیید کنید.
        </AppText>
        {failed ? (
          <AppText variant="label" color={colors.danger}>
            تأیید نشد. دوباره تلاش کنید.
          </AppText>
        ) : null}
        <View style={styles.actions}>
          <Button label="باز کردن با بیومتریک" onPress={tryUnlock} />
          <Button label="ورود با حسابِ دیگر" variant="ghost" onPress={signOut} />
        </View>
      </View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl, gap: spacing.md },
  actions: { alignSelf: 'stretch', gap: spacing.md, marginTop: spacing.lg },
})
