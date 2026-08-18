import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import * as SecureStore from 'expo-secure-store'
import * as LocalAuthentication from 'expo-local-authentication'
import { fetchMe, login as apiLogin } from '../api/auth'
import { setAccessToken, setOnUnauthorized } from '../api/client'
import type { Me } from '../api/types'

const ACCESS_KEY = 'cubita.access'

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('restoring')
  const [me, setMe] = useState<Me | null>(null)
  const [biometricAvailable, setBiometricAvailable] = useState(false)
  const tokenRef = useRef<string | null>(null)

  const loadMe = useCallback(async () => {
    const m = await fetchMe()
    setMe(m)
    return m
  }, [])

  const signOut = useCallback(async () => {
    tokenRef.current = null
    setAccessToken(null)
    setMe(null)
    await SecureStore.deleteItemAsync(ACCESS_KEY)
    setStatus('unauth')
  }, [])

  // ۴۰۱ از هر درخواستی → خروجِ خودکار.
  useEffect(() => {
    setOnUnauthorized(() => {
      void signOut()
    })
    return () => setOnUnauthorized(null)
  }, [signOut])

  // بازیابیِ نشست در بدو اجرا.
  useEffect(() => {
    void (async () => {
      const [hasHw, enrolled, stored] = await Promise.all([
        LocalAuthentication.hasHardwareAsync(),
        LocalAuthentication.isEnrolledAsync(),
        SecureStore.getItemAsync(ACCESS_KEY),
      ])
      const canBio = hasHw && enrolled
      setBiometricAvailable(canBio)

      if (!stored) {
        setStatus('unauth')
        return
      }
      tokenRef.current = stored
      setAccessToken(stored)
      if (canBio) {
        // نشستِ برگشتی: پیش از نمایشِ داده، قفلِ بیومتریک.
        setStatus('locked')
      } else {
        try {
          await loadMe()
          setStatus('authed')
        } catch {
          await signOut()
        }
      }
    })()
  }, [loadMe, signOut])

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
      await signOut()
      return false
    }
  }, [loadMe, signOut])

  const signIn = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await apiLogin(email.trim(), password)
      tokenRef.current = access_token
      setAccessToken(access_token)
      await SecureStore.setItemAsync(ACCESS_KEY, access_token)
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
