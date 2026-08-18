import Svg, { Defs, LinearGradient, Rect, Stop, Circle } from 'react-native-svg'
import { colors } from '../theme'

// نشانِ برندِ کوبیتا — مربعِ گِردِ طلایی با میله‌ها و نقطه‌ی بنفش. نیتیو با SVG رسم
// می‌شود (نه کپیِ CSSِ وب). همان هویتِ رنگیِ برند، اجرای مستقلِ اپ.
export function BrandMark({ size = 48 }: { size?: number }) {
  const r = size * 0.22
  return (
    <Svg width={size} height={size} viewBox="0 0 48 48">
      <Defs>
        <LinearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor="#ffe6a6" />
          <Stop offset="1" stopColor="#ef9f10" />
        </LinearGradient>
      </Defs>
      <Rect x="1.5" y="1.5" width="45" height="45" rx={r} fill="url(#g)" />
      <Rect x="12" y="26" width="6.5" height="10" rx="2" fill="#1a1400" />
      <Rect x="20.75" y="20" width="6.5" height="16" rx="2" fill="#1a1400" />
      <Rect x="29.5" y="14" width="6.5" height="22" rx="2" fill="#1a1400" />
      <Circle cx="33" cy="13" r="4.5" fill={colors.violet} />
    </Svg>
  )
}
