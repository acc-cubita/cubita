import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { ReportsListScreen } from '../screens/reports/ReportsListScreen'
import { IncomeStatementScreen } from '../screens/reports/IncomeStatementScreen'
import { BalanceSheetScreen } from '../screens/reports/BalanceSheetScreen'
import { AgingScreen } from '../screens/reports/AgingScreen'
import { InventoryScreen } from '../screens/reports/InventoryScreen'
import { colors, font } from '../theme'
import type { ReportsStackParams } from './types'

const Stack = createNativeStackNavigator<ReportsStackParams>()

export function ReportsStack() {
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
      <Stack.Screen name="ReportsList" component={ReportsListScreen} options={{ headerShown: false }} />
      <Stack.Screen name="IncomeStatement" component={IncomeStatementScreen} options={{ title: 'سود و زیان' }} />
      <Stack.Screen name="BalanceSheet" component={BalanceSheetScreen} options={{ title: 'ترازنامه' }} />
      <Stack.Screen
        name="Aging"
        component={AgingScreen}
        options={({ route }) => ({ title: route.params.kind === 'receivable' ? 'مطالبات' : 'بدهی‌ها' })}
      />
      <Stack.Screen name="Inventory" component={InventoryScreen} options={{ title: 'ارزشِ موجودی' }} />
    </Stack.Navigator>
  )
}
