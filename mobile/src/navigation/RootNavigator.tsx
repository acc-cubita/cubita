import { NavigationContainer, DarkTheme, type Theme as NavTheme } from '@react-navigation/native'
import { ActivityIndicator, StyleSheet, View } from 'react-native'
import { useAuth } from '../auth/AuthContext'
import { LoginScreen } from '../screens/LoginScreen'
import { LockScreen } from '../screens/LockScreen'
import { MainTabs } from './MainTabs'
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
    <NavigationContainer theme={navTheme}>
      <MainTabs />
    </NavigationContainer>
  )
}

const styles = StyleSheet.create({
  splash: { flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' },
})
