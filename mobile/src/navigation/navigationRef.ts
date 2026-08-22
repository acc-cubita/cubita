import { CommonActions, createNavigationContainerRef } from '@react-navigation/native'

//: مرجعِ ناوبری تا از بیرونِ درختِ کامپوننت‌ها (مثلِ لمسِ یک اعلانِ Push) بشود جابه‌جا شد.
export const navigationRef = createNavigationContainerRef()

/** `route`ِ payloadِ Push (مثلِ "chat/connection/123"، "chat/order/45"، یا "market") را
 *  به جابه‌جاییِ واقعی تبدیل می‌کند. اگر ناوبری آماده نباشد بی‌صدا رد می‌شود.
 *
 *  از `dispatch(CommonActions.navigate)` استفاده می‌شود چون refِ بدونِ تایپ برای
 *  navigate(name, params) اورلود ندارد. */
export function navigateFromRoute(route?: string): void {
  if (!route || !navigationRef.isReady()) return
  const parts = route.split('/').filter(Boolean)

  // چت داخلِ تبِ «بازار» است: chat/{connection|order}/{id}
  if (parts[0] === 'chat' && (parts[1] === 'connection' || parts[1] === 'order') && parts[2]) {
    navigationRef.dispatch(
      CommonActions.navigate('Market', { screen: 'Chat', params: { scope: parts[1], id: parts[2] } }),
    )
    return
  }

  // خانه‌ی بازار (اتصال/سفارشِ تازه، مرجوعی، …)
  if (parts[0] === 'market') {
    navigationRef.dispatch(CommonActions.navigate('Market', { screen: 'MarketHome' }))
    return
  }

  // دایجستِ روزانه‌ی هشدارها → صفحه‌ی هشدارها (تبِ خانه)
  if (parts[0] === 'alerts') {
    navigationRef.dispatch(CommonActions.navigate('Home', { screen: 'Alerts' }))
  }
}
