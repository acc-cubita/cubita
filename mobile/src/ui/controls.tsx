import { Pressable, StyleSheet, View } from 'react-native'
import { AppText } from './index'
import { colors, font, radius, spacing } from '../theme'

type Tone = 'success' | 'warning' | 'danger' | 'muted' | 'accent'

const TONE: Record<Tone, { fg: string; bg: string }> = {
  success: { fg: colors.success, bg: colors.successSoft },
  warning: { fg: colors.warning, bg: colors.warningSoft },
  danger: { fg: colors.danger, bg: colors.dangerSoft },
  accent: { fg: colors.accent, bg: colors.accentSoft },
  muted: { fg: colors.textMuted, bg: colors.surfaceAlt },
}

export function StatusPill({ label, tone = 'muted' }: { label: string; tone?: Tone }) {
  const t = TONE[tone]
  return (
    <View style={[styles.pill, { backgroundColor: t.bg }]}>
      <AppText variant="caption" color={t.fg} weight="semibold">
        {label}
      </AppText>
    </View>
  )
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { key: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <View style={styles.segWrap}>
      {options.map((o) => {
        const active = o.key === value
        return (
          <Pressable
            key={o.key}
            onPress={() => onChange(o.key)}
            accessibilityRole="tab"
            accessibilityLabel={o.label}
            accessibilityState={{ selected: active }}
            android_ripple={{ color: colors.surfaceAlt }}
            style={[styles.seg, active && styles.segActive]}
          >
            {/* برچسب‌ها واژه‌های بی‌فاصله‌اند («مغایرت‌دار»)، پس شکسته نمی‌شوند و
                در ستونِ یک‌سومِ خودشان جا نمی‌گیرند — با فونتِ بزرگ از کادر بیرون
                می‌زدند. سقفِ بزرگ‌نمایی نگهشان می‌دارد، و `numberOfLines` تضمینِ
                آخر است برای زبان‌های بلندتر. */}
            <AppText
              variant="label"
              color={active ? colors.onAccent : colors.textMuted}
              weight="bold"
              numberOfLines={1}
              maxFontSizeMultiplier={font.maxScale.dense}
            >
              {o.label}
            </AppText>
          </Pressable>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  pill: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill, alignSelf: 'flex-start' },
  segWrap: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: 4,
    gap: 4,
  },
  // ۴۸ کفِ هدفِ لمسیِ اندروید است. پیش از این ارتفاع فقط از padding می‌آمد و
  // روی فونتِ کوچک به ۳۰ می‌رسید — یعنی لمس با انگشتِ شست خطا می‌خورد.
  seg: {
    flex: 1,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: 4,
    borderRadius: radius.sm,
  },
  segActive: { backgroundColor: colors.accent },
})
