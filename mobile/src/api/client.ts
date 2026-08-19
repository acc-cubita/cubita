import { API_BASE_URL } from './config'
import type { Page } from './types'

// کلاینتِ نازکِ HTTP: تزریقِ توکن، رفرشِ خودکار روی ۴۰۱، مدیریتِ خطا، و پیمایشِ keyset.

let accessToken: string | null = null
let refreshToken: string | null = null

/** هر دو توکنِ نشست را ست می‌کند (یا با null پاک می‌کند). */
export function setTokens(access: string | null, refresh: string | null): void {
  accessToken = access
  refreshToken = refresh
}

// وقتی رفرشِ چرخشی توکنِ تازه داد، لایه‌ی احراز باید آن را ماندگار (SecureStore) کند
// تا با بستنِ اپ از دست نرود.
let onTokens: ((access: string, refresh: string) => void) | null = null
export function setOnTokens(cb: ((access: string, refresh: string) => void) | null): void {
  onTokens = cb
}

// وقتی حتی رفرش هم نتوانست نشست را زنده کند، لایه‌ی احراز باید کاربر را خارج کند.
let onUnauthorized: (() => void) | null = null
export function setOnUnauthorized(cb: (() => void) | null): void {
  onUnauthorized = cb
}

export interface ApiError {
  status: number
  message: string
}

function isApiError(e: unknown): e is ApiError {
  return typeof e === 'object' && e !== null && 'status' in e && 'message' in e
}
export { isApiError }

// مسیرهای احرازی که خودشان با ۴۰۱ حرف می‌زنند (رمزِ غلط، رفرشِ باطل) — نباید رفرش/خروج
// را تریگر کنند؛ پیامِ خطای خودِ سرور باید به کاربر برسد.
function isAuthPath(path: string): boolean {
  return (
    path.startsWith('/api/auth/login') ||
    path.startsWith('/api/auth/refresh') ||
    path.startsWith('/api/auth/logout')
  )
}

// رفرشِ تک‌پروازه: چند درخواستِ همزمان که ۴۰۱ می‌گیرند فقط یک بار رفرش را صدا می‌زنند.
let refreshing: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const j = (await res.json()) as { access_token: string; refresh_token?: string }
    accessToken = j.access_token
    if (j.refresh_token) refreshToken = j.refresh_token
    onTokens?.(accessToken, refreshToken as string)
    return true
  } catch {
    return false
  }
}

function tryRefresh(): Promise<boolean> {
  if (!refreshing) refreshing = doRefresh().finally(() => (refreshing = null))
  return refreshing
}

async function request<T>(method: string, path: string, body?: unknown, isRetry = false): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw { status: 0, message: 'اتصال به سرور برقرار نشد. اینترنت را بررسی کنید.' } as ApiError
  }

  if (res.status === 401 && !isAuthPath(path)) {
    // یک بار با رفرش‌توکن، accessِ تازه بگیر و همان درخواست را دوباره بزن.
    if (!isRetry && (await tryRefresh())) {
      return request<T>(method, path, body, true)
    }
    onUnauthorized?.()
    throw { status: 401, message: 'نشست منقضی شده است؛ دوباره وارد شوید.' } as ApiError
  }

  if (!res.ok) {
    let message = `خطای سرور (${res.status})`
    try {
      const j = await res.json()
      if (j && typeof j.detail === 'string') message = j.detail
    } catch {
      // بدنه‌ی غیرJSON یا خالی — همان پیامِ پیش‌فرض
    }
    throw { status: res.status, message } as ApiError
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const apiGet = <T>(path: string): Promise<T> => request<T>('GET', path)
export const apiPost = <T>(path: string, body?: unknown): Promise<T> => request<T>('POST', path, body)
export const apiPatch = <T>(path: string, body?: unknown): Promise<T> => request<T>('PATCH', path, body)
export const apiDelete = <T>(path: string): Promise<T> => request<T>('DELETE', path)

/** همه‌ی صفحاتِ یک اندپوینتِ keyset را دنبال می‌کند (والدِ الگو: authedGetAll در دسکتاپ). */
export async function apiGetAll<T>(path: string): Promise<T[]> {
  const all: T[] = []
  const sep = path.includes('?') ? '&' : '?'
  let cursor: string | null = null
  for (let i = 0; i < 100; i += 1) {
    const suffix = cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''
    const url: string = `${path}${sep}limit=200${suffix}`
    const page: Page<T> | T[] = await apiGet<Page<T> | T[]>(url)
    if (Array.isArray(page)) {
      all.push(...page)
      break
    }
    all.push(...page.items)
    if (!page.next_cursor) break
    cursor = page.next_cursor
  }
  return all
}
