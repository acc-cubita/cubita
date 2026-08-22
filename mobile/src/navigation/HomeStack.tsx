import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { HomeScreen } from '../screens/HomeScreen'
import { AlertsScreen } from '../screens/AlertsScreen'
import { colors, font } from '../theme'
import type { HomeStackParams } from './types'

const Stack = createNativeStackNavigator<HomeStackParams>()

export function HomeStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: font.weight.bold },
        contentStyle: { backgroundColor: colors.bg },
        headerShadowVisible: false,
      }}
    >
      <Stack.Screen name="Dashboard" component={HomeScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Alerts" component={AlertsScreen} options={{ title: 'هشدارها' }} />
    </Stack.Navigator>
  )
}
