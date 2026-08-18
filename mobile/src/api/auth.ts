import { apiGet, apiPost } from './client'
import type { Me, TokenOut } from './types'

// توابعِ احراز هویت. رفرش/خروجِ سمتِ سرور در M1 اضافه می‌شود.

export const login = (email: string, password: string): Promise<TokenOut> =>
  apiPost<TokenOut>('/api/auth/login', { email, password })

export const fetchMe = (): Promise<Me> => apiGet<Me>('/api/auth/me')
