import { Component, type ReactNode } from 'react'
import { StyleSheet, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import { AppText, Button } from '../ui'
import { colors, radius, spacing } from '../theme'
import { report } from './reporter'

/**
 * گیرنده‌ی خطای رندرِ React.
 *
 * **مسئله‌ای که حل می‌کند:** بدونِ این، یک خطا در رندر کلِ درخت را unmount می‌کند و
 * کاربر یک صفحه‌ی *سفیدِ خالی* می‌بیند — بدونِ پیام، بدونِ دکمه، بدونِ راهِ برگشت.
 * تنها کارِ ممکن بستن و باز کردنِ اپ است، و ما هم هرگز نمی‌فهمیم چه شد.
 *
 * **چرا کلاس:** React هیچ معادلِ هوکی برای `componentDidCatch` ندارد. این تنها
 * جای اپ است که کامپوننتِ کلاسی لازم دارد.
 *
 * **چرا دکمه‌ی «تلاش دوباره» و نه فقط پیام:** بیشترِ خطاهای رندر از یک وضعیتِ
 * گذرا می‌آیند (پاسخِ ناقصِ سرور، رکوردی که وسطِ کار حذف شده). ری‌ست کردنِ مرز
 * معمولاً کافی است و کاربر لازم نیست اپ را ببندد.
 */
interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error): void {
    // fatal نیست: اپ زنده است و کاربر می‌تواند ادامه دهد — ولی صفحه‌ای از کار افتاد.
    void report(error, false)
  }

  private reset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <View style={styles.root}>
        <View style={styles.icon}>
          <Ionicons name="warning-outline" size={34} color={colors.warning} />
        </View>

        <AppText variant="heading" weight="bold" style={styles.title}>
          این صفحه باز نشد
        </AppText>

        <AppText color={colors.textMuted} style={styles.body}>
          خطا گزارش شد تا بررسی شود. می‌توانید دوباره تلاش کنید؛ اگر باز هم نشد،
          اپ را ببندید و دوباره باز کنید.
        </AppText>

        {/* پیامِ فنی عمداً هست ولی کم‌رنگ: به پشتیبانی کمک می‌کند، کاربر را نمی‌ترساند. */}
        <AppText variant="caption" color={colors.textFaint} style={styles.detail} numberOfLines={3}>
          {error.message}
        </AppText>

        <View style={styles.action}>
          <Button label="تلاش دوباره" onPress={this.reset} />
        </View>
      </View>
    )
  }
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
    backgroundColor: colors.warningSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  title: {
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  body: {
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  detail: {
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  action: {
    alignSelf: 'stretch',
  },
})
