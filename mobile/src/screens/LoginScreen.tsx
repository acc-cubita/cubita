import { useState } from 'react'
import { KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { useAuth } from '../auth/AuthContext'
import { isApiError } from '../api/client'
import { AppText, Button, TextField } from '../ui'
import { BrandMark } from '../ui/BrandMark'
import { colors, spacing } from '../theme'

export function LoginScreen() {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    if (!email.trim() || !password) {
      setError('ایمیل و رمز عبور را وارد کنید.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await signIn(email, password)
    } catch (e) {
      setError(isApiError(e) ? e.message : 'ورود ناموفق بود.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <View style={styles.container}>
          <View style={styles.brand}>
            <BrandMark size={64} />
            <AppText variant="title">کوبیتا</AppText>
            <AppText variant="body" color={colors.textMuted}>
              مدیرِ همراهِ کسب‌وکارِ شما
            </AppText>
          </View>

          <View style={styles.form}>
            <TextField
              label="ایمیل"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              textContentType="emailAddress"
              placeholder="you@example.com"
              style={{ textAlign: 'left' }}
            />
            <TextField
              label="رمز عبور"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder="••••••••"
              onSubmitEditing={submit}
            />
            {error ? (
              <AppText variant="label" color={colors.danger}>
                {error}
              </AppText>
            ) : null}
            <View style={{ height: spacing.sm }} />
            <Button label="ورود" onPress={submit} loading={busy} />
          </View>

          <AppText variant="caption" color={colors.textFaint} style={styles.footer}>
            حساب روی cubita.ir ساخته می‌شود. این اپ برای مدیریتِ کسب‌وکارِ شماست.
          </AppText>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  container: { flex: 1, padding: spacing.xl, justifyContent: 'center', gap: spacing.xxl },
  brand: { alignItems: 'center', gap: spacing.sm },
  form: { gap: spacing.md },
  footer: { textAlign: 'center' },
})
