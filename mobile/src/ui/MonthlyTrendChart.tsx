import { useState } from 'react'
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native'
import Svg, { Line, Path } from 'react-native-svg'
import { AppText } from './index'
import { colors, faMoney, radius, spacing } from '../theme'
import type { DashboardMonth } from '../api/types'

// نمودارِ روندِ فروشِ ماهانه — تک‌سری (magnitude در زمان)، تنها رنگِ برند (طلایی).
// طبقِ dataviz: تک‌سری ⇒ بدونِ legend؛ عنوان سری را نام می‌برد. تضادِ رنگ با سطحِ
// تیره اعتبارسنجی شد. میله‌ها با سرِ گِرد و فاصله‌ی سطحی، خطِ پایه‌ی کم‌رنگ، برچسبِ
// پراکنده، و انتخاب با لمس.

const MONTHS_FA = ['فرو', 'ارد', 'خرد', 'تیر', 'مرد', 'شهر', 'مهر', 'آبا', 'آذر', 'دی', 'بهم', 'اسف']

function barPath(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h))
  // سرِ بالا گِرد، پایین صاف روی خطِ پایه.
  return `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${y + h} Z`
}

export function MonthlyTrendChart({ data }: { data: DashboardMonth[] }) {
  const [width, setWidth] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)

  const height = 150
  const padBottom = 20 // جای برچسبِ ماه
  const plotH = height - padBottom
  const values = data.map((d) => Number(d.sales) || 0)
  const max = Math.max(1, ...values)

  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)

  const n = data.length || 1
  const gap = 3 // فاصله‌ی سطحی بینِ میله‌ها
  const barW = width > 0 ? Math.max(4, (width - gap * (n - 1)) / n) : 0

  const sel = selected != null ? data[selected] : data[data.length - 1]
  const selIdx = selected != null ? selected : data.length - 1

  return (
    <View style={styles.wrap} onLayout={onLayout}>
      <View style={styles.headRow}>
        <AppText variant="label" color={colors.textMuted}>
          فروشِ ماهانه
        </AppText>
        {sel ? (
          <AppText variant="label" color={colors.accent}>
            {MONTHS_FA[(sel.jm - 1 + 12) % 12]} {(sel.jy % 100).toLocaleString('fa-IR')} · {faMoney(sel.sales)}
          </AppText>
        ) : null}
      </View>

      {width > 0 ? (
        <Svg width={width} height={height}>
          {/* خطِ پایه‌ی کم‌رنگ */}
          <Line x1={0} y1={plotH} x2={width} y2={plotH} stroke={colors.border} strokeWidth={1} />
          {data.map((d, i) => {
            const v = Number(d.sales) || 0
            const h = (v / max) * (plotH - 6)
            const x = i * (barW + gap)
            const y = plotH - h
            const isSel = i === selIdx
            return (
              <Path
                key={`${d.jy}-${d.jm}`}
                d={barPath(x, y, barW, Math.max(h, 2), 3)}
                fill={isSel ? colors.accent : colors.accentSoft}
                stroke={isSel ? 'none' : colors.accent}
                strokeWidth={isSel ? 0 : 1}
                onPress={() => setSelected(i)}
              />
            )
          })}
        </Svg>
      ) : (
        <View style={{ height }} />
      )}

      {/* برچسبِ پراکنده‌ی ماه: اول، وسط، آخر */}
      {width > 0 ? (
        <View style={styles.labels}>
          {data.map((d, i) => {
            const show = i === 0 || i === data.length - 1 || i === Math.floor(data.length / 2)
            return (
              <AppText
                key={`l-${d.jy}-${d.jm}`}
                variant="caption"
                color={colors.textFaint}
                style={{ width: barW + gap, textAlign: 'center' }}
              >
                {show ? MONTHS_FA[(d.jm - 1 + 12) % 12] : ''}
              </AppText>
            )
          })}
        </View>
      ) : null}
    </View>
  )
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm, borderRadius: radius.md },
  headRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  labels: { flexDirection: 'row', marginTop: -16 },
})
