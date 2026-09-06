import { NavigationContainer, DarkTheme, type LinkingOptions, type Theme as NavTheme } from '@react-navigation/native'
import { ActivityIndicator, StyleSheet, View } from 'react-native'
import { useAuth } from '../auth/AuthContext'
import { LoginScreen } from '../screens/LoginScreen'
import { LockScreen } from '../screens/LockScreen'
import { MainTabs } from './MainTabs'
import { navigationRef } from './navigationRef'
import { setCurrentScreen } from '../errors/reporter'
import { PushGate } from '../push/notifications'
import { BrandMark } from '../ui/BrandMark'
import { colors } from '../theme'

const navTheme: NavTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.bg,
    card: colors.surface,
    text: colors.text,
    border: colors.border,
    primary: colors.accent,
  },
}

// deep-link — پایه برای بازکردنِ مستقیمِ چت/اشخاص از روی اعلان یا لینک (cubita://).
// تحویلِ Push در M1 می‌آید؛ این نگاشت از حالا آماده است.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const linking: LinkingOptions<any> = {
  prefixes: ['cubita://', 'https://acc.cubita.ir'],
  config: {
    screens: {
      Home: { screens: { Dashboard: 'home', Alerts: 'alerts' } },
      Reports: { screens: { ReportsList: 'reports' } },
      Contacts: { screens: { ContactsList: 'contacts', ContactDetail: 'contacts/:id' } },
      Market: { screens: { MarketHome: 'market', Chat: 'chat/:scope/:id' } },
      More: 'more',
    },
  },
}

function Splash() {
  return (
    <View style={styles.splash}>
      <BrandMark size={72} />
      <ActivityIndicator color={colors.accent} style={{ marginTop: 24 }} />
    </View>
  )
}

export function RootNavigator() {
  const { status } = useAuth()
  if (status === 'restoring') return <Splash />
  if (status === 'unauth') return <LoginScreen />
  if (status === 'locked') return <LockScreen />
  return (
    <NavigationContainer
      ref={navigationRef}
      theme={navTheme}
      linking={linking}
      // گزارشِ کرش باید بگوید کاربر کجا بود. بدونِ این، یک stack traceِ minify‌شده
      // داریم و هیچ سرنخی از مسیرِ رسیدن به آن.
      //
      // cast به همان دلیلی است که `navigateFromRoute` از dispatch استفاده می‌کند:
      // `navigationRef` بدونِ ParamList ساخته شده، پس تایپِ خروجیِ getCurrentRoute
      // تهی می‌شود. فقط نامِ صفحه را می‌خواهیم.
      onStateChange={() => {
        const route = navigationRef.getCurrentRoute() as { name?: string } | undefined
        setCurrentScreen(route?.name ?? null)
      }}
    >
      <MainTabs />
      {/* بی‌نمایش: deep-linkِ لمسِ اعلان + تازه‌کردنِ نشانِ خوانده‌نشده. داخلِ کانتینر تا ناوبری آماده باشد. */}
      <PushGate />
    </NavigationContainer>
  )
}

const styles = StyleSheet.create({
  splash: { flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' },
})
