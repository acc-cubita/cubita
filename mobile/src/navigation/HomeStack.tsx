import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { HomeScreen } from '../screens/HomeScreen'
import { AlertsScreen } from '../screens/AlertsScreen'
import { TreasuryScreen } from '../screens/TreasuryScreen'
import { ContactPickerScreen } from '../screens/ContactPickerScreen'
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
      <Stack.Screen
        name="Treasury"
        component={TreasuryScreen}
        options={({ route }) => ({ title: route.params.type === 'receipt' ? 'ثبتِ دریافت' : 'ثبتِ پرداخت' })}
      />
      <Stack.Screen
        name="ContactPicker"
        component={ContactPickerScreen}
        options={{ title: 'انتخابِ طرف‌حساب' }}
      />
    </Stack.Navigator>
  )
}
