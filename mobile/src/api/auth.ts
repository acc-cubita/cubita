import { apiGet, apiPost } from './client'
import type { Me, TokenOut } from './types'

export const login = (email: string, password: string): Promise<TokenOut> =>
  apiPost<TokenOut>('/api/auth/login', { email, password })

export const fetchMe = (): Promise<Me> => apiGet<Me>('/api/auth/me')

/** خروجِ سمتِ سرور — رفرش‌توکن را باطل می‌کند (بی‌صدا؛ خطا مانعِ خروجِ محلی نمی‌شود). */
export const logout = (refreshToken: string): Promise<void> =>
  apiPost<void>('/api/auth/logout', { refresh_token: refreshToken })
