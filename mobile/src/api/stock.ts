import { apiGet, apiPost, apiPut } from './client'
import type { StockCountSession, StockCountSummary } from './types'

/**
 * انبارگردانی و بارکد — روی همان اندپوینت‌هایی که دسکتاپ استفاده می‌کند
 * (`backend/app/routers/stock_taking.py`). هیچ‌کدام تازه نیستند.
 *
 * مجوز: `inventory` — `view` برای دیدن، `create` برای جلسه‌ی تازه،
 * `update` برای ثبتِ شمارش و بستنِ جلسه.
 */

export const fetchStockCounts = () => apiGet<StockCountSummary[]>('/api/stock-counts')

export const fetchStockCount = (id: string) => apiGet<StockCountSession>(`/api/stock-counts/${id}`)

export const createStockCount = (body: { warehouse_id: string; count_date: string; notes?: string }) =>
  apiPost<StockCountSession>('/api/stock-counts', { notes: '', ...body })

/**
 * شمارشِ چند ردیف را ثبت می‌کند.
 *
 * ⚠️ **فقط ردیف‌هایی را بفرست که کاربر واقعاً دست زده.** بک‌اند این را به‌صورتِ
 * patchِ جزئی می‌بیند (`set_counts` فقط روی همان idهای فرستاده‌شده می‌نویسد). اگر
 * کلِ فهرست فرستاده شود، شمارشی که همکار روی گوشیِ دیگر در همین جلسه وارد کرده
 * با مقدارِ کهنه‌ی این گوشی **بی‌صدا بازنویسی می‌شود** — بدونِ خطا، فقط انبارِ غلط.
 */
export const setStockCounts = (id: string, lines: { line_id: string; counted_qty: string }[]) =>
  apiPut<StockCountSession>(`/api/stock-counts/${id}/counts`, { lines })

export const postStockCount = (id: string) =>
  apiPost<StockCountSession>(`/api/stock-counts/${id}/post`)

export const cancelStockCount = (id: string) =>
  apiPost<StockCountSession>(`/api/stock-counts/${id}/cancel`)

// نکته: `GET /api/items/by-barcode` هم در بک‌اند هست، ولی اینجا استفاده نمی‌شود:
// تطبیقِ بارکد در `stock/scanResolve.ts` **محلی** انجام می‌شود تا در انبارِ بدونِ
// آنتن هم کار کند. دلیلِ کامل آنجا نوشته شده.
