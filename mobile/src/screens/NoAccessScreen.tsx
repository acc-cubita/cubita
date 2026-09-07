import { StyleSheet, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'

import { useAuth } from '../auth/AuthContext'
import { AppText, Button } from '../ui'
import { colors, radius, spacing } from '../theme'

/**
 * وقتی نقشِ کاربر هیچ بخشی از اپِ موبایل را نمی‌بیند.
 *
 * **چرا صفحه‌ی جدا و نه فقط تبِ خالی:** «مسئولِ حقوق و دستمزد» و «انباردار» در
 * بک‌اند مجوزهای واقعی دارند، ولی اپِ موبایل هنوز هیچ صفحه‌ای برای آن‌ها نساخته.
 * سه راه داشتیم: تب‌های خالی نشان بدهیم (گیج‌کننده)، تب‌های ۴۰۳‌دهنده نشان بدهیم
 * (همان چیزی که داشتیم و خراب بود)، یا صادقانه بگوییم چرا. سومی را انتخاب کردیم.
 *
 * پیام عمداً می‌گوید «هنوز» — چون این محدودیتِ اپ است نه نقشِ کاربر؛ همان کاربر
 * روی نسخه‌ی وب/دسکتاپ کارش را می‌کند.
 */
export function NoAccessScreen() {
  const { me, signOut } = useAuth()
  const insets = useSafeAreaInsets()

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.xxl }]}>
      <View style={styles.icon}>
        <Ionicons name="phone-portrait-outline" size={34} color={colors.textMuted} />
      </View>

      <AppText variant="heading" weight="bold" style={styles.title}>
        اپِ موبایل هنوز برای نقشِ شما آماده نیست
      </AppText>

      <AppText color={colors.textMuted} style={styles.body}>
        {me?.role_name
          ? `نقشِ شما «${me.role_name}» است. بخش‌های مربوط به این نقش فعلاً فقط در نسخه‌ی وب و دسکتاپ در دسترس‌اند.`
          : 'بخش‌های مربوط به نقشِ شما فعلاً فقط در نسخه‌ی وب و دسکتاپ در دسترس‌اند.'}
      </AppText>

      <AppText variant="caption" color={colors.textFaint} style={styles.hint}>
        اگر فکر می‌کنید باید دسترسیِ بیشتری داشته باشید، با مدیرِ کسب‌وکارتان صحبت کنید.
      </AppText>

      <View style={styles.action}>
        <Button label="خروج از حساب" variant="ghost" onPress={signOut} />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  icon: {
    width: 68,
    height: 68,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  title: { textAlign: 'center', marginBottom: spacing.sm },
  body: { textAlign: 'center', lineHeight: 22, marginBottom: spacing.lg },
  hint: { textAlign: 'center', marginBottom: spacing.xl },
  action: { alignSelf: 'stretch' },
})
