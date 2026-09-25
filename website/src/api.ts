export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'https://acc.cubita.ir'

/** محصولی که درخواستِ خرید درباره‌اش است — همان `SALES_PRODUCTS`ِ بک‌اند. */
export type SalesProduct = 'cloud' | 'desktop' | 'enterprise' | 'mobile' | 'unsure'

export interface SalesInquiryRequest {
  name: string
  company: string
  phone: string
  email: string
  product: SalesProduct
  seats: number | null
  message: string
  /** تله‌ی ربات — همیشه خالی از آدم. */
  website: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const hasBody = init?.body != null
  // Content-Type فقط وقتی بدنه هست. افزودنش روی GET درخواست را «غیرِ ساده» می‌کند و
  // مرورگر را وادار به preflightِ OPTIONS می‌کند؛ روی موبایلِ کند این round-tripِ دوم
  // شکننده است. GET حالا درخواستِ ساده است.
  const headers = { ...(hasBody ? { 'Content-Type': 'application/json' } : {}), ...(init?.headers ?? {}) }
  // فقط GET (idempotent) را retry کن؛ POST را نه، تا درخواست دوباره ثبت نشود.
  const attempts = method === 'GET' ? 3 : 1

  let lastErr: unknown
  for (let attempt = 0; attempt < attempts; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 12000)
    try {
      const res = await fetch(`${API_BASE}${path}`, { ...init, headers, signal: init?.signal ?? controller.signal })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `خطای سرور (${res.status})`)
      }
      return (await res.json()) as T
    } catch (err) {
      lastErr = err
      if (attempt < attempts - 1) await new Promise((r) => setTimeout(r, 600 * (attempt + 1)))
    } finally {
      clearTimeout(timer)
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error('خطا در ارتباط با سرور')
}

//: پلن‌های قیمت‌دار از سایت برداشته شدند (۱۴۰۵/۰۷/۰۳) — خرید از راهِ فرمِ «تماس برای خرید» است.
export function submitSalesInquiry(data: SalesInquiryRequest): Promise<{ ok: boolean }> {
  return request('/api/sales-inquiries', { method: 'POST', body: JSON.stringify(data) })
}
