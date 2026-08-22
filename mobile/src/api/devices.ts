import { apiDelete, apiPost } from './client'

//: توکنِ FCMِ این دستگاه را برای اعلانِ Push ثبت/به‌روزرسانی می‌کند (بک‌اند upsert می‌کند).
export function registerDevice(fcmToken: string, platform = 'android'): Promise<void> {
  return apiPost<void>('/api/devices', { fcm_token: fcmToken, platform })
}

//: توکنِ این دستگاه را هنگامِ خروج حذف می‌کند. token در query می‌آید چون کاراکترهای
//: ناسازگار با مسیر دارد.
export function unregisterDevice(fcmToken: string): Promise<void> {
  return apiDelete<void>(`/api/devices?token=${encodeURIComponent(fcmToken)}`)
}
