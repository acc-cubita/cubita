import { API_BASE_URL } from './config'
import type { Page } from './types'

// کلاینتِ نازکِ HTTP: تزریقِ توکن، مدیریتِ خطا، و پیمایشِ صفحه‌بندیِ keyset.
// رفرشِ خودکارِ توکن در M1 (پس از افزودنِ رفرش‌توکنِ بک‌اند) به همین‌جا اضافه می‌شود.

let accessToken: string | null = null
export function setAccessToken(token: string | null): void {
  accessToken = token
}

// وقتی توکن نامعتبر/منقضی شد (۴۰۱)، لایه‌ی احراز هویت باید کاربر را خارج کند.
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

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
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

  if (res.status === 401) {
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
