export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'https://acc.cubita.ir'

export type BillingPeriod = 'monthly' | 'semiannual' | 'yearly'

export interface Plan {
  id: string
  key: string
  name: string
  description: string
  price_toman: string
  billing_period: string
  //: نگاشتِ دوره→قیمت (تومان). با تعویضِ دوره، قیمتِ همان کارت از این خوانده می‌شود.
  prices: Partial<Record<BillingPeriod, string>>
  max_users: number | null
  features: string[]
  is_active: boolean
  sort_order: number
  highlighted: boolean
}

export interface PurchaseRequest {
  plan_key: string
  customer_name: string
  customer_email: string
  customer_phone: string
  business_name: string
  billing_period: BillingPeriod
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const hasBody = init?.body != null
  // Content-Type فقط وقتی بدنه هست. افزودنش روی GET درخواست را «غیرِ ساده» می‌کند و
  // مرورگر را وادار به preflightِ OPTIONS می‌کند؛ روی موبایلِ کند این round-tripِ دوم
  // شکننده است و باعثِ خطای «امکان دریافت پلن‌ها نیست» می‌شد. GET حالا درخواستِ ساده است.
  const headers = { ...(hasBody ? { 'Content-Type': 'application/json' } : {}), ...(init?.headers ?? {}) }
  // فقط GET (idempotent) را retry کن؛ POSTِ خرید را نه، تا تراکنش دوباره ثبت نشود.
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

export function fetchPlans(): Promise<Plan[]> {
  return request<Plan[]>('/api/plans')
}

export function requestPurchase(data: PurchaseRequest): Promise<{ purchase_id: string; payment_url: string }> {
  return request('/api/purchases', { method: 'POST', body: JSON.stringify(data) })
}
