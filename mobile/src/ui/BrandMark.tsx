import Svg, { Rect } from 'react-native-svg'

// نشانِ برندِ کوبیتا («خانه‌ها»): هشت خانه‌ی جدول که حرفِ C را می‌سازند و خانه‌ی بنفشِ فعال، روی کاشیِ
// تیره. نیتیو با SVG رسم می‌شود؛ هندسه همان desktop/scripts/gen-brand-assets.mjs است که آیکون‌های اپ را هم می‌سازد.
const CELLS = [
  [24, 24],
  [50, 24],
  [24, 50],
  [24, 76],
  [50, 76],
  [76, 76],
] as const

export function BrandMark({ size = 48 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 120 120">
      <Rect width="120" height="120" rx="28" fill="#17130C" />
      {CELLS.map(([x, y]) => (
        <Rect key={`${x}-${y}`} x={x} y={y} width="20" height="20" rx="5" fill="#FFC72C" />
      ))}
      <Rect x="76" y="24" width="20" height="20" rx="5" fill="#A592E9" />
    </Svg>
  )
}
