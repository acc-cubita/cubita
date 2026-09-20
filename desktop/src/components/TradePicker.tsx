import { toggleGroup, toggleTrade } from '../lib/tradeSelection'
import { toFaDigits } from '../lib/jalali'
import type { TradeGroup } from '../api'

/**
 * شبکه‌ی چک‌باکسِ اصناف — گروه‌بندی‌شده، با دکمه‌ی «کلِ گروه».
 *
 * یک نسخه، دو مصرف‌کننده: اصنافِ کلیِ پخش‌کننده در تبِ تنظیمات، و اصنافِ اضافه‌ی یک
 * قلم در فرمِ لیستینگ (و ویزاردش). دو کپیِ موازی از ~۹۴ چک‌باکس یعنی هر اصلاحِ
 * بعدی باید دو بار انجام شود و یکی‌شان فراموش شود.
 */
export function TradePicker({
  groups,
  value,
  onChange,
}: {
  groups: TradeGroup[]
  value: string[]
  onChange: (next: string[]) => void
}) {
  const chosen = new Set(value)
  return (
    <div className="trade-picker">
      {groups.map((g) => {
        const keys = g.trades.map((t) => t.key)
        const allOn = keys.every((k) => chosen.has(k))
        return (
          <div key={g.key} className="trade-group">
            <div className="trade-group-head">
              <span className="trade-group-title">{g.label}</span>
              <button type="button" className="link-btn" onClick={() => onChange(toggleGroup(value, keys))}>
                {allOn ? 'برداشتنِ گروه' : 'کلِ گروه'}
              </button>
            </div>
            <div className="trade-items">
              {g.trades.map((t) => (
                <label key={t.key} className="cal-check-inline">
                  <input
                    type="checkbox"
                    checked={chosen.has(t.key)}
                    onChange={() => onChange(toggleTrade(value, t.key))}
                  />
                  {t.label}
                </label>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/**
 * راهنمای فیلدستِ «اصنافِ اضافه» — یک متن، دو مصرف‌کننده (فرمِ کلاسیک و ویزارد).
 *
 * حالتِ اول عمدی است: وقتی پخش‌کننده اصلاً صنفِ کلی نگذاشته، کاتالوگش برای همه باز
 * است و انتخابِ این‌جا **هیچ اثری ندارد**. سکوت در این حالت یعنی کاربر چند تیک
 * می‌زند، ذخیره می‌کند و هرگز نمی‌فهمد چرا چیزی عوض نشد.
 */
export function ExtraTradesHint({ count, ownTargets }: { count: number; ownTargets: string[] }) {
  if (ownTargets.length === 0) {
    return (
      <p className="mp-limit-hint">
        شما هنوز <b>اصنافِ کلی</b> انتخاب نکرده‌اید، پس کاتالوگتان برای همه‌ی فروشگاه‌ها باز
        است و انتخابِ این‌جا چیزی را عوض نمی‌کند. اول در تبِ «تنظیمات» اصنافِ کلی را مشخص
        کنید.
      </p>
    )
  }
  return (
    <p className="field-hint">
      این قلم <b>علاوه بر</b> اصنافِ کلیِ شما، به این اصناف هم نشان داده می‌شود — بدونِ اینکه
      بقیه‌ی کاتالوگتان برایشان باز شود.
      {count > 0 && ` ${toFaDigits(String(count))} صنف انتخاب شده.`}
    </p>
  )
}
