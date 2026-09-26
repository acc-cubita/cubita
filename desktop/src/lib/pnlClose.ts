import type { PnlPreview, PnlPreviewRow } from '../api'

/**
 * منطقِ خالصِ «بستن حساب‌های سود و زیان» — پیش‌نمایشِ همان سندی که صادر می‌شود.
 *
 * ردیف‌ها و شرحشان از سرور است (`_pnl_rows`، یک محاسبه برای پیش‌نمایش و صدور)؛ این‌جا فقط چیزهایی است که رابط از
 * روی همان داده می‌سازد: کلیدِ ردیف، بُعدها زیرِ حساب، خطِ مقصد و حالِ نوارِ پایین.
 */

export const pnlRowKey = (r: Pick<PnlPreviewRow, 'account_id' | 'analytic_id' | 'cost_center_id'>): string =>
  `${r.account_id}|${r.analytic_id ?? ''}|${r.cost_center_id ?? ''}`

/** بُعدهای ردیف ستونِ تازه نمی‌گیرند — هویتِ ردیف‌اند، پس زیرِ خودِ حساب می‌نشینند (همان الگوی تسعیر). */
export function dimsText(
  r: Pick<PnlPreviewRow, 'analytic_code' | 'analytic_name' | 'cost_center_name'>,
): string | null {
  const parts = [
    r.analytic_name ? `تفصیلی: ${r.analytic_code ? `${r.analytic_code} ` : ''}${r.analytic_name}` : null,
    r.cost_center_name ? `مرکز: ${r.cost_center_name}` : null,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : null
}

/** خطِ مقصد: سود بستانکارِ سود انباشته می‌شود و زیان بدهکارش. دوره‌ی بی سود و زیان خطِ مقصد ندارد. */
export function destinationLine(p: Pick<PnlPreview, 'net_profit'>): { debit: number; credit: number } | null {
  const net = Number(p.net_profit)
  if (!net) return null
  return net > 0 ? { debit: 0, credit: net } : { debit: -net, credit: 0 }
}

/**
 * حالِ نوارِ پایین:
 * * `none` — در بازه فعالیتِ درآمد و هزینه نیست، سندی لازم نیست؛
 * * `off` — سندِ پیش‌نمایش ناتراز است (نباید رخ دهد؛ صدور بسته می‌ماند)؛
 * * `profit` / `loss` / `even` — سود، زیان، یا درآمد و هزینه‌ی برابر (ردیف‌ها بسته می‌شوند ولی خطِ مقصد نیست).
 */
export type PnlState = 'none' | 'off' | 'profit' | 'loss' | 'even'

export function pnlState(p: Pick<PnlPreview, 'rows' | 'difference' | 'net_profit'>): PnlState {
  if (p.rows.length === 0) return 'none'
  if (Number(p.difference) !== 0) return 'off'
  const net = Number(p.net_profit)
  return net > 0 ? 'profit' : net < 0 ? 'loss' : 'even'
}

/** رنگِ نوار: سود سبز، زیان و ناتراز قرمز (قراردادِ حسابداری، مثلِ تسعیر)، بقیه خاکستری. */
export const PNL_TONE: Record<PnlState, 'ok' | 'err' | 'empty'> = {
  none: 'empty',
  off: 'err',
  profit: 'ok',
  loss: 'err',
  even: 'empty',
}
