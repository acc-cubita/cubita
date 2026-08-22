import { useEffect } from 'react'
import { Platform } from 'react-native'
import * as Device from 'expo-device'
import * as Notifications from 'expo-notifications'
import { useQueryClient } from '@tanstack/react-query'
import { navigateFromRoute } from '../navigation/navigationRef'

// اعلان در پیش‌زمینه هم بنر و صدا داشته باشد (APIِ SDK 57).
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
})

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== 'android') return
  await Notifications.setNotificationChannelAsync('default', {
    name: 'اعلان‌های کوبیتا',
    importance: Notifications.AndroidImportance.DEFAULT,
    lightColor: '#ffc72c',
  })
}

/** توکنِ نیتیوِ FCMِ دستگاه را می‌گیرد.
 *
 *  اگر روی شبیه‌ساز باشد، مجوز رد شود، یا FCM هنوز کانفیگ نشده باشد (بدونِ
 *  google-services.json)، به‌جای کرش **null** برمی‌گرداند — پس اپ بی‌اعلان هم سالم کار می‌کند
 *  تا وقتی زیرساختِ Firebase آماده شود. */
export async function getFcmToken(): Promise<string | null> {
  try {
    if (!Device.isDevice) return null
    await ensureAndroidChannel()
    let status = (await Notifications.getPermissionsAsync()).status
    if (status !== 'granted') {
      status = (await Notifications.requestPermissionsAsync()).status
    }
    if (status !== 'granted') return null
    const token = await Notifications.getDevicePushTokenAsync()
    return typeof token.data === 'string' ? token.data : null
  } catch {
    return null
  }
}

function routeOf(resp: Notifications.NotificationResponse | null): string | undefined {
  const data = resp?.notification.request.content.data as { route?: string } | undefined
  return typeof data?.route === 'string' ? data.route : undefined
}

/** رفتارِ سمتِ اپ برای اعلان‌ها:
 *  - **لمسِ اعلان** (گرم یا سردِ راه‌اندازی) → باز شدنِ مستقیمِ چت/بازار (deep link).
 *  - **دریافت در پیش‌زمینه** → تازه‌کردنِ نشانِ خوانده‌نشده‌ی بازار.
 *  داخلِ NavigationContainer و QueryClientProvider صدا می‌شود تا ناوبری و کش هر دو در دسترس باشند. */
export function usePushNotifications(): void {
  const qc = useQueryClient()
  useEffect(() => {
    let mounted = true
    // اپ با لمسِ یک اعلان باز شده باشد.
    void Notifications.getLastNotificationResponseAsync().then((resp) => {
      if (mounted) navigateFromRoute(routeOf(resp))
    })
    const tap = Notifications.addNotificationResponseReceivedListener((resp) => {
      navigateFromRoute(routeOf(resp))
    })
    const recv = Notifications.addNotificationReceivedListener(() => {
      void qc.invalidateQueries({ queryKey: ['mp-unread'] })
    })
    return () => {
      mounted = false
      tap.remove()
      recv.remove()
    }
  }, [qc])
}

/** کامپوننتِ بی‌نمایش که رفتارِ اعلان‌ها را نصب می‌کند؛ داخلِ NavigationContainer رندر می‌شود. */
export function PushGate(): null {
  usePushNotifications()
  return null
}
