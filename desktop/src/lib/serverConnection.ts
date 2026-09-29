export type ConnectionState = 'checking' | 'starting' | 'ready' | 'offline' | 'maintenance'
  | 'permission' | 'missing' | 'repair' | 'client' | 'unconfigured'

export interface ServerConnection {
  state: ConnectionState
  message: string
  url: string | null
}

export const CONNECTION_EVENT = 'cubita:server-reconnected'

export function connectionError(error: unknown, fallback = 'درخواست انجام نشد؛ دوباره امتحان کنید.'): string {
  const text = error instanceof Error ? error.message : typeof error === 'string' ? error : fallback
  return /failed to fetch|fetch failed|networkerror|ECONNREFUSED|ETIMEDOUT|timeout/i.test(text)
    ? 'ارتباط با سرور برقرار نیست؛ برنامه اتصال را خودکار دوباره بررسی می‌کند. کارهای ذخیره‌شده و صف اسناد محفوظ‌اند.'
    : text
}
