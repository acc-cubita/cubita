import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { HomeScreen } from '../screens/HomeScreen'
import { AlertsScreen } from '../screens/AlertsScreen'
import { TreasuryScreen } from '../screens/TreasuryScreen'
import { OutboxScreen } from '../screens/OutboxScreen'
import { ContactPickerScreen } from '../screens/ContactPickerScreen'
import { NewInvoiceScreen } from '../screens/NewInvoiceScreen'
import { ItemPickerScreen } from '../screens/ItemPickerScreen'
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
        name="Outbox"
        component={OutboxScreen}
        options={{ title: 'صفِ ارسال' }}
      />
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
      <Stack.Screen name="NewInvoice" component={NewInvoiceScreen} options={{ title: 'فاکتورِ فروش' }} />
      <Stack.Screen name="ItemPicker" component={ItemPickerScreen} options={{ title: 'انتخابِ کالا' }} />
    </Stack.Navigator>
  )
}
