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
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `خطای سرور (${res.status})`)
  }
  return res.json()
}

export function fetchPlans(): Promise<Plan[]> {
  return request<Plan[]>('/api/plans')
}

export function requestPurchase(data: PurchaseRequest): Promise<{ purchase_id: string; payment_url: string }> {
  return request('/api/purchases', { method: 'POST', body: JSON.stringify(data) })
}
