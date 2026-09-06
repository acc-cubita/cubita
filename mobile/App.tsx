import 'react-native-gesture-handler'
import { I18nManager } from 'react-native'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { StatusBar } from 'expo-status-bar'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './src/auth/AuthContext'
import { AppUpdateProvider } from './src/update/AppUpdateProvider'
import { RootNavigator } from './src/navigation/RootNavigator'
import { ErrorBoundary } from './src/errors/ErrorBoundary'
import { flush, installGlobalHandler } from './src/errors/reporter'
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
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
})

export default function App() {
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
                <RootNavigator />
              </AppUpdateProvider>
            </AuthProvider>
          </QueryClientProvider>
        </ErrorBoundary>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  )
}
