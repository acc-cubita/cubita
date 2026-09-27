/**
 * نشانِ کوبیتا («خانه‌ها»): هشت خانه‌ی جدول که حرفِ C را می‌سازند؛ خانه‌ی بنفشِ بالا «خانه‌ی فعالِ برگه» است.
 * همان کاشیِ فاوآیکون و آیکونِ برنامه — هندسه‌اش با scripts/gen-brand-assets.mjs یکی است.
 */
const CELLS = [
  [24, 24],
  [50, 24],
  [24, 50],
  [24, 76],
  [50, 76],
  [76, 76],
] as const

export function BrandMark({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <rect width="120" height="120" rx="28" fill="#17130C" />
      {CELLS.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="20" height="20" rx="5" fill="#FFC72C" />
      ))}
      <rect x="76" y="24" width="20" height="20" rx="5" fill="#A592E9" />
    </svg>
  )
}
