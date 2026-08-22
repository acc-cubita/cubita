import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import * as SecureStore from 'expo-secure-store'
import * as LocalAuthentication from 'expo-local-authentication'
import { fetchMe, login as apiLogin, logout as apiLogout } from '../api/auth'
import { setOnTokens, setOnUnauthorized, setTokens } from '../api/client'
import { registerDevice, unregisterDevice } from '../api/devices'
import { getFcmToken } from '../push/notifications'
import type { Me } from '../api/types'

const ACCESS_KEY = 'cubita.access'
const REFRESH_KEY = 'cubita.refresh'

type Status = 'restoring' | 'unauth' | 'locked' | 'authed'

interface AuthValue {
  status: Status
  me: Me | null
  /** ورود با ایمیل/رمز. خطا را throw می‌کند تا فرم پیام دهد. */
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  /** بازکردنِ قفلِ بیومتریک (وقتی status === 'locked'). */
  unlock: () => Promise<boolean>
  /** آیا سخت‌افزار/ثبتِ بیومتریک هست (برای نمایشِ دکمه‌ی مناسب). */
  biometricAvailable: boolean
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

async function persistTokens(access: string, refresh: string): Promise<void> {
  await Promise.all([
    SecureStore.setItemAsync(ACCESS_KEY, access),
    SecureStore.setItemAsync(REFRESH_KEY, refresh),
  ])
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('restoring')
  const [me, setMe] = useState<Me | null>(null)
  const [biometricAvailable, setBiometricAvailable] = useState(false)
  // آخرین رفرش‌توکن — برای صدا زدنِ خروجِ سمتِ سرور. رفرشِ چرخشی این را به‌روز نگه می‌دارد.
  const refreshRef = useRef<string | null>(null)
  // توکنِ FCMِ ثبت‌شده‌ی این دستگاه — برای لغوِ ثبت هنگامِ خروج.
  const deviceTokenRef = useRef<string | null>(null)

  const loadMe = useCallback(async () => {
    const m = await fetchMe()
    setMe(m)
    return m
  }, [])

  const clearSession = useCallback(async () => {
    refreshRef.current = null
    setTokens(null, null)
    setMe(null)
    await Promise.all([
      SecureStore.deleteItemAsync(ACCESS_KEY),
      SecureStore.deleteItemAsync(REFRESH_KEY),
    ])
    setStatus('unauth')
  }, [])

  const signOut = useCallback(async () => {
    // لغوِ ثبتِ دستگاه پیش از بستنِ نشست تا این گوشی دیگر Push نگیرد (بهترین‌تلاش).
    const deviceToken = deviceTokenRef.current
    if (deviceToken) {
      try {
        await unregisterDevice(deviceToken)
      } catch {
        // خروجِ محلی نباید به لغوِ اعلان گره بخورد.
      }
      deviceTokenRef.current = null
    }
    // خروجِ سمتِ سرور: رفرش را باطل کن تا نشست واقعاً بسته شود (بهترین‌تلاش).
    const refresh = refreshRef.current
    if (refresh) {
      try {
        await apiLogout(refresh)
      } catch {
        // شبکه/باطل‌بودن مانعِ خروجِ محلی نمی‌شود.
      }
    }
    await clearSession()
  }, [clearSession])

  // رفرشِ چرخشیِ کلاینت توکنِ تازه داد → ماندگارش کن تا با بستنِ اپ از دست نرود.
  useEffect(() => {
    setOnTokens((access, refresh) => {
      refreshRef.current = refresh
      void persistTokens(access, refresh)
    })
    return () => setOnTokens(null)
  }, [])

  // ۴۰۱ که حتی رفرش هم نتوانست زنده‌اش کند → خروجِ محلی (بدونِ صدا زدنِ سرور؛ رفرش مرده است).
  useEffect(() => {
    setOnUnauthorized(() => {
      void clearSession()
    })
    return () => setOnUnauthorized(null)
  }, [clearSession])

  // بازیابیِ نشست در بدو اجرا.
  useEffect(() => {
    void (async () => {
      const [hasHw, enrolled, storedAccess, storedRefresh] = await Promise.all([
        LocalAuthentication.hasHardwareAsync(),
        LocalAuthentication.isEnrolledAsync(),
        SecureStore.getItemAsync(ACCESS_KEY),
        SecureStore.getItemAsync(REFRESH_KEY),
      ])
      const canBio = hasHw && enrolled
      setBiometricAvailable(canBio)

      if (!storedAccess) {
        setStatus('unauth')
        return
      }
      refreshRef.current = storedRefresh
      setTokens(storedAccess, storedRefresh)
      if (canBio) {
        // نشستِ برگشتی: پیش از نمایشِ داده، قفلِ بیومتریک.
        setStatus('locked')
      } else {
        try {
          // اگر accessِ ۸ساعته منقضی باشد، کلاینت خودش با رفرش زنده‌اش می‌کند.
          await loadMe()
          setStatus('authed')
        } catch {
          await clearSession()
        }
      }
    })()
  }, [loadMe, clearSession])

  // پس از احراز، دستگاه را برای Push ثبت کن. بهترین‌تلاش: اگر مجوز رد شود یا FCM هنوز
  // کانفیگ نشده باشد، getFcmToken برابرِ null است و بی‌صدا رد می‌شویم.
  useEffect(() => {
    if (status !== 'authed') return
    let cancelled = false
    void (async () => {
      const token = await getFcmToken()
      if (cancelled || !token) return
      deviceTokenRef.current = token
      try {
        await registerDevice(token)
      } catch {
        // ثبتِ اعلان نباید مانعِ استفاده از اپ شود.
      }
    })()
    return () => {
      cancelled = true
    }
  }, [status])

  const unlock = useCallback(async (): Promise<boolean> => {
    const res = await LocalAuthentication.authenticateAsync({
      promptMessage: 'برای ورود به کوبیتا احراز هویت کنید',
      cancelLabel: 'انصراف',
    })
    if (!res.success) return false
    try {
      await loadMe()
      setStatus('authed')
      return true
    } catch {
      await clearSession()
      return false
    }
  }, [loadMe, clearSession])

  const signIn = useCallback(
    async (email: string, password: string) => {
      const { access_token, refresh_token } = await apiLogin(email.trim(), password)
      const refresh = refresh_token ?? ''
      refreshRef.current = refresh
      setTokens(access_token, refresh)
      await persistTokens(access_token, refresh)
      await loadMe()
      setStatus('authed')
    },
    [loadMe],
  )

  const refreshMe = useCallback(async () => {
    await loadMe()
  }, [loadMe])

  return (
    <AuthContext.Provider
      value={{ status, me, signIn, signOut, unlock, biometricAvailable, refreshMe }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth باید داخلِ AuthProvider استفاده شود')
  return ctx
}
