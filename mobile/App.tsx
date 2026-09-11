import 'react-native-gesture-handler'
import { useEffect, useState } from 'react'
import { I18nManager, View } from 'react-native'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { StatusBar } from 'expo-status-bar'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { AuthProvider } from './src/auth/AuthContext'
import { AppUpdateProvider } from './src/update/AppUpdateProvider'
import { RootNavigator } from './src/navigation/RootNavigator'
import { ErrorBoundary } from './src/errors/ErrorBoundary'
import { flush, installGlobalHandler } from './src/errors/reporter'
import { OfflineBanner } from './src/offline/OfflineBanner'
import { OutboxBadge } from './src/offline/OutboxBadge'
import { navigateFromRoute } from './src/navigation/navigationRef'
import { drain } from './src/offline/outbox'
import { loadCache, startPersisting } from './src/offline/persist'
import { syncAllDrafts } from './src/stock/countDraft'
import { colors } from './src/theme'

// RTLِ فارسی. اعمالِ کاملش ممکن است به یک ری‌لود نیاز داشته باشد (نصبِ اول).
I18nManager.allowRTL(true)
I18nManager.forceRTL(true)

// گزارشِ کرش پیش از هر چیزِ دیگر نصب می‌شود — خطای خودِ راه‌اندازی هم باید گرفته شود.
installGlobalHandler()
// گزارش‌هایی که دفعه‌ی قبل (شاید همان کرشی که اپ را کشت) نتوانستند ارسال شوند.
void flush()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // کشِ روی دیسک تا ۲۴ ساعت زنده است؛ اگر gcTime کوتاه‌تر بماند، react-query
      // داده‌ی بازیابی‌شده را بلافاصله دور می‌ریزد و کلِ ماندگاری بی‌اثر می‌شود.
      gcTime: 24 * 60 * 60 * 1000,
    },
  },
})

export default function App() {
  // پیش از رندر منتظرِ کشِ روی دیسک می‌مانیم. اگر همزمان رندر کنیم، کاربر یک لحظه
  // صفحه‌ی خالی می‌بیند و بعد داده می‌پرد وسط — که بدتر از یک مکثِ کوتاه است.
  const [cacheReady, setCacheReady] = useState(false)

  useEffect(() => {
    let stop: (() => void) | undefined
    loadCache(queryClient)
      .catch(() => false)
      .finally(() => {
        stop = startPersisting(queryClient)
        setCacheReady(true)
      })
    return () => stop?.()
  }, [])

  // وقتی شبکه برمی‌گردد، صفِ نوشتن خودش خالی شود. بدونِ این، کارِ آفلاینِ کاربر
  // تا وقتی دستی چیزِ دیگری ثبت نکند روی گوشی می‌ماند.
  useEffect(
    () =>
      onlineManager.subscribe((online) => {
        if (!online) return
        void drain()
        // شمارشِ انبارگردانی هم روی گوشی می‌ماند تا شبکه برگردد.
        void syncAllDrafts()
      }),
    [],
  )

  if (!cacheReady) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />
  }

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaProvider>
        {/* بیرونِ providerها: اگر خودِ AuthProvider یا ناوبری موقعِ رندر بشکند هم
            کاربر صفحه‌ی سفید نبیند. */}
        <ErrorBoundary>
          <QueryClientProvider client={queryClient}>
            <AuthProvider>
              <AppUpdateProvider>
                <StatusBar style="light" />
                <OfflineBanner />
                {/* لمسِ نوار به صفحه‌ی صف می‌برد؛ از همان مسیرِ اعلان‌ها رد می‌شود
                    تا یک نگاشتِ دوم ساخته نشود. */}
                <OutboxBadge onPress={() => navigateFromRoute('outbox')} />
                <RootNavigator />
              </AppUpdateProvider>
            </AuthProvider>
          </QueryClientProvider>
        </ErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  )
}
