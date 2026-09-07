import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { StockCountsScreen } from '../screens/stock/StockCountsScreen'
import { StockCountScreen } from '../screens/stock/StockCountScreen'
import { StockScanScreen } from '../screens/stock/StockScanScreen'
import { colors, font } from '../theme'
import type { StockStackParams } from './types'

const Stack = createNativeStackNavigator<StockStackParams>()

export function StockStack() {
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
      <Stack.Screen name="StockCounts" component={StockCountsScreen} options={{ headerShown: false }} />
      <Stack.Screen
        name="StockCount"
        component={StockCountScreen}
        options={({ route }) => ({ title: route.params.title ?? 'انبارگردانی' })}
      />
      <Stack.Screen name="StockScan" component={StockScanScreen} options={{ title: 'اسکنِ بارکد' }} />
    </Stack.Navigator>
  )
}
