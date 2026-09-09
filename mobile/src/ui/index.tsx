import { type ReactNode } from 'react'
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
  type ViewStyle,
} from 'react-native'
import { colors, font, radius, spacing } from '../theme'

// کامپوننت‌های پایه‌ی مشترک — سبک، بدونِ وابستگیِ اضافه، هم‌رنگِ تمِ تیره‌ی برند.

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>
}

export function AppText({
  children,
  variant = 'body',
  color,
  weight,
  style,
  numberOfLines,
  maxFontSizeMultiplier,
}: {
  children: ReactNode
  variant?: 'display' | 'title' | 'heading' | 'body' | 'label' | 'caption'
  color?: string
  weight?: keyof typeof font.weight
  style?: object
  numberOfLines?: number
  /** سقفِ بزرگ‌نماییِ فونتِ سیستم. ← `font.maxScale` در تم. */
  maxFontSizeMultiplier?: number
}) {
  const v = TEXT_VARIANTS[variant]
  return (
    <Text
      numberOfLines={numberOfLines}
      maxFontSizeMultiplier={maxFontSizeMultiplier}
      style={[
        { color: color ?? colors.text, fontSize: v.size, fontWeight: weight ? font.weight[weight] : v.weight },
        style,
      ]}
    >
      {children}
    </Text>
  )
}

const TEXT_VARIANTS = {
  display: { size: font.size.display, weight: font.weight.black },
  title: { size: font.size.xxl, weight: font.weight.bold },
  heading: { size: font.size.lg, weight: font.weight.bold },
  body: { size: font.size.md, weight: font.weight.regular },
  label: { size: font.size.sm, weight: font.weight.semibold },
  caption: { size: font.size.xs, weight: font.weight.regular },
} as const

export function Button({
  label,
  onPress,
  variant = 'primary',
  loading,
  disabled,
  icon,
}: {
  label: string
  onPress: () => void
  variant?: 'primary' | 'ghost' | 'danger'
  loading?: boolean
  disabled?: boolean
  icon?: ReactNode
}) {
  const isPrimary = variant === 'primary'
  const isDanger = variant === 'danger'
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      android_ripple={{ color: isPrimary ? 'rgba(0,0,0,0.15)' : colors.surfaceAlt }}
      style={({ pressed }) => [
        styles.btn,
        isPrimary && { backgroundColor: colors.accent },
        variant === 'ghost' && { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors.borderStrong },
        isDanger && { backgroundColor: colors.dangerSoft, borderWidth: 1, borderColor: colors.danger },
        (disabled || loading) && { opacity: 0.55 },
        pressed && { opacity: 0.9 },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isPrimary ? colors.onAccent : colors.text} />
      ) : (
        <View style={styles.btnInner}>
          {icon}
          <Text
            style={{
              color: isPrimary ? colors.onAccent : isDanger ? colors.danger : colors.text,
              fontSize: font.size.md,
              fontWeight: font.weight.bold,
            }}
          >
            {label}
          </Text>
        </View>
      )}
    </Pressable>
  )
}

export function TextField({
  label,
  style,
  ...props
}: TextInputProps & { label?: string }) {
  return (
    <View style={{ gap: spacing.xs }}>
      {label ? <AppText variant="label" color={colors.textMuted}>{label}</AppText> : null}
      <TextInput
        placeholderTextColor={colors.textFaint}
        style={[styles.input, style]}
        {...props}
      />
    </View>
  )
}

export function Badge({ count }: { count: number }) {
  if (count <= 0) return null
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText} maxFontSizeMultiplier={font.maxScale.dense}>
        {count > 99 ? '۹۹+' : count.toLocaleString('fa-IR')}
      </Text>
    </View>
  )
}

export function Center({ children }: { children: ReactNode }) {
  return <View style={styles.center}>{children}</View>
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  btn: {
    // `minHeight` و نه `height`: با فونتِ بزرگِ سیستم متنِ دکمه از کادر بیرون
    // می‌زند و از پایین بریده می‌شود. کف را نگه می‌داریم، سقف را نه.
    minHeight: 52,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
  },
  btnInner: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    minHeight: 52,
    paddingVertical: spacing.sm,
    color: colors.text,
    fontSize: font.size.md,
    textAlign: 'right',
  },
  badge: {
    minWidth: 20,
    minHeight: 20,
    paddingHorizontal: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.danger,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl, gap: spacing.md },
})
